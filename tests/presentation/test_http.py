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
    assert payload["navigation"]


def test_infeasible_query_returns_an_explained_result(clients):
    with clients() as client:
        response = client.post(
            "/api/v1/recommendations", json={**BODY, "remaining_l": "0"}, headers=AUTH
        )
    assert response.status_code == 200
    assert response.json()["outcome"] == "no_feasible_stations"
    assert response.json()["alternatives"] == []
    assert response.json()["navigation"] == []


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
        assert client.get("/api/v1/operations").status_code == 503


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
    assert response.json()["navigation"] == []


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


def test_navigation_uses_station_coordinates_without_persisting_links(clients, engine, caplog):
    import json
    from urllib.parse import parse_qs, urlsplit

    with clients() as client:
        response = client.post("/api/v1/recommendations", json=BODY, headers=AUTH)
    assert response.status_code == 200
    payload = response.json()
    stations = {str(row["station_id"]): (row["lat"], row["lon"]) for row in load_scenario().rows}
    assert {link["station_id"] for link in payload["navigation"]} == {
        row["station_id"] for row in payload["alternatives"]
    }
    assert payload["navigation_notice"]
    assert "navigation_destinations" not in payload
    for link in payload["navigation"]:
        query = parse_qs(urlsplit(link["url"]).query)
        assert tuple(map(float, query["destination"][0].split(","))) == stations[link["station_id"]]
        assert not {"origin", "waypoints", "key"} & query.keys()
    with engine.connect() as conn:
        saved = repo.get_recommendation(conn, payload["recommendation_id"])
    encoded = json.dumps(saved, default=str)
    assert "google.com/maps" not in encoded and "navigation_destinations" not in encoded
    assert "-34.6037" not in encoded and "-58.4565" not in encoded
    assert "google.com/maps" not in caplog.text


