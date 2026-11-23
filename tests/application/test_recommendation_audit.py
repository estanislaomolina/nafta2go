"""Recomendaciones sintéticas: la auditoría revisa lo persistido, no la calidad del ranking."""

import json
from copy import deepcopy
from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from nafta2go.application.recommendation_audit import (
    audit_recommendations,
    privacy_failures,
    stale_evaluations,
    traceability_failures,
)
from nafta2go.audit.__main__ import main
from nafta2go.persistence import repository as repo

SCENARIO = {
    "scenario_id": "vigente-2026-10-24",
    "reference_at": "2026-10-24T18:00:00-03:00",
    "extract_sha256": "a" * 64,
    "source_sha256": "b" * 64,
}


def evaluation(published, source_row=1):
    return {"station_id": "1", "published_at_local": published, "source_row": source_row}


def record(**changes):
    base = {
        "id": 1,
        "data_run_id": None,
        "data_run_status": None,
        "scenario": deepcopy(SCENARIO),
        "engine_version": "mvp-02-v2",
        "routing_provider": "openrouteservice",
        "request": {"fuel_type": "super", "max_price_age_days": 30},
        "result": {
            "data_run_id": None,
            "scenario": deepcopy(SCENARIO),
            "engine_version": "mvp-02-v2",
            "routing_provider": "openrouteservice",
            "price_reference_at": "2026-10-24T21:00:00+00:00",
            "query": {"max_price_age_days": 30},
            "routes": {"replayed": True, "sha256": "c" * 64},
            "evaluations": [evaluation("2026-10-13T06:00:00"), evaluation("2026-09-24T18:00:00")],
        },
    }
    return base | changes


def test_a_complete_record_passes_every_check():
    report = audit_recommendations([record()])
    assert report["origins"] == {"ingesta_vigente": 0, "escenario_historico": 1}
    for name in ("trazabilidad", "privacidad"):
        assert report[name] == {"cumplen": 1, "total": 1, "proporcion": 1.0}
    assert report["frescura"]["cumplen"] == report["frescura"]["total"] == 2
    assert report["fallas"] == {"trazabilidad": {}, "frescura": {}, "privacidad": {}}


def test_exactly_thirty_days_is_fresh_and_one_minute_more_is_not():
    current = record()
    current["result"]["evaluations"] = [
        evaluation("2026-09-24T18:00:00"),
        evaluation("2026-09-24T17:59:00"),
        evaluation("2026-10-25T09:00:00"),
    ]
    assert stale_evaluations(current) == (3, 2)
    report = audit_recommendations([current])
    assert report["frescura"]["cumplen"] == 1 and report["fallas"]["frescura"] == {"1": 2}


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"data_run_id": 4, "data_run_status": "succeeded"}, "origen_no_unico"),
        ({"scenario": None}, "origen_no_unico"),
        ({"scenario": None, "data_run_id": 4, "data_run_status": "failed"}, "ingesta_no_exitosa"),
        ({"scenario": SCENARIO | {"source_sha256": "x"}}, "escenario_incompleto"),
        ({"scenario": SCENARIO | {"reference_at": "2026-10-24T18:00:00"}}, "escenario_incompleto"),
        ({"scenario": SCENARIO | {"reference_at": "ayer"}}, "escenario_incompleto"),
        ({"scenario": SCENARIO | {"scenario_id": " "}}, "escenario_incompleto"),
        ({"engine_version": "otra"}, "engine_version_inconsistente"),
        ({"routing_provider": ""}, "routing_provider_inconsistente"),
    ],
)
def test_traceability_failures_are_named(changes, reason):
    assert reason in traceability_failures(record(**changes))
    report = audit_recommendations([record(**changes)])
    assert (
        report["trazabilidad"]["cumplen"] == 0 and reason in report["fallas"]["trazabilidad"]["1"]
    )


def test_a_result_with_another_origin_than_its_columns_is_not_traceable():
    current = record()
    current["result"]["scenario"] = None
    assert traceability_failures(current) == ["origen_inconsistente"]
    current = record(data_run_id=4, data_run_status="succeeded", scenario=None)
    current["result"] |= {"data_run_id": 5, "scenario": None}
    assert traceability_failures(current) == ["origen_inconsistente"]
    current["result"]["data_run_id"] = 4
    assert traceability_failures(current) == []
    del current["result"]["data_run_id"]
    assert traceability_failures(current) == ["origen_inconsistente"]


