"""El smoke usa transporte inyectable y falla ante cada violación del contrato."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from deploy.smoke import SmokeFailure, smoke
from nafta2go.adapters.recorded_routes import RecordedRoutes
from nafta2go.application.coverage_rules import ROOT
from nafta2go.presentation.http import create_app


def test_smoke_through_http_and_persistence(engine, monkeypatch):
    monkeypatch.setenv("NAFTA2GO_API_TOKEN", "driver")
    monkeypatch.setenv("NAFTA2GO_ADMIN_TOKEN", "admin")
    app = create_app(
        engine, lambda: RecordedRoutes(ROOT / "docs/evidencia/poc-05-flujo-2026-10-26/matrix.json")
    )
    with TestClient(app) as client:
        assert smoke("", "driver", client)["evaluations"] == 10


@pytest.mark.parametrize(
    "failure", ["health", "ready", "web", "operation", "anonymous", "roles", "query", "empty"]
)
def test_failed_contract(failure):
    def response(status, body=None):
        return SimpleNamespace(status_code=status, json=lambda: body)

    def get(url, **kwargs):
        path = {
            "/health": "health",
            "/ready": "ready",
            "/": "web",
            "/operacion": "operation",
            "/api/v1/operations": "roles",
        }[url]
        return response(500 if failure == path else 401 if path == "roles" else 200)

    def post(url, **kwargs):
        name = "query" if kwargs.get("headers") else "anonymous"
        return response(
            500 if failure == name else 401 if name == "anonymous" else 200,
            {
                "evaluations": [] if failure == "empty" else [1],
                "recommendation_id": 1,
                "status": "historical_scenario",
            },
        )

    with pytest.raises(SmokeFailure):
        smoke("", "private", SimpleNamespace(get=get, post=post))


def test_readiness_reports_missing_and_historical_data(engine, monkeypatch):
    monkeypatch.setenv("NAFTA2GO_API_TOKEN", "driver")
    with TestClient(create_app(engine)) as client:
        assert client.get("/ready").json()["data_status"] == "historical_scenario"
        monkeypatch.setattr(
            "nafta2go.application.readiness.load_scenario", Mock(side_effect=OSError("private"))
        )
        response = client.get("/ready")
        assert response.status_code == 503 and response.json()["data_status"] == "unavailable"
        assert "private" not in response.text


def test_readiness_rejects_a_historical_fixture_outside_age_policy(engine, monkeypatch):
    monkeypatch.setenv("NAFTA2GO_API_TOKEN", "driver")
    monkeypatch.setenv("NAFTA2GO_MAX_PRICE_AGE_DAYS", "1")
    with TestClient(create_app(engine)) as client:
        response = client.get("/ready")
    assert response.status_code == 503
    assert response.json()["data_status"] == "unavailable"
