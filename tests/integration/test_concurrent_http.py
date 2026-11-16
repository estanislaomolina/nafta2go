"""Concurrencia HTTP real con precios históricos y transporte ORS sintético."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Event, Lock
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from nafta2go.adapters.openrouteservice import OpenRouteServiceClient
from nafta2go.adapters.recorded_routes import CapturedRoutes
from nafta2go.adapters.route_cache import RouteCache
from nafta2go.persistence import repository as repo
from nafta2go.persistence.schema import recommendations
from nafta2go.presentation.http import create_app

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


@pytest.mark.parametrize("identical", [False, True])
def test_http_requests_share_identical_routes_but_do_not_block_different_routes(
    engine, monkeypatch, identical
):
    monkeypatch.setenv("NAFTA2GO_API_TOKEN", "codigo-concurrencia-qa")
    monkeypatch.setenv("NAFTA2GO_MAX_PRICE_AGE_DAYS", "30")
    cache = RouteCache()
    both_transports, both_providers, release, state = Event(), Event(), Event(), Lock()
    counts = {"providers": 0, "transports": 0}

    def post(_url, *, json, **_options):
        with state:
            counts["transports"] += 1
            if counts["transports"] == 2:
                both_transports.set()
        assert release.wait(5), "El test debe liberar el transporte sintético"
        table = [[1000.0] * len(json["destinations"]) for _ in json["sources"]]
        return SimpleNamespace(
            status_code=200, headers={}, json=lambda: {"durations": table, "distances": table}
        )

    session = Mock()
    session.post.side_effect = post
    monkeypatch.setattr(
        "nafta2go.adapters.recorded_routes.client_from_env",
        lambda: OpenRouteServiceClient("clave-sintetica", session=session),
    )

    def provider():
        with state:
            counts["providers"] += 1
            if counts["providers"] == 2:
                both_providers.set()
        return CapturedRoutes(cache)

    app = create_app(
        engine,
        provider,
        lambda: datetime(2026, 10, 26, 12, tzinfo=UTC),
        routing_provider="synthetic-concurrency-qa",
    )
    second = BODY if identical else {**BODY, "origin": {"lat": -34.6040, "lon": -58.3816}}
    with TestClient(app) as client, ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [
            pool.submit(
                client.post,
                "/api/v1/recommendations",
                json=body,
                headers={"Authorization": "Bearer codigo-concurrencia-qa"},
            )
            for body in (BODY, second)
        ]
        try:
            assert both_providers.wait(3)
            if not identical:
                assert both_transports.wait(1), "Una ruta distinta quedó bloqueada por la otra"
        finally:
            release.set()
        responses = [job.result(timeout=5) for job in jobs]
    assert [response.status_code for response in responses] == [200, 200]
    assert counts["transports"] == (1 if identical else 2)
    assert cache.snapshot()["requests"] == (1 if identical else 2)
    assert cache.snapshot()["hits"] == int(identical)
    payloads = [response.json() for response in responses]
    assert all(payload["outcome"] == "recommended" for payload in payloads)
    assert len({payload["recommendation_id"] for payload in payloads}) == 2
    with engine.connect() as conn:
        assert conn.execute(select(func.count()).select_from(recommendations)).scalar_one() == 2
        for payload in payloads:
            record = repo.get_recommendation(conn, payload["recommendation_id"])
            assert "-34.6037" not in str(record) and "-34.604" not in str(record)
