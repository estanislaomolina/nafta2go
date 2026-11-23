"""Métricas reproducibles, privadas y sin contar una estación por prioridad."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from prometheus_client.parser import text_string_to_metric_families
from sqlalchemy import select

from nafta2go.adapters.recorded_routes import RecordedRoutes
from nafta2go.persistence.schema import recommendations
from nafta2go.presentation.http import create_app
from tests.presentation.test_http import BODY

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def client(engine, monkeypatch):
    monkeypatch.setenv("NAFTA2GO_API_TOKEN", "private-driver")
    monkeypatch.setenv("NAFTA2GO_ADMIN_TOKEN", "private-admin")
    with TestClient(
        create_app(
            engine,
            lambda: RecordedRoutes(ROOT / "docs/evidencia/poc-05-flujo-2026-10-26/matrix.json"),
            clock=lambda: datetime(2026, 10, 26, 12, tzinfo=UTC),
        )
    ) as client:
        yield client


def scrape(client):
    response = client.get("/metrics", headers={"Authorization": "Bearer private-admin"})
    assert response.status_code == 200
    return response.text, [
        sample
        for family in text_string_to_metric_families(response.text)
        for sample in family.samples
    ]


def values(samples, name):
    return [sample.value for sample in samples if sample.name == "nafta2go_" + name]


def test_authentication_and_private_labels(client):
    assert client.get("/metrics").status_code == 401
    assert (
        client.get("/metrics", headers={"Authorization": "Bearer private-driver"}).status_code
        == 401
    )
    client.get("/unknown/private-search/-34.6037")
    client.get("/api/v1/price-diagnostics/private-search")
    text, samples = scrape(client)
    for private in ("private-search", "private-driver", "private-admin", "-34.6037", "-58.4565"):
        assert private not in text
    assert any(s.labels.get("endpoint") == "other" for s in samples)
    assert any(
        s.labels.get("endpoint") == "/api/v1/price-diagnostics/{station_id}" for s in samples
    )


def test_stored_estimates_deduplicate_winners_and_scrapes(client, engine):
    result = client.post(
        "/api/v1/recommendations", json=BODY, headers={"Authorization": "Bearer private-driver"}
    ).json()
    with engine.begin() as conn:
        row = conn.execute(select(recommendations)).first()._mapping
        body = dict(row["result"])
        body["alternatives"] += body["alternatives"]  # Otra prioridad no es otra estación.
        conn.execute(recommendations.update().values(result=body))
    _, samples = scrape(client)
    assert sum(values(samples, "recommendations_stored")) == 1
    assert sum(values(samples, "recommendations_station")) == len(result["alternatives"])
    ids = {str(choice["station_id"]) for choice in result["alternatives"]}
    expected = sum(
        float(row["metrics"]["purchased_l"])
        for row in result["evaluations"]
        if str(row["station_id"]) in ids
    )
    assert sum(values(samples, "recommendations_estimated_liters")) == pytest.approx(expected)
    assert sum(values(samples, "recommendations_commune_estimated_liters")) == pytest.approx(
        expected
    )
    _, repeated = scrape(client)
    assert values(repeated, "recommendations_station") == values(samples, "recommendations_station")
    assert sum(values(samples, "queries_total")) == 1


def test_business_cache_is_bounded_and_request_counters_stay_fresh(client, monkeypatch):
    clock = [0.0]
    monkeypatch.setattr("nafta2go.presentation.prometheus.monotonic", lambda: clock[0])
    headers = {"Authorization": "Bearer private-driver"}
    client.post("/api/v1/recommendations", json=BODY, headers=headers)
    _, first = scrape(client)
    assert sum(values(first, "recommendations_stored")) == 1
    client.post("/api/v1/recommendations", json=BODY, headers=headers)
    _, cached = scrape(client)
    assert sum(values(cached, "recommendations_stored")) == 1
    assert sum(values(cached, "queries_total")) == 2
    clock[0] = 121
    _, refreshed = scrape(client)
    assert sum(values(refreshed, "recommendations_stored")) == 2


def test_missing_coverage_is_counted_in_process_without_private_rows(client, engine):
    result = client.post(
        "/api/v1/recommendations",
        json={**BODY, "origin": {"lat": -34.71, "lon": -58.33}, "destination": None},
        headers={"Authorization": "Bearer private-driver"},
    )
    assert result.status_code == 200 and result.json()["outcome"] == "insufficient_coverage"
    _, samples = scrape(client)
    assert sum(values(samples, "recommendations_stored")) == 0
    assert any(s.labels.get("outcome") == "insufficient_coverage" and s.value == 1 for s in samples)