@pytest.mark.parametrize("limit", [3, 20])
def test_http_accepts_and_propagates_candidate_limit(clients, engine, limit):
    from nafta2go.adapters.routing import DistanceMatrix

    sizes = []

    class Matrix:
        def matrix(self, sources, destinations):
            sizes.append(len(sources) - 1)
            return DistanceMatrix(
                [[60.0] * len(destinations) for _ in sources],
                [[1000.0] * len(destinations) for _ in sources],
                list(sources),
                list(destinations),
            )

    with clients(provider_factory=Matrix, routing_provider="synthetic-test") as client:
        response = client.post(
            "/api/v1/recommendations", json={**BODY, "max_candidates": limit}, headers=AUTH
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["query"]["max_candidates"] == limit
    assert (
        len(payload["evaluations"]) == 3 if limit == 3 else 10 < len(payload["evaluations"]) <= 20
    )
    assert sizes == [len(payload["evaluations"])]
    assert payload["navigation"]
    with engine.connect() as conn:
        saved = repo.get_recommendation(conn, payload["recommendation_id"])
    assert saved["request"]["max_candidates"] == limit
    assert saved["result"]["query"]["max_candidates"] == limit


@pytest.mark.parametrize("limit", [2, 21, 3.0, True, "20", None])
def test_invalid_candidate_limit_does_not_load_routes(clients, limit):
    def forbidden():
        pytest.fail("No se deben cargar rutas con un límite inválido")

    with clients(provider_factory=forbidden) as client:
        response = client.post(
            "/api/v1/recommendations", json={**BODY, "max_candidates": limit}, headers=AUTH
        )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_request"


def query_events(caplog):
    import json

    return [
        json.loads(record.message)
        for record in caplog.records
        if record.name == "nafta2go.presentation.telemetry"
    ]


def test_query_telemetry_is_correlated_private_and_authenticated(clients, caplog):
    from datetime import datetime
    from uuid import UUID

    caplog.set_level("INFO", logger="nafta2go.presentation.telemetry")
    with clients() as client:
        denied = client.get("/api/v1/operations")
        assert denied.status_code == 401
        initial_response = client.get("/api/v1/operations", headers=AUTH)
        assert initial_response.headers["cache-control"] == "no-store"
        initial = initial_response.json()
        assert initial["queries"]["completed"] == 0
        response = client.post(
            "/api/v1/recommendations?ubicacion=secreto-en-query",
            json=BODY,
            headers={**AUTH, "X-Request-ID": "secreto-del-cliente"},
        )
        metrics = client.get("/api/v1/operations", headers=AUTH).json()
    (event,) = query_events(caplog)
    assert UUID(response.headers["x-request-id"]).hex == event["request_id"]
    assert datetime.fromisoformat(event["started_at_utc"]).utcoffset().total_seconds() == 0
    assert event["duration_ms"] >= 0 and event["http_status"] == 200
    assert event["outcome"] == "recommended"
    assert set(event) == {
        "event",
        "request_id",
        "started_at_utc",
        "duration_ms",
        "http_status",
        "outcome",
    }
    assert metrics["scope"] == "process"
    assert metrics["queries"]["completed"] == 1
    assert metrics["queries"]["outcome"] == {"recommended": 1}
    assert metrics["routes"].keys() == {
        "hits",
        "misses",
        "requests",
        "errors",
        "limited",
        "busy",
        "entries",
    }
    for private in ("-34.6037", "-58.4565", "token-local-de-prueba", "secreto"):
        assert private not in str(event) + str(metrics)


@pytest.mark.parametrize("kind,status", [("unauthorized", 401), ("invalid", 422), ("timeout", 504)])
def test_telemetry_counts_errors_and_preserves_safe_responses(clients, caplog, kind, status):
    class Failing:
        def matrix(self, sources, destinations):
            raise ProviderTimeout("secreto-en-excepcion")

    caplog.set_level("INFO", logger="nafta2go.presentation.telemetry")
    with clients(provider_factory=Failing) as client:
        response = client.post(
            "/api/v1/recommendations",
            json={} if kind == "invalid" else BODY,
            headers={} if kind == "unauthorized" else AUTH,
        )
        metrics = client.get("/api/v1/operations", headers=AUTH).json()["queries"]
    assert response.status_code == status
    assert metrics["http_status"] == {str(status): 1}
    assert metrics["outcome"] == {"http_error": 1}
    assert query_events(caplog)[0]["http_status"] == status
    assert "secreto" not in caplog.text


def test_unexpected_failure_is_recorded_once_without_exception_text(clients, caplog):
    def failing():
        raise RuntimeError("secreto-inesperado")

    caplog.set_level("INFO", logger="nafta2go.presentation.telemetry")
    with clients(provider_factory=failing) as client:
        response = client.post("/api/v1/recommendations", json=BODY, headers=AUTH)
        assert response.status_code == 500
        assert response.json() == {"detail": {"code": "internal_error"}}
        assert response.headers["x-request-id"]
        assert client.get("/api/v1/operations", headers=AUTH).json()["queries"]["completed"] == 1
    (event,) = query_events(caplog)
    assert event["http_status"] == 500 and event["outcome"] == "http_error"
    assert event["error_type"] == "RuntimeError"
    assert "secreto" not in caplog.text


def test_query_telemetry_isolated_and_counts_concurrent_requests(clients):
    from concurrent.futures import ThreadPoolExecutor

    with clients() as client, clients() as other:
        with ThreadPoolExecutor(max_workers=8) as pool:
            responses = list(
                pool.map(lambda _: client.post("/api/v1/recommendations", json={}), range(24))
            )
        identifiers = {response.headers["x-request-id"] for response in responses}
        assert len(identifiers) == 24
        assert client.get("/api/v1/operations", headers=AUTH).json()["queries"]["completed"] == 24
        assert other.get("/api/v1/operations", headers=AUTH).json()["queries"]["completed"] == 0


@pytest.mark.parametrize("value", ["", "31", "secreto"])
def test_bad_coverage_policy_disables_readiness_and_returns_safe_503(
    clients, monkeypatch, caplog, value
):
    class NoRoutes:
        def matrix(self, sources, destinations):
            pytest.fail("No debe consultar rutas con política inválida")

    monkeypatch.setenv("NAFTA2GO_MAX_PRICE_AGE_DAYS", value)
    with clients(provider_factory=NoRoutes) as client:
        assert client.get("/ready").status_code == 503
        response = client.post("/api/v1/recommendations", json=BODY, headers=AUTH)
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "coverage_not_configured"
    assert "secreto" not in response.text + caplog.text


def test_server_controls_age_policy_and_client_cannot_override_it(clients, monkeypatch):
    monkeypatch.setenv("NAFTA2GO_MAX_PRICE_AGE_DAYS", "14")
    with clients() as client:
        response = client.post(
            "/api/v1/recommendations", json={**BODY, "max_price_age_days": 90}, headers=AUTH
        )
        assert response.status_code == 422
        response = client.post(
            "/api/v1/recommendations",
            headers=AUTH,
            json={**BODY, "origin": {"lat": -34.71, "lon": -58.33}, "destination": None},
        )
        assert response.status_code == 200
        assert response.json()["query"]["max_price_age_days"] == 14
