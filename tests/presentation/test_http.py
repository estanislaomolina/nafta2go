"""Contrato HTTP con SQLite migrado y rutas grabadas: ninguna prueba usa red."""

from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from nafta2go.adapters.recorded_routes import CapturedRoutes, RecordedRoutes
from nafta2go.adapters.routing import (
    InvalidCredentials,
    ProviderTimeout,
    ProviderUnavailable,
    QuotaExceeded,
    RoutingError,
)
from nafta2go.application.scenario import ScenarioIntegrityError, load_scenario
from nafta2go.persistence import repository as repo
from nafta2go.persistence.database import create_db_engine, upgrade_to_head
from nafta2go.persistence.schema import recommendations, station_prices
from nafta2go.presentation.http import create_app

MATRIX = Path(__file__).resolve().parents[2] / "docs/evidencia/poc-05-flujo-2026-10-26/matrix.json"
AUTH = {"Authorization": "Bearer token-local-de-prueba"}
BODY = {
    "origin": {"lat": -34.6037, "lon": -58.3816},
    "destination": {"lat": -34.5627, "lon": -58.4565},
    "fuel_type": "super",
    "consumption_l_per_100km": "10",
    "tank_capacity_l": "50",
    "remaining_l": "10",
    "budget_ars": "12000",
    "reserve_l": "2",
}


@pytest.fixture
def clients(engine, monkeypatch):
    monkeypatch.setenv("NAFTA2GO_API_TOKEN", "token-local-de-prueba")

    @contextmanager
    def open_client(**options):
        config = {
            "engine": engine,
            "provider_factory": lambda: RecordedRoutes(MATRIX),
            "clock": lambda: datetime(2026, 10, 26, 12, tzinfo=UTC),
            "routing_provider": "openrouteservice-recorded",
            **options,
        }
        with TestClient(create_app(**config)) as client:
            yield client

    return open_client


def test_full_http_flow_is_explained_and_persisted_without_user_coordinates(clients, engine):
    with clients() as client:
        response = client.post("/api/v1/recommendations", json=BODY, headers=AUTH)
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "historical_scenario" and payload["scenario"]
    assert payload["outcome"] == "recommended"
    assert len(payload["evaluations"]) == 10
    assert payload["routes"]["replayed"]
    with engine.connect() as conn:
        saved = repo.get_recommendation(conn, payload["recommendation_id"])
    assert not {"origin", "destination", "lat", "lon"} & set(saved["request"])
    assert "-34.6037" not in str(saved) and "-58.4565" not in str(saved)


def test_current_data_response_refers_to_its_ingestion(clients, engine):
    now = datetime(2026, 10, 26, 12)
    with engine.begin() as conn:
        run_id = repo.start_run(conn, "vigente", now)
        conn.execute(
            station_prices.insert(),
            [{**row, "id": None, "run_id": run_id} for row in load_scenario().rows],
        )
        repo.finish_run(conn, run_id, "succeeded", now)
    with clients() as client:
        response = client.post("/api/v1/recommendations", json=BODY, headers=AUTH)
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready" and payload["scenario"] is None
    assert payload["data_run_id"] == run_id


def test_infeasible_query_returns_an_explained_result(clients):
    with clients() as client:
        response = client.post(
            "/api/v1/recommendations", json={**BODY, "remaining_l": "0"}, headers=AUTH
        )
    assert response.status_code == 200
    assert response.json()["outcome"] == "no_feasible_stations"
    assert response.json()["alternatives"] == []


@pytest.mark.parametrize("authorization", [None, "Bearer incorrecto", "Basic incorrecto"])
def test_unauthorized_queries_do_not_load_routes(clients, authorization):
    def forbidden():
        pytest.fail("No se deben cargar rutas sin autorización")

    headers = {} if authorization is None else {"Authorization": authorization}
    with clients(provider_factory=forbidden) as client:
        response = client.post("/api/v1/recommendations", json=BODY, headers=headers)
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_missing_api_token_fails_closed(clients, monkeypatch):
    monkeypatch.delenv("NAFTA2GO_API_TOKEN")
    with clients() as client:
        assert client.post("/api/v1/recommendations", json=BODY, headers=AUTH).status_code == 503
        assert client.get("/ready").status_code == 503


