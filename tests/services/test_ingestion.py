"""Tests del ciclo de vida de una ejecución de ingesta."""

from datetime import datetime

import pytest

from nafta2go.persistence import repository as repo
from nafta2go.persistence.models import NormalizationResult, RawCapture
from nafta2go.services.ingestion import IngestionFailed, ingest

T0 = datetime(2026, 10, 24, 18, 0)


def fixed_clock():
    return T0


def capture(sha="b" * 64):
    return RawCapture(
        source="vigente",
        url="http://datos.energia.gob.ar/vigentes.csv",
        sha256=sha,
        size_bytes=9268946,
        stored_path="data/raw/vigente/captura.csv",
        fetched_at=T0,
        source_last_modified="2026-10-24T18:00:24",
    )


def price_row(schedule=2):
    return {
        "fila_origen": 10 + schedule,
        "idempresa": 9930,
        "empresa": "ESTACION SA",
        "empresabandera": "PUMA",
        "direccion": "VELEZ SARFIELD 522",
        "idproducto": 2,
        "tipo_nafta": "super",
        "idtipohorario": schedule,
        "precio": 2147,
        "fecha_vigencia": datetime(2026, 10, 23, 6, 0),
        "latitud": -34.640861,
        "longitud": -58.389601,
        "fecha_vigencia_original": "2026-10-23 06:00:00",
        "precio_original": "2147",
        "alertas": "",
    }


def rejection():
    return {"fila_origen": 40, "motivo": "precio_no_positivo", "precio": "0"}


def result(rows=None, rejections=None, report=None):
    rows = [price_row(2), price_row(3)] if rows is None else rows
    rejections = [rejection()] if rejections is None else rejections
    if report is None:
        report = {"filas_validas": len(rows), "filas_rechazadas": len(rejections)}
    return NormalizationResult(rows=rows, rejections=rejections, report=report, rules_version="1")


def normalizer_returning(value):
    return lambda _capture: value


def counts(engine, run_id):
    with engine.connect() as conn:
        return (
            len(repo.prices_for_run(conn, run_id)),
            len(repo.rejections_for_run(conn, run_id)),
        )


def test_successful_ingest_persists_everything(engine):
    run_id = ingest(engine, capture(), normalizer_returning(result()), clock=fixed_clock)
    with engine.connect() as conn:
        run = repo.get_run(conn, run_id)
        assert repo.find_run_by_sha256(conn, "vigente", "b" * 64) == run_id
    assert run["status"] == "succeeded"
    assert run["rules_version"] == "1"
    assert run["report"]["filas_validas"] == 2
    assert counts(engine, run_id) == (2, 1)


def test_normalizer_error_marks_run_failed_without_data(engine):
    def broken(_capture):
        raise ValueError("columna fecha_vigencia faltante")

    with pytest.raises(IngestionFailed) as exc:
        ingest(engine, capture(), broken, clock=fixed_clock)
    run_id = exc.value.run_id
    with engine.connect() as conn:
        run = repo.get_run(conn, run_id)
    assert run["status"] == "failed"
    assert "ValueError" in run["error"]
    assert "fecha_vigencia" in run["error"]
    assert run["finished_at"] == T0
    assert counts(engine, run_id) == (0, 0)
    assert isinstance(exc.value.__cause__, ValueError)


def test_database_error_mid_ingest_rolls_back(engine):
    duplicated = result(rows=[price_row(2), price_row(2)], rejections=[])
    with pytest.raises(IngestionFailed) as exc:
        ingest(engine, capture(), normalizer_returning(duplicated), clock=fixed_clock)
    run_id = exc.value.run_id
    with engine.connect() as conn:
        assert repo.get_run(conn, run_id)["status"] == "failed"
        assert repo.find_run_by_sha256(conn, "vigente", "b" * 64) is None
    assert counts(engine, run_id) == (0, 0)


def test_report_mismatch_fails_run(engine):
    inconsistent = result(report={"filas_validas": 10, "filas_rechazadas": 1})
    with pytest.raises(IngestionFailed, match="filas_validas"):
        ingest(engine, capture(), normalizer_returning(inconsistent), clock=fixed_clock)
    with engine.connect() as conn:
        assert repo.latest_successful_run(conn, "vigente") is None


def test_failed_ingest_does_not_change_latest_version(engine):
    first = ingest(engine, capture(), normalizer_returning(result()), clock=fixed_clock)

    def broken(_capture):
        raise RuntimeError("corte")

    with pytest.raises(IngestionFailed):
        ingest(engine, capture(sha="c" * 64), broken, clock=fixed_clock)
    with engine.connect() as conn:
        assert repo.latest_successful_run(conn, "vigente") == first


def test_reingesting_same_capture_links_previous_run(engine):
    first = ingest(engine, capture(), normalizer_returning(result()), clock=fixed_clock)
    second = ingest(engine, capture(), normalizer_returning(result()), clock=fixed_clock)
    with engine.connect() as conn:
        report = repo.get_run(conn, second)["report"]
    assert second != first
    assert report["duplicate_of_run_id"] == first


def test_report_is_not_mutated(engine):
    original = result()
    report_before = dict(original.report)
    ingest(engine, capture(), normalizer_returning(original), clock=fixed_clock)
    assert original.report == report_before
