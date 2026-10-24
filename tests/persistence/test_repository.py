"""Tests de los repositorios contra un SQLite migrado."""

from datetime import datetime
from decimal import Decimal

import pytest

from nafta2go.persistence import repository as repo
from nafta2go.persistence.models import RawCapture

T0 = datetime(2026, 10, 24, 18, 0)


def price_row(**overrides):
    row = {
        "fila_origen": 12,
        "idempresa": 9930,
        "empresa": "ESTACION SA",
        "empresabandera": "PUMA",
        "direccion": "VELEZ SARFIELD 522",
        "idproducto": 2,
        "tipo_nafta": "super",
        "idtipohorario": 2,
        "precio": 45.67,
        "fecha_vigencia": datetime(2026, 10, 23, 6, 0),
        "latitud": -34.640861,
        "longitud": -58.389601,
        "fecha_vigencia_original": "23/10/2026 06:00",
        "precio_original": "45.67",
        "alertas": "",
    }
    return row | overrides


def capture(**overrides):
    values = {
        "source": "vigente",
        "url": "http://datos.energia.gob.ar/x.csv",
        "sha256": "a" * 64,
        "size_bytes": 9268946,
        "stored_path": "data/raw/vigente/x.csv",
        "fetched_at": T0,
        "source_last_modified": "2026-10-24T18:00:24",
    }
    return RawCapture(**(values | overrides))


def succeeded_run(conn, source="vigente", started_at=T0):
    run_id = repo.start_run(conn, source, started_at)
    repo.finish_run(conn, run_id, "succeeded", started_at, report={}, rules_version="1")
    return run_id


def test_start_and_finish_run(engine):
    with engine.begin() as conn:
        run_id = repo.start_run(conn, "vigente", T0)
        assert repo.get_run(conn, run_id)["status"] == "running"
        repo.finish_run(conn, run_id, "succeeded", T0, report={"filas": 1}, rules_version="1")
        run = repo.get_run(conn, run_id)
    assert run["status"] == "succeeded"
    assert run["report"] == {"filas": 1}
    assert run["rules_version"] == "1"
    assert run["finished_at"] == T0


def test_start_run_rejects_unknown_source(engine):
    with pytest.raises(ValueError, match="source"), engine.begin() as conn:
        repo.start_run(conn, "otro", T0)


def test_raw_capture_is_stored_and_found_by_sha(engine):
    with engine.begin() as conn:
        run_id = succeeded_run(conn)
        repo.add_raw_capture(conn, run_id, capture())
        assert repo.find_run_by_sha256(conn, "vigente", "a" * 64) == run_id
        assert repo.find_run_by_sha256(conn, "historico", "a" * 64) is None


def test_prices_round_trip_as_decimal(engine):
    with engine.begin() as conn:
        run_id = succeeded_run(conn)
        repo.add_prices(conn, run_id, [price_row(precio=45.67), price_row(idtipohorario=3)])
        prices = repo.prices_for_run(conn, run_id)
    assert prices[0]["price"] == Decimal("45.670")
    assert isinstance(prices[0]["price"], Decimal)


def test_add_prices_keeps_original_values(engine):
    with engine.begin() as conn:
        run_id = succeeded_run(conn)
        inserted = repo.add_prices(conn, run_id, [price_row()])
        stored = repo.prices_for_run(conn, run_id)[0]
    assert inserted == 1
    assert stored["source_row"] == 12
    assert stored["valid_from_raw"] == "23/10/2026 06:00"
    assert stored["price_raw"] == "45.67"
    assert stored["station_id"] == 9930
    assert stored["fuel_type"] == "super"


def test_prices_for_run_filters_fuel_type(engine):
    with engine.begin() as conn:
        run_id = succeeded_run(conn)
        repo.add_prices(conn, run_id, [price_row(), price_row(idproducto=3, tipo_nafta="premium")])
        premium = repo.prices_for_run(conn, run_id, fuel_type="premium")
    assert [p["fuel_type"] for p in premium] == ["premium"]


