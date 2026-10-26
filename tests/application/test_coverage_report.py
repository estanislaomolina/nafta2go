"""Tests del reporte de cobertura que se corre al ejecutar la POC."""

import json
from datetime import UTC, datetime
from decimal import Decimal

from nafta2go.adapters.routing import Point
from nafta2go.application import coverage_rules
from nafta2go.application.coverage_report import REPORT_WINDOWS_DAYS, coverage_report
from nafta2go.coverage.__main__ import main
from nafta2go.persistence import repository as repo
from nafta2go.persistence.database import create_db_engine, upgrade_to_head

OBELISCO = Point(-34.6037, -58.3816)
CABILDO = Point(-34.5627, -58.4565)
REFERENCE = datetime(2026, 10, 24, 21, tzinfo=UTC)


def price_row(station_id, valid_from, lat=-34.59, lon=-58.41):
    return {
        "fila_origen": station_id,
        "idempresa": station_id,
        "empresa": "ESTACION SA",
        "empresabandera": "PRUEBA",
        "direccion": "DIRECCION",
        "idproducto": 2,
        "tipo_nafta": "super",
        "idtipohorario": 2,
        "precio": Decimal(1200),
        "fecha_vigencia": valid_from,
        "latitud": lat,
        "longitud": lon,
        "fecha_vigencia_original": str(valid_from),
        "precio_original": "1200",
        "alertas": "",
    }


def put_run(engine, rows):
    with engine.begin() as conn:
        run_id = repo.start_run(conn, "vigente", REFERENCE.replace(tzinfo=None))
        repo.add_prices(conn, run_id, rows)
        repo.finish_run(conn, run_id, "succeeded", REFERENCE.replace(tzinfo=None))
    return run_id


ROWS = [
    price_row(1, datetime(2026, 10, 22, 9)),  # 2 días, en el corredor
    price_row(2, datetime(2026, 9, 10, 9)),  # 44 días, en el corredor
    price_row(3, datetime(2026, 10, 22, 9), lat=-34.70, lon=-58.50),  # 2 días, lejos
]


def report(engine, **overrides):
    options = {"fuel_type": "super", "schedule_id": 2, "reference_at": REFERENCE, **overrides}
    with engine.connect() as conn:
        return coverage_report(conn, OBELISCO, CABILDO, **options)


def test_windows_count_city_and_corridor(engine):
    run_id = put_run(engine, ROWS)
    result = report(engine)
    assert result["current"]["data_run_id"] == run_id
    assert result["current"]["stations_by_age_days"]["7"] == {"caba": 2, "corridor": 1}
    assert result["current"]["stations_by_age_days"]["90"] == {"caba": 3, "corridor": 2}
    assert list(result["current"]["stations_by_age_days"]) == [str(d) for d in REPORT_WINDOWS_DAYS]


def test_report_shows_parameters_and_decision(engine):
    put_run(engine, ROWS)
    result = report(engine)
    assert result["parameters"] == {
        "max_price_age_days": coverage_rules.MAX_PRICE_AGE_DAYS,
        "min_recent_candidates": coverage_rules.MIN_RECENT_CANDIDATES,
        "max_detour_km": coverage_rules.MAX_DETOUR_KM,
    }
    # Una sola estación reciente en el corredor: se activa el escenario congelado.
    assert result["decision"]["status"] == "historical_scenario"
    assert result["decision"]["scenario"]["scenario_id"] == coverage_rules.HISTORICAL_SCENARIO_ID
    assert result["historical"]["eligible_in_corridor"] == 16
    json.dumps(result)


def test_report_without_ingestion(engine):
    result = report(engine)
    assert result["current"]["status"] == "no_successful_ingestion"
    assert result["current"]["stations_by_age_days"]["30"] == {"caba": 0, "corridor": 0}


def test_cli_prints_and_saves_report(tmp_path, monkeypatch, capsys):
    url = f"sqlite:///{tmp_path / 'cobertura.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    upgrade_to_head(url)
    engine = create_db_engine(url)
    put_run(engine, ROWS)
    engine.dispose()
    out = tmp_path / "reporte.json"
    # Las coordenadas negativas van con "=" para que argparse no las tome como opciones.
    argv = ["--origin=-34.6037,-58.3816", "--destination=-34.5627,-58.4565"]
    argv += ["--reference-at", REFERENCE.isoformat(), "--output", str(out)]
    assert main(argv) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed == json.loads(out.read_text(encoding="utf-8"))
    assert printed["query"]["destination"] == {"lat": -34.5627, "lon": -58.4565}


def test_cli_rejects_reference_without_timezone(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'c.db'}")
    argv = ["--origin=-34.6037,-58.3816", "--reference-at", "2026-10-24T18:00"]
    assert main(argv) == 2
    assert "zona horaria" in capsys.readouterr().err