@pytest.mark.parametrize(
    "changes",
    [
        {"remaining_l": "51"},
        {"reserve_l": "60"},
        {"consumption_l_per_100km": True},
        {"consumption_l_per_100km": "0"},
        {"budget_ars": "NaN"},
        {"budget_ars": None},
        {"origin": {"lat": "-34.6037", "lon": -58.3816}},
        {"origin": {"lat": 0, "lon": 0}},
        {"fuel_type": "diesel"},
        {"schedule_id": 2.0},
        {"reference_at": "2020-01-01T00:00:00Z"},
        {"matrix_file": "/etc/passwd"},
    ],
)
def test_invalid_inputs_return_safe_422(clients, changes):
    with clients() as client:
        response = client.post("/api/v1/recommendations", json={**BODY, **changes}, headers=AUTH)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_request"
    assert "-34.6037" not in response.text


def test_missing_fields_and_malformed_json_have_safe_validation_errors(clients):
    with clients() as client:
        missing = client.post("/api/v1/recommendations", json={}, headers=AUTH)
        malformed = client.post(
            "/api/v1/recommendations",
            content='{"origin": secreto',
            headers={**AUTH, "Content-Type": "application/json"},
        )
    assert missing.status_code == malformed.status_code == 422
    assert missing.json()["detail"]["errors"][0]["message"] == "Campo obligatorio"
    assert "secreto" not in malformed.text


@pytest.mark.parametrize(
    "error,status,code",
    [
        (ProviderTimeout("secreto"), 504, "routes_timeout"),
        (QuotaExceeded("secreto"), 503, "routes_quota_exceeded"),
        (InvalidCredentials("secreto"), 503, "routes_not_configured"),
        (ProviderUnavailable("secreto"), 502, "routes_unavailable"),
        (RoutingError("secreto"), 502, "routes_unavailable"),
        (SQLAlchemyError("secreto"), 503, "data_unavailable"),
        (ScenarioIntegrityError("secreto"), 503, "data_unavailable"),
        (OSError("secreto"), 503, "data_unavailable"),
    ],
)
def test_dependency_errors_rollback_and_hide_details(clients, engine, error, status, code, caplog):
    class Failing:
        def matrix(self, sources, destinations):
            raise error

    with clients(provider_factory=Failing) as client:
        response = client.post("/api/v1/recommendations", json=BODY, headers=AUTH)
    assert response.status_code == status
    assert response.json()["detail"]["code"] == code
    assert "secreto" not in response.text + caplog.text
    assert "-34.6037" not in caplog.text
    with engine.connect() as conn:
        assert conn.execute(select(func.count()).select_from(recommendations)).scalar() == 0


def test_no_coverage_needs_no_provider_key(clients, monkeypatch):
    monkeypatch.delenv("ORS_API_KEY", raising=False)
    with clients(provider_factory=CapturedRoutes) as client:
        response = client.post(
            "/api/v1/recommendations",
            json={**BODY, "origin": {"lat": -34.71, "lon": -58.33}, "destination": None},
            headers=AUTH,
        )
    assert response.status_code == 200
    assert response.json()["outcome"] == "insufficient_coverage"
    assert response.json()["recommendation_id"] is None


def test_liveness_and_readiness_do_not_migrate_the_database(clients, tmp_path):
    url = f"sqlite:///{tmp_path / 'empty.db'}"
    db = create_db_engine(url)
    try:
        with clients(engine=db) as client:
            assert client.get("/health").json() == {"status": "ok"}
            assert client.get("/ready").status_code == 503
            upgrade_to_head(url)
            assert client.get("/ready").status_code == 200
            schema = client.get("/openapi.json").json()
            endpoint = schema["paths"]["/api/v1/recommendations"]["post"]
            assert endpoint["security"]
            assert endpoint["responses"]["422"]["content"]["application/json"]["schema"][
                "$ref"
            ].endswith("/ErrorOutput")
    finally:
        db.dispose()


def test_readiness_detects_an_unreadable_database(clients, tmp_path):
    path = tmp_path / "broken.db"
    path.write_text("archivo que no es SQLite")
    db = create_db_engine(f"sqlite:///{path}")
    try:
        with clients(engine=db) as client:
            assert client.get("/health").status_code == 200
            assert client.get("/ready").status_code == 503
    finally:
        db.dispose()


def test_application_owns_its_default_engine_lifecycle(clients, database_url, monkeypatch):
    from unittest.mock import Mock

    owned = create_db_engine(database_url)
    dispose = Mock(wraps=owned.dispose)
    monkeypatch.setattr(owned, "dispose", dispose)
    monkeypatch.setattr("nafta2go.presentation.http.create_db_engine", lambda: owned)
    with clients(engine=None) as client:
        assert client.get("/ready").status_code == 200
    dispose.assert_called_once()
