"""Serving con precios/manifiestos sintéticos; no afirma calidad predictiva real."""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from nafta2go.application.price_diagnostic import ASSUMPTION
from nafta2go.application.scenario import load_scenario
from nafta2go.ml.models import examples_frame, reference_predictions
from nafta2go.ml.temporal import FEATURES_VERSION, build_temporal_dataset
from nafta2go.persistence import repository as repo
from nafta2go.persistence.models import RawCapture
from nafta2go.persistence.schema import raw_captures, recommendations, station_prices
from nafta2go.presentation.http import create_app

NOW = datetime(2026, 1, 4, tzinfo=UTC)
AUTH = {"Authorization": "Bearer prueba-local"}
URL = "/api/v1/price-diagnostics/7"


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True))


@pytest.fixture
def prepared(engine, tmp_path, monkeypatch):
    monkeypatch.setenv("NAFTA2GO_API_TOKEN", "prueba-local")
    start = datetime(2026, 1, 1, 12)
    base = {
        **load_scenario().rows[0],
        "id": None,
        "lat": -34.60,
        "lon": -58.40,
        "brand": "PRUEBA",
        "product_id": 2,
        "schedule_id": 2,
    }
    history = [
        {
            **base,
            "station_id": station,
            "source_row": index,
            "valid_from": start + timedelta(days=day),
            "price": price,
        }
        for index, (station, day, price) in enumerate(
            [(1, 0, 100), (2, 0, 110), (3, 0, 120), (7, 1, 125), (5, 1, 135)], 1
        )
    ]
    target = {
        **base,
        "station_id": 7,
        "source_row": 900,
        "valid_from": start + timedelta(days=2),
        "price": 150,
    }
    runs = {}
    with engine.begin() as conn:
        for source, rows, digest in [
            ("historico", history, "a" * 64),
            ("vigente", [target], "b" * 64),
        ]:
            run = repo.start_run(conn, source, start)
            repo.add_raw_capture(
                conn,
                run,
                RawCapture(
                    source, "https://example.invalid/secreto", digest, 123, "/secreto.csv", start
                ),
            )
            conn.execute(station_prices.insert(), [{**row, "run_id": run} for row in rows])
            repo.finish_run(conn, run, "succeeded", start, rules_version="1")
            runs[source] = run
    dataset, model = tmp_path / "dataset", tmp_path / "model"
    dataset.mkdir()
    model.mkdir()
    write(
        dataset / "manifest.json",
        {
            "format_version": 1,
            "features_version": FEATURES_VERSION,
            "source": "historico",
            "source_sha256": "a" * 64,
            "dataset_sha256": "d" * 64,
            "availability_assumption": ASSUMPTION,
            "normalization_rules_version": "1",
            "parameters": {"window_days": 30, "min_history": 5},
        },
    )
    write(
        model / "manifest.json",
        {
            "format_version": 1,
            "features_version": FEATURES_VERSION,
            "source_sha256": "a" * 64,
            "dataset_sha256": "d" * 64,
            "availability_assumption": ASSUMPTION,
            "chosen_method": "bandera_reciente",
            "artifact_model": "boosting",
            "artifact_file": "model.joblib",
            "dataset_manifest_sha256": hashlib.sha256(
                (dataset / "manifest.json").read_bytes()
            ).hexdigest(),
        },
    )
    # El artefacto no elegido ni siquiera es un pickle válido: nunca debe cargarse.
    (model / "model.joblib").write_bytes(b"NO CARGAR")
    monkeypatch.setenv("NAFTA2GO_PRICE_DATASET_DIR", str(dataset))
    monkeypatch.setenv("NAFTA2GO_PRICE_MODEL_DIR", str(model))
    return runs, history, target, model / "manifest.json"


def client(engine):
    return TestClient(
        create_app(
            engine, clock=lambda: NOW, provider_factory=Mock(side_effect=AssertionError("No ORS"))
        )
    )


