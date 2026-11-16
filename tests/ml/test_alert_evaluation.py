"""Umbrales sobre precios sintéticos; no constituyen validación de calidad real."""

import json
from datetime import UTC, datetime

import pytest

from nafta2go.application.price_alert_evaluation import evaluate_price_alerts
from nafta2go.application.price_dataset import encoded, sha256
from nafta2go.application.price_diagnostic import ASSUMPTION, reference_price
from nafta2go.ml.evaluate_alerts import main
from nafta2go.ml.temporal import FEATURES_VERSION

AUDIT = datetime(2026, 7, 1, tzinfo=UTC)


def inputs(tmp_path, *, audit_prices=(105, 106), mutate=lambda data, model: None):
    dataset, model = tmp_path / "dataset", tmp_path / "model"
    dataset.mkdir()
    model.mkdir()
    rows = [
        {
            "source_row": i,
            "partition": "validation",
            "target_at_utc": datetime(2026, i if i < 5 else i + 3, 1, tzinfo=UTC).isoformat(),
            "target_price_ars_per_l": price,
            "features": {
                "product_id": 2,
                "schedule_id": 2,
                "prior_median": 80,
                "previous_station_price": 90,
                "brand_recent_median": 100,
            },
        }
        for i, price in enumerate([110, 120, 130, 140, *audit_prices], 1)
    ]
    raw = b"".join(encoded(r) + b"\n" for r in rows)
    data = {
        "format_version": 1,
        "features_version": FEATURES_VERSION,
        "source": "historico",
        "availability_assumption": ASSUMPTION,
        "dataset_file": "examples.jsonl",
        "dataset_sha256": sha256(raw),
        "source_sha256": "a" * 64,
        "parameters": {"cutoff_utc": "2026-01-01T00:00:00+00:00"},
    }
    selection = {
        "format_version": 1,
        "features_version": FEATURES_VERSION,
        "availability_assumption": ASSUMPTION,
        "chosen_method": "bandera_reciente",
        "dataset_sha256": sha256(raw),
        "source_sha256": "a" * 64,
        "parameters": {"selection_start_utc": "2025-01-01T00:00:00+00:00"},
    }
    mutate(data, selection)
    selection["dataset_manifest_sha256"] = sha256(encoded(data))
    (dataset / "manifest.json").write_bytes(encoded(data))
    (dataset / "examples.jsonl").write_bytes(raw)
    (model / "manifest.json").write_bytes(encoded(selection))
    return dataset, model


def rewrite(dataset, model, rows):
    changed = b"".join(encoded(row) + b"\n" for row in rows)
    data = json.loads((dataset / "manifest.json").read_bytes())
    data["dataset_sha256"] = sha256(changed)
    selection = json.loads((model / "manifest.json").read_bytes())
    selection.update(dataset_sha256=sha256(changed), dataset_manifest_sha256=sha256(encoded(data)))
    (dataset / "examples.jsonl").write_bytes(changed)
    (dataset / "manifest.json").write_bytes(encoded(data))
    (model / "manifest.json").write_bytes(encoded(selection))


def test_audit_never_changes_calibration_threshold_and_outputs_repeat(tmp_path):
    dataset, model = inputs(tmp_path)
    first = evaluate_price_alerts(dataset, model, tmp_path / "first", AUDIT, 0.5, 2)
    second = evaluate_price_alerts(dataset, model, tmp_path / "second", AUDIT, 0.5, 2)
    assert first == second
    assert first["runtime_enabled"] is False
    segment = first["segments"]["2:2"]
    assert segment == {
        "status": "candidate",
        "calibration_examples": 4,
        "audit_examples": 2,
        "relative_deviation_threshold": 0.2,
        "audit_exceedances": 0,
        "audit_exceedance_rate": 0,
    }
    raw = (dataset / "examples.jsonl").read_bytes()
    assert first["dataset_sha256"] == sha256(raw)
    rows = [json.loads(line) for line in raw.splitlines()]
    rows[-1]["target_price_ars_per_l"] = 100000
    rewrite(dataset, model, rows)
    third = evaluate_price_alerts(dataset, model, tmp_path / "third", AUDIT, 0.5, 2)
    assert third["segments"]["2:2"]["relative_deviation_threshold"] == 0.2
    assert third["segments"]["2:2"]["audit_exceedance_rate"] == 0.5
    with pytest.raises(ValueError):
        evaluate_price_alerts(dataset, model, tmp_path / "first", AUDIT, 0.5, 2)


@pytest.mark.parametrize("kind", ["method", "hash", "features", "cutoff", "file", "assumption"])
def test_rejects_incompatible_manifests_before_writing(tmp_path, kind):
    def mutate(data, model):
        if kind == "method":
            model["chosen_method"] = "boosting"
        if kind == "hash":
            model["source_sha256"] = "b" * 64
        if kind == "features":
            model["features_version"] = "old"
        if kind == "cutoff":
            data["parameters"]["cutoff_utc"] = AUDIT.isoformat()
        if kind == "file":
            data["dataset_file"] = "../private.json"
        if kind == "assumption":
            data["availability_assumption"] = "unknown"

    dataset, model = inputs(tmp_path, mutate=mutate)
    with pytest.raises(ValueError):
        evaluate_price_alerts(dataset, model, tmp_path / "output", AUDIT, 0.95, 2)
    assert not (tmp_path / "output").exists()


def test_abstains_without_support_and_rejects_tampered_dataset(tmp_path, capsys):
    dataset, model = inputs(tmp_path)
    report = evaluate_price_alerts(dataset, model, tmp_path / "output", AUDIT, 0.95)
    assert report["segments"]["2:2"]["status"] == "insufficient_support"
    assert report["segments"]["2:2"]["relative_deviation_threshold"] is None
    (dataset / "examples.jsonl").write_text("secreto")
    args = [
        "--dataset",
        str(dataset),
        "--model",
        str(model),
        "--output",
        str(tmp_path / "bad"),
        "--audit-start",
        AUDIT.isoformat(),
        "--quantile",
        ".95",
    ]
    assert main(args) == 2
    assert "secreto" not in capsys.readouterr().err
    assert not (tmp_path / "bad").exists()


def test_reference_is_shared_with_serving_and_falls_back():
    features = {"brand_recent_median": None, "previous_station_price": 90.1234, "prior_median": 80}
    assert str(reference_price(features, "bandera_reciente")) == "90.123"
    features["previous_station_price"] = None
    assert str(reference_price(features, "bandera_reciente")) == "80.000"


@pytest.mark.parametrize("kind", ["duplicate", "train_after_cutoff", "validation_before_cutoff"])
def test_rejects_temporal_overlap_and_duplicate_support(tmp_path, kind):
    dataset, model = inputs(tmp_path)
    rows = [json.loads(line) for line in (dataset / "examples.jsonl").read_bytes().splitlines()]
    if kind == "duplicate":
        rows.append(rows[0])
    elif kind == "train_after_cutoff":
        rows[0]["partition"] = "train"
    else:
        rows[0]["target_at_utc"] = "2025-12-31T00:00:00+00:00"
    rewrite(dataset, model, rows)
    with pytest.raises(ValueError):
        evaluate_price_alerts(dataset, model, tmp_path / "output", AUDIT, 0.95, 2)
    assert not (tmp_path / "output").exists()
