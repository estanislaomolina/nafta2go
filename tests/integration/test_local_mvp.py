"""Cruce de ingesta, reintentos, caché, HTTP y monitor; reloj/datos de QA explícitos."""

import csv
import hashlib
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import requests
from fastapi.testclient import TestClient

from nafta2go.adapters.acquisition import acquire_with_retries
from nafta2go.adapters.openrouteservice import OpenRouteServiceClient
from nafta2go.adapters.recorded_routes import CapturedRoutes
from nafta2go.adapters.route_cache import RouteCache
from nafta2go.application.ingestion_monitor import check_ingestion
from nafta2go.normalization.pipeline import normalize_capture
from nafta2go.persistence import repository as repo
from nafta2go.persistence.models import RawCapture
from nafta2go.presentation.http import create_app
from nafta2go.services.ingestion import IngestionFailed, ingest_from_source

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "docs/evidencia/escenario-vigente-2026-10-24/precios_caba_nafta.csv"
REFERENCE = datetime(2026, 10, 26, 12, tzinfo=UTC)
BODY = {
    "origin": {"lat": -34.6037, "lon": -58.3816},
    "destination": {"lat": -34.5627, "lon": -58.4565},
    "fuel_type": "super",
    "consumption_l_per_100km": "10",
    "tank_capacity_l": "50",
    "remaining_l": "10",
    "budget_ars": "12000",
    "reserve_l": "2",
    "max_candidates": 20,
}


def capture(path):
    content = path.read_bytes()
    return RawCapture(
        "vigente",
        path.as_uri(),
        hashlib.sha256(content).hexdigest(),
        len(content),
        str(path),
        datetime(2026, 10, 26, 9),
    )


def changed_fixture(path):
    # Captura sintética: conserva coordenadas/fechas y aumenta 1 ARS cada precio.
    with SOURCE.open(encoding="utf-8-sig", newline="") as raw:
        reader = csv.DictReader(raw)
        rows, fields = list(reader), reader.fieldnames
    for row in rows:
        row["precio"] = str(Decimal(row["precio"]) + 1)
    with path.open("w", encoding="utf-8-sig", newline="") as raw:
        writer = csv.DictWriter(raw, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return capture(path)


def test_recovery_prices_and_cached_routes_remain_consistent(engine, tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("NAFTA2GO_API_TOKEN", "codigo-integracion-de-prueba")
    original = capture(SOURCE)
    acquire, sleep = Mock(side_effect=[requests.ConnectionError("DNS de prueba"), original]), Mock()
    run = ingest_from_source(
        engine,
        "vigente",
        lambda: acquire_with_retries(acquire, "vigente", sleep),
        normalize_capture,
        clock=lambda: REFERENCE.replace(tzinfo=None),
    )
    sleep.assert_called_once_with(60)
    with engine.connect() as conn:
        assert repo.get_run(conn, run)["report"]["acquisition_attempts"] == 2
    assert check_ingestion(engine, "vigente", REFERENCE)["status"] == "healthy"

    def post(_url, *, json, **_options):
        table = [[1000.0] * len(json["destinations"]) for _ in json["sources"]]
        return SimpleNamespace(
            status_code=200, headers={}, json=lambda: {"durations": table, "distances": table}
        )

    session, cache = Mock(post=Mock(side_effect=post)), RouteCache()
    monkeypatch.setattr(
        "nafta2go.adapters.recorded_routes.client_from_env",
        lambda: OpenRouteServiceClient("credencial-ficticia", session),
    )
    app = create_app(
        engine,
        lambda: CapturedRoutes(cache),
        lambda: REFERENCE + timedelta(minutes=5),
        "synthetic-integration-fixture",
    )
    with TestClient(app) as client:

        def query():
            response = client.post(
                "/api/v1/recommendations",
                json=BODY,
                headers={"Authorization": "Bearer codigo-integracion-de-prueba"},
            )
            assert response.status_code == 200
            return response.json()

        first = query()
        assert first["status"] == "ready" and first["data_run_id"] == run
        assert first["query"]["max_candidates"] == 20
        assert 10 < len(first["evaluations"]) <= 20
        assert first["routes"]["cache_hit"] is False
        replacement = changed_fixture(tmp_path / "synthetic-price-update.csv")
        updated = ingest_from_source(
            engine,
            "vigente",
            lambda: replacement,
            normalize_capture,
            clock=lambda: (REFERENCE + timedelta(minutes=1)).replace(tzinfo=None),
        )
        second = query()
        assert second["data_run_id"] == updated != run
        assert second["source"]["sha256"] == replacement.sha256 != original.sha256
        assert second["routes"]["cache_hit"] is True
        assert second["routes"]["sha256"] == first["routes"]["sha256"]
        prices = {
            row["station_id"]: Decimal(row["price_ars_per_l"]) for row in first["evaluations"]
        }
        assert all(
            Decimal(row["price_ars_per_l"]) == prices[row["station_id"]] + 1
            for row in second["evaluations"]
        )
        assert second["navigation"]

        failed = Mock(side_effect=requests.Timeout("fallo sintético"))
        with pytest.raises(IngestionFailed) as failure:
            ingest_from_source(
                engine,
                "vigente",
                lambda: acquire_with_retries(failed, "vigente", Mock()),
                normalize_capture,
                clock=lambda: (REFERENCE + timedelta(minutes=2)).replace(tzinfo=None),
            )
        assert failed.call_count == 3
        assert (
            check_ingestion(engine, "vigente", REFERENCE + timedelta(minutes=6))["alerts"][0][
                "run_id"
            ]
            == failure.value.run_id
        )
        third = query()
        assert third["data_run_id"] == updated and third["routes"]["cache_hit"]
        assert session.post.call_count == 1
        with engine.connect() as conn:
            saved = repo.get_recommendation(conn, third["recommendation_id"])
        encoded = json.dumps(saved, default=str)
        assert "-34.6037" not in encoded and "-58.4565" not in encoded
        assert "google.com/maps" not in encoded
        assert "credencial-ficticia" not in caplog.text
