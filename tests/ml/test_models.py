"""Comparación de modelos sobre ejemplos sintéticos: ninguna métrica representa calidad real."""

import json
import math
from datetime import UTC, datetime, timedelta

import joblib
import numpy as np
import pandas as pd
import pytest

from nafta2go.application.price_dataset import encoded, sha256
from nafta2go.application.price_model import train_price_models
from nafta2go.ml.models import (
    CANDIDATES,
    build_model,
    error_analysis,
    examples_frame,
    fit,
    metrics,
    predict,
    reference_predictions,
)
from nafta2go.ml.train import main

START = datetime(2023, 1, 1, tzinfo=UTC)
CUTOFF = datetime(2026, 1, 1, 3, tzinfo=UTC)
SELECTION = datetime(2025, 1, 1, tzinfo=UTC)


def example(row, station, when, price, prior, previous=None, partition="train", **features):
    return {
        "source_row": row,
        "station_id": station,
        "target_at_utc": when.isoformat(),
        "partition": partition,
        "target_price_ars_per_l": price,
        "baseline_scope": "zone",
        "features": {
            "product_id": 2,
            "schedule_id": 2,
            "brand": "YPF",
            "zone_lat": -1730,
            "zone_lon": -2920,
            "time_days": 0.0,
            "prior_median": prior,
            "prior_count": 10,
            "prior_iqr": 2.0,
            "previous_station_price": previous[1] if previous else None,
            "previous_station_age_days": previous[0] if previous else None,
        }
        | features,
    }


def synthetic_examples(seed=3, stations=8):
    """Precios que siguen al mercado con un desvío propio y persistente por estación."""
    rng = np.random.default_rng(seed)
    rows, number = [], 0
    for station in range(stations):
        offset, brand = (
            rng.uniform(-0.04, 0.04),
            ("YPF", "AXION", "PUMA", "SHELL C.A.P.S.A.")[station % 4],
        )
        when, previous = START + timedelta(days=float(rng.uniform(0, 9))), None
        while when < CUTOFF + timedelta(days=90):
            prior = 100 * math.exp(0.002 * (when - START).days)
            price = round(prior * math.exp(offset + rng.normal(0, 0.005)), 2)
            number += 1
            partition = "train" if when < CUTOFF else "validation"
            age = (when - previous[0]).total_seconds() / 86400 if previous else None
            rows.append(
                example(
                    number,
                    station,
                    when,
                    price,
                    round(prior, 2),
                    (age, previous[1]) if previous else None,
                    partition,
                    brand=brand,
                )
            )
            previous = (when, price)
            when += timedelta(days=float(rng.uniform(5, 15)))
    return rows


def write_dataset(directory, examples):
    directory.mkdir()
    raw = b"".join(encoded(row) + b"\n" for row in examples)
    (directory / "examples.jsonl").write_bytes(raw)
    manifest = {
        "dataset_file": "examples.jsonl",
        "dataset_sha256": sha256(raw),
        "features_version": "price-temporal-v1",
        "source_sha256": "c" * 64,
        "availability_assumption": "valid_from_proxy_retrospective_not_verified",
    }
    (directory / "manifest.json").write_bytes(encoded(manifest) + b"\n")
    return directory


def test_frame_is_relative_to_prior_median_and_uses_only_previous_examples():
    when = datetime(2025, 3, 1, tzinfo=UTC)
    frame = examples_frame(
        [
            example(2, 1, when + timedelta(days=10), 121, 110, (10, 100)),
            example(1, 1, when, 100, 100),
            example(3, 2, when + timedelta(days=10), 99, 110, brand="PUMA"),
        ]
    )
    later = frame[frame.source_row == 2].iloc[0]
    assert later.target == pytest.approx(math.log(121 / 110))
    assert later.previous_relative == pytest.approx(math.log(100 / 110))
    assert later.market_change == pytest.approx(math.log(110 / 100))
    assert later.prior_iqr_relative == pytest.approx(2 / 110)
    first = frame[frame.source_row == 1].iloc[0]
    assert math.isnan(first.market_change) and first.reference == 0
    assert frame[frame.source_row == 3].brand_group.item() == "OTRA"


def test_references_and_metrics_are_in_ars_per_liter():
    when = datetime(2025, 3, 1, tzinfo=UTC)
    frame = examples_frame([example(1, 1, when, 110, 100, (5, 105)), example(2, 2, when, 90, 100)])
    predicted = reference_predictions(frame)
    # Último precio: 105 frente a 110; sin precio previo se usa la mediana (100 frente a 90).
    assert metrics(frame, predicted["ultimo_precio"])["mae_ars_per_l"] == pytest.approx(7.5)
    assert metrics(frame, predicted["mediana_previa"])["mae_ars_per_l"] == pytest.approx(10)
    analysis = error_analysis(frame, predicted["ultimo_precio"])
    assert analysis["antiguedad_precio_previo"]["hasta_7_dias"]["mae_ars_per_l"] == pytest.approx(5)
    assert analysis["antiguedad_precio_previo"]["sin_precio_previo"]["examples"] == 1
    assert analysis["cambio_sobre_precio_previo"]["1_a_5pct"]["examples"] == 1