@pytest.mark.parametrize("method", ["mediana_previa", "ultimo_precio", "bandera_reciente"])
@pytest.mark.parametrize("brand", ["PRUEBA", "NUEVA"])
def test_reference_matches_training_and_does_not_write(engine, prepared, method, brand):
    runs, history, target, manifest = prepared
    target["brand"] = brand
    with engine.begin() as conn:
        conn.execute(
            station_prices.update()
            .where(station_prices.c.run_id == runs["vigente"])
            .values(brand=brand)
        )
    model = json.loads(manifest.read_bytes())
    model["chosen_method"] = method
    write(manifest, model)
    examples, _ = build_temporal_dataset([*history, target], NOW)
    frame = examples_frame(examples)
    expected = frame.prior_median.iloc[-1] * np.exp(reference_predictions(frame)[method].iloc[-1])
    with client(engine) as http:
        response = http.get(URL, headers=AUTH)
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    body = response.json()
    assert float(body["reference_ars_per_l"]) == pytest.approx(expected)
    assert body["official_price_ars_per_l"] == "150.000"
    assert float(body["difference_ars_per_l"]) == pytest.approx(150 - expected)
    assert body["status"] == "reference_only" and body["alert_level"] == "not_calibrated"
    assert body["scope"] == "published_price_retrospective" and body["method"] == method
    assert body["version"] == hashlib.sha256(manifest.read_bytes()).hexdigest()
    assert body["data_run_id"] == runs["vigente"]
    assert not any(secret in response.text for secret in ("secreto", "lat", "lon", "joblib"))
    with engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(recommendations)) == 0
        assert conn.scalar(select(func.count()).select_from(station_prices)) == 6


def test_same_time_future_and_target_price_do_not_change_reference(engine, prepared):
    runs, history, target, _ = prepared
    with engine.begin() as conn:
        conn.execute(
            station_prices.update()
            .where(station_prices.c.run_id == runs["vigente"])
            .values(price=900)
        )
        conn.execute(
            station_prices.insert(),
            [
                {
                    **history[0],
                    "id": None,
                    "run_id": runs["historico"],
                    "station_id": 90 + day,
                    "source_row": 90 + day,
                    "valid_from": target["valid_from"] + timedelta(days=day),
                    "price": 1,
                }
                for day in (0, 1)
            ],
        )
        conn.execute(
            station_prices.insert(),
            {
                **target,
                "id": None,
                "run_id": runs["vigente"],
                "source_row": 901,
                "valid_from": target["valid_from"] + timedelta(days=10),
                "price": 9999,
            },
        )
    with client(engine) as http:
        body = http.get(URL, headers=AUTH).json()
    assert body["reference_ars_per_l"] == "120.000"
    assert body["official_price_ars_per_l"] == "900.000"
    assert body["alert_level"] == "not_calibrated"  # No inventar un umbral ante esa diferencia.


@pytest.mark.parametrize(
    "failure", ["config", "hash", "features", "method", "capture", "rules", "history"]
)
def test_incompatible_configuration_is_safe(engine, prepared, monkeypatch, failure):
    runs, _, _, manifest = prepared
    model = json.loads(manifest.read_bytes())
    if failure == "config":
        monkeypatch.setenv("NAFTA2GO_PRICE_MODEL_DIR", "/secreto-no-existe")
    if failure == "hash":
        model["dataset_manifest_sha256"] = "otro"
    if failure == "features":
        model["features_version"] = "incompatible"
    if failure == "method":
        model["chosen_method"] = "boosting"
    if failure == "capture":
        with engine.begin() as conn:
            conn.execute(
                raw_captures.update()
                .where(raw_captures.c.run_id == runs["historico"])
                .values(sha256="c" * 64)
            )
    if failure == "history":
        with engine.begin() as conn:
            repo.finish_run(
                conn, runs["historico"], "failed", datetime(2026, 1, 1), rules_version="1"
            )
    if failure == "rules":
        with engine.begin() as conn:
            repo.finish_run(
                conn, runs["historico"], "succeeded", datetime(2026, 1, 1), rules_version="otra"
            )
    write(manifest, model)
    with client(engine) as http:
        response = http.get(URL, headers=AUTH)
    assert response.status_code == 503
    assert response.json() == {"detail": {"code": "price_diagnostic_unavailable"}}
    assert "secreto" not in response.text


def test_insufficient_context_and_missing_station_are_explicit(engine, prepared):
    runs, _, _, _ = prepared
    with engine.begin() as conn:
        conn.execute(station_prices.delete().where(station_prices.c.run_id == runs["historico"]))
    with client(engine) as http:
        body = http.get(URL, headers=AUTH).json()
        assert http.get(URL + "99", headers=AUTH).status_code == 404
    assert body["status"] == "unavailable" and body["reference_ars_per_l"] is None
    assert body["difference_ars_per_l"] is None and body["reason"] == "context_unavailable"


def test_auth_validation_and_missing_configuration(engine, monkeypatch):
    monkeypatch.setenv("NAFTA2GO_API_TOKEN", "prueba-local")
    monkeypatch.delenv("NAFTA2GO_PRICE_MODEL_DIR", raising=False)
    with client(engine) as http:
        assert http.get(URL).status_code == 401
        assert http.get(URL + "?product_id=9", headers=AUTH).status_code == 422
        extra = http.get(URL + "?price=secreto", headers=AUTH)
        assert extra.status_code == 422 and "secreto" not in extra.text
        assert http.get(URL, headers=AUTH).status_code == 503
