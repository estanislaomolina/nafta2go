"""Detección y recuperación de alertas con reloj controlado y migraciones reales."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from nafta2go.application.ingestion_monitor import check_ingestion
from nafta2go.domain.ingestion_health import detect_alerts
from nafta2go.persistence import repository as repo
from nafta2go.persistence.schema import ingestion_alerts

NOW = datetime(2026, 11, 9, 11, tzinfo=UTC)  # 08:00 de Argentina.


def add_run(engine, started_at, status="succeeded", source="vigente", duration=1):
    with engine.begin() as conn:
        run_id = repo.start_run(conn, source, started_at.replace(tzinfo=None))
        if status != "running":
            repo.finish_run(
                conn,
                run_id,
                status,
                (started_at + timedelta(minutes=duration)).replace(tzinfo=None),
            )
    return run_id


def test_empty_database_alerts_with_detection_timestamp(engine):
    summary = check_ingestion(engine, "vigente", NOW)
    assert summary["status"] == "alerting"
    alert = summary["alerts"][0]
    assert alert["kind"] == "missing"
    assert alert["run_id"] is None
    assert alert["detected_at"] == NOW.isoformat()


@pytest.mark.parametrize("minutes,missing", [(-1, False), (0, True), (1, True)])
def test_daily_grace_period_uses_argentina_timezone(engine, minutes, missing):
    add_run(engine, NOW - timedelta(days=1, hours=2))
    summary = check_ingestion(engine, "vigente", NOW + timedelta(minutes=minutes))
    assert bool(summary["alerts"]) == missing


def test_previous_day_is_checked_before_scheduled_time(engine):
    add_run(engine, NOW - timedelta(days=2, hours=2))
    summary = check_ingestion(engine, "vigente", NOW - timedelta(hours=3))
    assert summary["alerts"][0]["key"] == "vigente:missing:2026-11-08"


def test_running_at_timeout_boundary_alerts_without_rewriting_status(engine):
    run_id = add_run(engine, NOW - timedelta(hours=2), status="running")
    summary = check_ingestion(engine, "vigente", NOW)
    assert [(a["kind"], a["run_id"]) for a in summary["alerts"]] == [("stalled", run_id)]
    with engine.connect() as conn:
        assert repo.get_run(conn, run_id)["status"] == "running"


def test_recent_running_ingestion_is_not_stalled(engine):
    add_run(engine, NOW - timedelta(hours=1), status="running")
    assert check_ingestion(engine, "vigente", NOW)["status"] == "healthy"


def test_failed_run_is_detected_even_if_retry_is_running(engine):
    failed = add_run(engine, NOW - timedelta(hours=1), status="failed")
    add_run(engine, NOW - timedelta(minutes=5), status="running")
    summary = check_ingestion(engine, "vigente", NOW)
    assert [(a["kind"], a["run_id"]) for a in summary["alerts"]] == [("failed", failed)]


@pytest.mark.parametrize("status", [None, "failed", "running"])
def test_repeated_checks_preserve_first_detection_and_recovery(engine, status):
    run_id = None
    if status:
        run_id = add_run(engine, NOW - timedelta(hours=2), status=status)
    first = check_ingestion(engine, "vigente", NOW)["alerts"][0]
    later = NOW + timedelta(minutes=10)
    second = check_ingestion(engine, "vigente", later)["alerts"][0]
    assert first["detected_at"] == second["detected_at"]
    assert second["last_seen_at"] == later.isoformat()
    if status == "running":
        with engine.begin() as conn:
            repo.finish_run(conn, run_id, "failed", later.replace(tzinfo=None))
    add_run(engine, later)
    recovered_at = later + timedelta(minutes=2)
    assert check_ingestion(engine, "vigente", recovered_at)["status"] == "healthy"
    with engine.connect() as conn:
        rows = conn.execute(select(ingestion_alerts)).mappings().all()
    assert len(rows) == 1
    assert rows[0]["run_id"] == run_id
    assert rows[0]["resolved_at"] == recovered_at.replace(tzinfo=None)


def test_success_does_not_hide_an_older_stalled_run(engine):
    old = add_run(engine, NOW - timedelta(days=1), status="running")
    add_run(engine, NOW - timedelta(minutes=10))
    alerts = check_ingestion(engine, "vigente", NOW)["alerts"]
    assert [(a["kind"], a["run_id"]) for a in alerts] == [("stalled", old)]


def test_sources_are_isolated_and_unknown_source_is_rejected(engine):
    add_run(engine, NOW - timedelta(minutes=10), source="historico")
    assert check_ingestion(engine, "vigente", NOW)["status"] == "alerting"
    assert check_ingestion(engine, "historico", NOW)["status"] == "healthy"
    with pytest.raises(ValueError, match="Origen"):
        check_ingestion(engine, "otro", NOW)


def test_naive_clock_is_rejected():
    with pytest.raises(ValueError, match="zona"):
        detect_alerts([], NOW.replace(tzinfo=None))