def test_missing_coordinates_are_stored_as_null(engine):
    with engine.begin() as conn:
        run_id = succeeded_run(conn)
        repo.add_prices(conn, run_id, [price_row(latitud=None, longitud=float("nan"))])
        stored = repo.prices_for_run(conn, run_id)[0]
    assert stored["lat"] is None and stored["lon"] is None


def test_rejections_keep_reason_and_raw_row(engine):
    raw = {"fila_origen": 7, "motivo": "fecha_futura", "fecha_vigencia": "01/01/2044 00:00"}
    with engine.begin() as conn:
        run_id = succeeded_run(conn)
        assert repo.add_rejections(conn, run_id, [raw]) == 1
        stored = repo.rejections_for_run(conn, run_id)[0]
    assert stored["source_row"] == 7
    assert stored["reason"] == "fecha_futura"
    assert stored["raw"] == {"fecha_vigencia": "01/01/2044 00:00"}


def test_latest_successful_run_ignores_failed(engine):
    with engine.begin() as conn:
        ok = succeeded_run(conn)
        failed = repo.start_run(conn, "vigente", T0)
        repo.finish_run(conn, failed, "failed", T0, error="ValueError: x")
        assert repo.latest_successful_run(conn, "vigente") == ok


def test_running_runs_are_not_data_versions(engine):
    with engine.begin() as conn:
        repo.start_run(conn, "vigente", T0)
        assert repo.latest_successful_run(conn, "vigente") is None


def test_latest_successful_run_is_per_source(engine):
    with engine.begin() as conn:
        vigente = succeeded_run(conn, "vigente")
        historico = succeeded_run(conn, "historico")
        assert repo.latest_successful_run(conn, "vigente") == vigente
        assert repo.latest_successful_run(conn, "historico") == historico


def test_recommendation_links_data_run(engine):
    with engine.begin() as conn:
        run_id = succeeded_run(conn)
        rec_id = repo.record_recommendation(
            conn,
            data_run_id=run_id,
            engine_version="poc-04",
            routing_provider="openrouteservice",
            request={"fuel_type": "super", "budget_ars": "20000"},
            result={"alternatives": []},
            created_at=T0,
        )
        stored = repo.get_recommendation(conn, rec_id)
    assert stored["data_run_id"] == run_id
    assert stored["request"] == {"fuel_type": "super", "budget_ars": "20000"}


@pytest.mark.parametrize("field", ["origin", "destination", "lat", "lon"])
def test_recommendation_rejects_location_fields(engine, field):
    with pytest.raises(ValueError, match=field), engine.begin() as conn:
        run_id = succeeded_run(conn)
        repo.record_recommendation(
            conn,
            data_run_id=run_id,
            engine_version="poc-04",
            routing_provider="openrouteservice",
            request={"fuel_type": "super", field: "-34.6"},
            result={},
            created_at=T0,
        )


def test_recommendation_requires_succeeded_run(engine):
    with pytest.raises(ValueError, match="succeeded"), engine.begin() as conn:
        failed = repo.start_run(conn, "vigente", T0)
        repo.finish_run(conn, failed, "failed", T0, error="x")
        repo.record_recommendation(
            conn,
            data_run_id=failed,
            engine_version="poc-04",
            routing_provider="openrouteservice",
            request={},
            result={},
            created_at=T0,
        )


def test_rejection_raw_values_are_made_json_safe(engine):
    raw = {
        "fila_origen": 8,
        "motivo": "precio_invalido",
        "precio": float("nan"),
        "fecha": datetime(2026, 10, 1, 9, 30),
        "monto": Decimal("12.5"),
    }
    with engine.begin() as conn:
        run_id = succeeded_run(conn)
        repo.add_rejections(conn, run_id, [raw])
        stored = repo.rejections_for_run(conn, run_id)[0]["raw"]
    assert stored == {"precio": None, "fecha": "2026-10-01 09:30:00", "monto": "12.5"}