@pytest.mark.parametrize("days", [31, 0, "30", True])
def test_a_stored_age_threshold_out_of_range_fails_and_does_not_widen_freshness(days):
    current = record()
    current["result"]["query"]["max_price_age_days"] = days
    current["result"]["evaluations"] = [evaluation("2026-09-20T18:00:00")]
    assert traceability_failures(current) == ["vigencia_fuera_de_rango"]
    assert stale_evaluations(current) == (1, 1)


def test_an_incomplete_row_is_reported_without_stopping_the_audit():
    incomplete = record(id=7)
    del incomplete["result"]["price_reference_at"]
    without_query = record(id=8)
    del without_query["result"]["query"]
    report = audit_recommendations(iter([incomplete, record(id=9), without_query]))
    assert report["recommendations"] == 3
    assert report["fallas"]["trazabilidad"] == {"7": ["fila_incompleta"], "8": ["fila_incompleta"]}
    assert report["frescura"]["total"] == 2 and report["privacidad"]["cumplen"] == 3


def test_prices_without_source_row_and_unhashed_replays_are_not_traceable():
    current = record()
    current["result"]["evaluations"][0]["source_row"] = None
    current["result"]["routes"]["sha256"] = None
    assert traceability_failures(current) == [
        "precio_sin_fila_de_origen",
        "matriz_reproducida_sin_hash",
    ]
    live = record()
    live["result"]["routes"] = {"replayed": False, "cache_hit": True}
    assert traceability_failures(live) == []


def test_locations_and_map_links_anywhere_are_privacy_failures():
    current = record()
    current["request"]["origin"] = "-34.60,-58.38"
    current["result"]["evaluations"][0]["navigation"] = {
        "url": "https://www.google.com/maps/dir/?api=1&destination=-34.5,-58.4"
    }
    assert privacy_failures(current) == ["request_con_ubicacion", "result_con_enlace_de_mapas"]
    nested = record()
    nested["result"]["query"]["Destino"] = [1, 2]
    assert privacy_failures(nested) == ["result_con_ubicacion"]
    similar = record()
    similar["request"] |= {"has_destination": True, "origin_type": "manual"}
    assert privacy_failures(similar) == []
    report = audit_recommendations([current, record(id=2)])
    assert report["privacidad"] == {"cumplen": 1, "total": 2, "proporcion": 0.5}
    assert list(report["fallas"]["privacidad"]) == ["1"]


@pytest.mark.parametrize(
    "value",
    [
        {"from": {"lat": 1, "lon": 2}},
        {"from": [-34.6, -58.4]},
        {"punto": ["-58.4", "-34.6"]},
        {"nota": "salida en -34.6037, -58.3816"},
    ],
)
def test_coordinates_under_other_keys_are_privacy_failures(value):
    current = record()
    current["request"] |= value
    assert privacy_failures(current) == ["request_con_ubicacion"]


def test_number_pairs_outside_caba_are_not_locations():
    current = record()
    current["request"] |= {"rango": [10, 20], "nota": "30, 120 días", "par": ["a", "b"]}
    assert privacy_failures(current) == []


def test_an_empty_history_reports_no_proportion():
    report = audit_recommendations([])
    assert report["trazabilidad"]["proporcion"] is None
    assert report["frescura"]["total"] == 0


def store(engine):
    current = record()
    with engine.begin() as conn:
        return repo.record_recommendation(
            conn,
            None,
            current["engine_version"],
            current["routing_provider"],
            current["request"],
            current["result"],
            datetime(2026, 10, 24, 21, tzinfo=UTC),
            scenario=current["scenario"],
        )


def test_cli_reads_the_database_and_exits_by_result(engine, database_url, monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", database_url)
    recommendation_id = store(engine)
    assert main([]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["recommendations"] == 1 and report["privacidad"]["proporcion"] == 1.0
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE recommendations SET request = :request WHERE id = :id"),
            {"request": json.dumps({"origin": [-34.6, -58.4]}), "id": recommendation_id},
        )
    assert main([]) == 1
    assert json.loads(capsys.readouterr().out)["fallas"]["privacidad"] == {
        str(recommendation_id): ["request_con_ubicacion"]
    }


def test_cli_reports_an_unmigrated_database_as_an_error(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'vacia.db'}")
    assert main([]) == 2
    assert json.loads(capsys.readouterr().out) == {
        "status": "audit_error",
        "error_type": "OperationalError",
    }