@pytest.mark.parametrize("name", CANDIDATES)
def test_models_learn_a_correction_over_the_last_price(name):
    frame = examples_frame(synthetic_examples())
    train, rest = frame[frame.partition == "train"], frame[frame.partition == "validation"]
    model = fit(build_model(name, seed=0), train)
    predicted = predict(model, rest)
    assert predicted.notna().all()
    assert (
        metrics(rest, predicted)["mae_ars_per_l"]
        < metrics(rest, reference_predictions(rest)["mediana_previa"])["mae_ars_per_l"]
    )


def test_training_writes_reproducible_artifacts(tmp_path):
    dataset = write_dataset(tmp_path / "dataset", synthetic_examples())
    first = train_price_models(dataset, tmp_path / "a", SELECTION)
    train_price_models(dataset, tmp_path / "b", SELECTION)
    for name in ("model-report.json", "validation-predictions.jsonl", "manifest.json"):
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()
    report, manifest = first["report"], first["manifest"]
    assert (
        set(report["selection"])
        == set(report["validation"])
        == {
            "mediana_previa",
            "ultimo_precio",
            *CANDIDATES,
        }
    )
    assert report["chosen_method"] == min(
        report["selection"], key=lambda name: report["selection"][name]["mae_ars_per_l"]
    )
    assert (
        manifest["dataset_sha256"]
        == json.loads((dataset / "manifest.json").read_text())["dataset_sha256"]
    )
    assert manifest["parameters"]["random_seed"] == 0

    frame = examples_frame(synthetic_examples())
    validation = frame[frame.partition == "validation"]
    stored = [json.loads(line) for line in (tmp_path / "a" / "validation-predictions.jsonl").open()]
    reloaded = predict(joblib.load(tmp_path / "a" / "model.joblib"), validation)
    assert [row["source_row"] for row in stored] == validation.source_row.tolist()
    np.testing.assert_allclose(reloaded, [row["predicted_target"] for row in stored], atol=1e-6)


def test_validation_never_influences_the_choice(tmp_path):
    examples = synthetic_examples()
    altered = [
        row | {"target_price_ars_per_l": row["target_price_ars_per_l"] * 5}
        if row["partition"] == "validation"
        else row
        for row in examples
    ]
    original = train_price_models(
        write_dataset(tmp_path / "d1", examples), tmp_path / "a", SELECTION
    )
    changed = train_price_models(write_dataset(tmp_path / "d2", altered), tmp_path / "b", SELECTION)
    assert original["report"]["selection"] == changed["report"]["selection"]
    assert original["report"]["chosen_method"] == changed["report"]["chosen_method"]
    assert original["report"]["validation"] != changed["report"]["validation"]


@pytest.mark.parametrize(
    "selection,message",
    [
        (datetime(2027, 1, 1, tzinfo=UTC), "vacía"),
        (datetime(2025, 1, 1), "zona horaria"),
    ],
)
def test_invalid_selection_is_rejected(tmp_path, selection, message):
    dataset = write_dataset(tmp_path / "dataset", synthetic_examples())
    with pytest.raises(ValueError, match=message):
        train_price_models(dataset, tmp_path / "out", selection)


def test_tampered_dataset_and_existing_output_are_rejected(tmp_path):
    dataset = write_dataset(tmp_path / "dataset", synthetic_examples())
    (tmp_path / "out").mkdir()
    with pytest.raises(ValueError, match="nuevo"):
        train_price_models(dataset, tmp_path / "out", SELECTION)
    with (dataset / "examples.jsonl").open("ab") as raw:
        raw.write(b"\n")
    with pytest.raises(ValueError, match="hash"):
        train_price_models(dataset, tmp_path / "other", SELECTION)


def test_cli_summarizes_and_hides_errors(tmp_path, capsys):
    dataset = write_dataset(tmp_path / "dataset", synthetic_examples())
    assert main(["--dataset", str(dataset), "--output", str(tmp_path / "out")]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["chosen_method"] in summary["selection_mae_ars_per_l"]
    assert len(summary["artifact_sha256"]) == 64
    assert main(["--dataset", str(tmp_path / "missing"), "--output", str(tmp_path / "x")]) == 2
    assert "Entrenamiento fallido" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        main(["--seed", "uno"])


def test_frame_handles_missing_previous_values_as_numbers():
    when = datetime(2025, 3, 1, tzinfo=UTC)
    frame = examples_frame([example(1, 1, when, 100, 100), example(2, 2, when, 100, 100)])
    assert pd.api.types.is_float_dtype(frame.previous_relative)
