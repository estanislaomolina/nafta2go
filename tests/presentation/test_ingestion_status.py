"""Estado administrativo de ingesta con datos temporales y sin servicios externos."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select

from nafta2go.application.ingestion_status import ingestion_status
from nafta2go.application.scenario import load_scenario
from nafta2go.persistence import repository as repo
from nafta2go.persistence.models import RawCapture
from nafta2go.persistence.schema import ingestion_alerts, ingestion_runs, station_prices
from nafta2go.presentation.http import create_app

NOW = datetime(2026, 11, 13, 11, tzinfo=UTC)
AUTH = {"Authorization": "Bearer token-administrativo"}
URL = "/api/v1/operations/ingestion"


@pytest.fixture
def client(engine, monkeypatch):
    monkeypatch.setenv("NAFTA2GO_API_TOKEN", "token-administrativo")
    with TestClient(create_app(engine, clock=lambda: NOW)) as client:
        yield client


def add_run(engine, status="succeeded", source="vigente", hours=1):
    start = (NOW - timedelta(hours=hours)).replace(tzinfo=None)
    with engine.begin() as conn:
        run_id = repo.start_run(conn, source, start)
        if status != "running":
            repo.finish_run(
                conn,
                run_id,
                status,
                start + timedelta(seconds=60),
                report={"privado": "secreto-reporte"},
                error="secreto-error",
                rules_version="test-v1",
            )
        return run_id


def test_empty_state_is_protected_read_only_and_explicit(client, engine):
    assert client.get(URL).status_code == 401
    assert client.get(URL, headers={"Authorization": "Bearer incorrecto"}).status_code == 401
    response = client.get(URL, headers=AUTH)
    state = response.json()
    assert response.headers["cache-control"] == "no-store"
    assert state["source"] == "vigente" and state["observed_at"] == NOW.isoformat()
    assert state["status"] == "alerting"
    assert state["latest_attempt"] is state["latest_successful"] is None
    assert [item["kind"] for item in state["conditions"]] == ["missing"]
    with engine.connect() as conn:
        assert conn.execute(select(ingestion_alerts)).all() == []
        assert conn.execute(select(ingestion_runs)).all() == []


def test_failure_keeps_last_successful_version_without_private_columns(client, engine):
    good = add_run(engine, hours=2)
    failed = add_run(engine, status="failed")
    rows = load_scenario().rows[:3]
    with engine.begin() as conn:
        repo.add_raw_capture(
            conn,
            good,
            RawCapture(
                "vigente",
                "https://example.invalid/secreto-url",
                "a" * 64,
                1234,
                "/secreto-archivo.csv",
                NOW.replace(tzinfo=None),
            ),
        )
        conn.execute(station_prices.insert(), [{**row, "run_id": good} for row in rows])
        repo.add_rejections(
            conn, good, [{"fila_origen": 99, "motivo": "fecha", "raw": "secreto-crudo"}]
        )
    statements = []

    def capture_sql(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.lower())

    event.listen(engine, "before_cursor_execute", capture_sql)
    try:
        state = client.get(URL, headers=AUTH).json()
    finally:
        event.remove(engine, "before_cursor_execute", capture_sql)
    assert state["status"] == "alerting"
    assert state["latest_attempt"]["id"] == failed
    version = state["latest_successful"]
    assert version["id"] == good and version["duration_seconds"] == 60
    assert version["started_at"].endswith("+00:00")
    assert version["rules_version"] == "test-v1"
    assert version["sha256"] == "a" * 64 and version["size_bytes"] == 1234
    assert version["price_rows"] == 3 and version["rejected_rows"] == 1
    assert version["stations"] == len({row["station_id"] for row in rows})
    assert state["conditions"] == [{"key": f"failed:{failed}", "kind": "failed", "run_id": failed}]
    assert "secreto" not in str(state)
    for statement in statements:
        assert statement.lstrip().startswith("select")
        assert not any(
            column in statement
            for column in (".error", ".report", ".url", ".stored_path", ".lat", ".lon", ".raw")
        )


def test_status_does_not_update_persisted_monitor_alerts(client, engine):
    from nafta2go.application.ingestion_monitor import check_ingestion

    check_ingestion(engine, "vigente", NOW - timedelta(minutes=5))
    with engine.connect() as conn:
        before = conn.execute(select(ingestion_alerts)).all()
    run_id = add_run(engine)
    state = client.get(URL, headers=AUTH).json()
    assert state["status"] == "healthy" and not state["conditions"]
    assert state["latest_successful"]["id"] == run_id
    with engine.connect() as conn:
        assert conn.execute(select(ingestion_alerts)).all() == before


def test_stalled_attempt_and_source_isolation(client, engine):
    historical = add_run(engine, source="historico")
    running = add_run(engine, status="running", hours=2)
    current = client.get(URL, headers=AUTH).json()
    assert current["latest_attempt"]["id"] == running
    assert current["latest_attempt"]["finished_at"] is None
    assert current["latest_attempt"]["duration_seconds"] == 7200
    assert [item["kind"] for item in current["conditions"]] == ["stalled"]
    assert current["latest_successful"] is None
    history = client.get(URL, params={"source": "historico"}, headers=AUTH).json()
    assert history["status"] == "healthy"
    assert history["latest_attempt"]["id"] == historical
    invalid = client.get(URL, params={"source": "secreto-no-permitido"}, headers=AUTH)
    assert invalid.status_code == 422 and "secreto" not in invalid.text


def test_many_stalled_conditions_have_an_explicit_response_limit(client, engine):
    for _ in range(21):
        add_run(engine, status="running", hours=2)
    state = client.get(URL, headers=AUTH).json()
    assert state["condition_count"] == 21 and state["conditions_truncated"]
    assert len(state["conditions"]) == 20


@pytest.mark.parametrize("source,now", [("otro", NOW), ("vigente", NOW.replace(tzinfo=None))])
def test_application_rejects_unknown_source_or_naive_clock(engine, source, now):
    with pytest.raises(ValueError, match="zona"):
        ingestion_status(engine, source, now)


def test_missing_token_fails_closed(client, monkeypatch):
    monkeypatch.delenv("NAFTA2GO_API_TOKEN")
    response = client.get(URL, headers=AUTH)
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "api_not_configured"


def test_missing_schema_returns_safe_error(tmp_path, monkeypatch, caplog):
    from nafta2go.persistence.database import create_db_engine

    monkeypatch.setenv("NAFTA2GO_API_TOKEN", "token-administrativo")
    engine = create_db_engine(f"sqlite:///{tmp_path / 'secreto-base.db'}")
    try:
        with TestClient(create_app(engine, clock=lambda: NOW)) as client:
            response = client.get(URL, headers=AUTH)
        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "data_unavailable"
        assert "secreto" not in response.text + caplog.text
    finally:
        engine.dispose()
