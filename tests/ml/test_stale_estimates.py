"""Reingresos sobre precios sintéticos: ninguna métrica representa calidad real (#57)."""

import json
import math
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from nafta2go.application.price_dataset import encoded, sha256
from nafta2go.application.stale_price_evaluation import (
    adjusted_last_price,
    evaluate_stale_estimates,
    stale_examples,
)
from nafta2go.ml.evaluate_stale import main
from nafta2go.ml.models import examples_frame
from nafta2go.ml.temporal import FEATURES_VERSION

START = datetime(2023, 1, 1, tzinfo=UTC)
CUTOFF = datetime(2026, 1, 1, 3, tzinfo=UTC)
SELECTION = datetime(2025, 1, 1, tzinfo=UTC)
END = datetime(2026, 6, 30, tzinfo=UTC)
METHODS = {"ultimo_precio", "ultimo_ajustado", "bandera_reciente", "mediana_previa"}
METHODS |= {"ridge", "boosting"}


def example(row, station, when, price, prior, previous=None, partition="train"):
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
            "brand": ("YPF", "AXION", "PUMA", "SHELL C.A.P.S.A.")[station % 4],
            "zone_lat": -1730,
            "zone_lon": -2920,
            "time_days": 0.0,
            "prior_median": prior,
            "prior_count": 10,
            "prior_iqr": 2.0,
            "previous_station_price": previous[1] if previous else None,
            "previous_station_age_days": previous[0] if previous else None,
            "recent_median": prior,
            "recent_count": 4,
            "brand_recent_median": prior,
            "brand_recent_count": 2,
        },
    }


def synthetic_rows(seed=5, stations=10):
    """Precios que siguen al mercado; cada estación tiene huecos de publicación."""
    rng = np.random.default_rng(seed)
    rows, number = [], 0
    for station in range(stations):
        offset = rng.uniform(-0.03, 0.03)
        when, previous = START + timedelta(days=station), None
        while when < END:
            prior = 100 * math.exp(0.002 * (when - START).days)
            price = round(prior * math.exp(offset + rng.normal(0, 0.004)), 2)
            number += 1
            age = (when - previous[0]).total_seconds() / 86400 if previous else None
            partition = "train" if when < CUTOFF else "validation"
            rows.append(
                example(
                    number,
                    station,
                    when,
                    price,
                    prior,
                    (age, previous[1]) if previous else None,
                    partition,
                )
            )
            previous = (when, price)
            if station == 0 and datetime(2025, 9, 1, tzinfo=UTC) <= when:
                step = 200 if when < CUTOFF else 4
            else:
                step = int(rng.choice([4] * 12 + [45, 90]))
            when += timedelta(days=step)
    return rows


def write_dataset(path, rows):
    path.mkdir()
    raw = b"".join(encoded(row) + b"\n" for row in rows)
    manifest = {
        "format_version": 1,
        "features_version": FEATURES_VERSION,
        "dataset_file": "examples.jsonl",
        "dataset_sha256": sha256(raw),
        "source_sha256": "a" * 64,
    }
    (path / "examples.jsonl").write_bytes(raw)
    (path / "manifest.json").write_bytes(encoded(manifest))
    return path


@pytest.fixture
def dataset(tmp_path):
    return write_dataset(tmp_path / "dataset", synthetic_rows())


def evaluate(dataset, output, **options):
    return evaluate_stale_estimates(dataset, output, SELECTION, min_examples=3, **options)


def test_exactly_thirty_days_is_not_stale():
    rows = [
        example(1, 1, START, 100.0, 100.0, (30.0, 99.0)),
        example(2, 2, START, 100.0, 100.0, (45.0, 99.0)),
    ]
    stale = stale_examples(examples_frame(rows), 30)
    assert stale.source_row.tolist() == [2]


def test_adjusted_last_price_applies_market_change():
    later = START + timedelta(days=45)
    rows = [
        example(1, 1, START, 1000.0, 1000.0),
        example(2, 1, later, 1100.0, 1100.0, (45.0, 1000.0)),
    ]
    frame = examples_frame(rows)
    predicted, fallbacks = adjusted_last_price(frame)
    assert frame.prior_median[1] * math.exp(predicted[1]) == pytest.approx(1100, abs=0.01)
    assert fallbacks == 0


def test_adjusted_last_price_falls_back_without_market_change():
    frame = examples_frame([example(1, 1, START, 1000.0, 1100.0, (45.0, 1000.0))])
    predicted, fallbacks = adjusted_last_price(frame)
    assert predicted[0] == pytest.approx(frame.reference[0])
    assert fallbacks == 1


def test_selection_uses_only_2025_and_validation_is_reported_after(dataset, tmp_path):
    first = evaluate(dataset, tmp_path / "first")
    assert first["chosen_method"] in first["selection"]
    rows = synthetic_rows()
    for row in rows:
        if row["partition"] == "validation":
            row["target_price_ars_per_l"] *= 1.5
    changed = write_dataset(tmp_path / "changed", rows)
    second = evaluate(changed, tmp_path / "second")
    assert second["chosen_method"] == first["chosen_method"]
    assert second["validation"] != first["validation"]


def test_buckets_without_support_abstain(dataset, tmp_path):
    rows = [r for r in synthetic_rows() if r["partition"] == "validation"]
    ages = [r["features"]["previous_station_age_days"] or 0 for r in rows]
    oldest = sum(age > 120 for age in ages)
    middle = sum(30 < age <= 60 for age in ages)
    assert 0 < oldest < middle
    report = evaluate_stale_estimates(dataset, tmp_path / "out", SELECTION, min_examples=oldest + 1)
    buckets = report["validation"]["segments"]
    assert buckets["mas_de_120"]["status"] == "insufficient_support"
    assert buckets["mas_de_120"]["methods"] is None
    assert buckets["31_a_60"]["status"] == "candidate"


def test_report_lists_every_method_per_bucket(dataset, tmp_path):
    report = evaluate(dataset, tmp_path / "out")
    assert set(report["selection"]) == METHODS
    for bucket in report["validation"]["segments"].values():
        if bucket["status"] == "candidate":
            assert set(bucket["methods"]) == METHODS
            assert {"mape", "p90_relative", "mae_ars_per_l"} <= set(bucket["methods"]["ridge"])


def test_adoption_check_compares_against_last_price(dataset, tmp_path):
    report = evaluate(dataset, tmp_path / "out")
    check = report["adoption_check"]
    assert set(check) == {
        "max_mape",
        "max_p90_relative",
        "beats_last_price_in_supported_segments",
        "adopt",
    }
    assert check["adopt"] == (
        check["max_mape"]
        and check["max_p90_relative"]
        and check["beats_last_price_in_supported_segments"]
    )
    strict = evaluate(dataset, tmp_path / "strict", max_mape=0.0)
    assert strict["adoption_check"]["adopt"] is False


def test_no_stale_examples_in_selection_fails(tmp_path):
    rows = [
        r
        for r in synthetic_rows()
        if not (
            SELECTION.isoformat() <= r["target_at_utc"] < CUTOFF.isoformat()
            and (r["features"]["previous_station_age_days"] or 0) > 30
        )
    ]
    with pytest.raises(ValueError, match="Sin reingresos"):
        evaluate(write_dataset(tmp_path / "dataset", rows), tmp_path / "out")


def test_report_is_reproducible_and_not_runtime(dataset, tmp_path):
    evaluate(dataset, tmp_path / "one")
    report = evaluate(dataset, tmp_path / "two")
    one = (tmp_path / "one" / "stale-evaluation.json").read_bytes()
    assert one == (tmp_path / "two" / "stale-evaluation.json").read_bytes()
    assert report["runtime_enabled"] is False
    assert (
        report["dataset_sha256"]
        == json.loads((dataset / "manifest.json").read_bytes())["dataset_sha256"]
    )


def test_existing_output_and_naive_dates_are_rejected(dataset, tmp_path):
    (tmp_path / "exists").mkdir()
    with pytest.raises(ValueError):
        evaluate(dataset, tmp_path / "exists")
    with pytest.raises(ValueError):
        evaluate_stale_estimates(dataset, tmp_path / "naive", datetime(2025, 1, 1))


@pytest.mark.parametrize(
    "options",
    [{"min_gap_days": 0}, {"min_gap_days": -5}, {"min_gap_days": True}, {"min_examples": 0}],
)
def test_non_positive_parameters_are_rejected(dataset, tmp_path, options):
    with pytest.raises(ValueError, match="entero positivo"):
        evaluate_stale_estimates(dataset, tmp_path / "out", SELECTION, **options)
    assert not (tmp_path / "out").exists()


def test_tampered_dataset_is_rejected(dataset, tmp_path):
    (dataset / "examples.jsonl").write_bytes(b"{}\n")
    with pytest.raises(ValueError, match="hash"):
        evaluate(dataset, tmp_path / "out")


def test_cli_hides_internal_errors(tmp_path, capsys):
    missing = tmp_path / "no-existe"
    code = main(
        [
            "--dataset",
            str(missing),
            "--output",
            str(tmp_path / "out"),
            "--selection-start",
            "2025-01-01T00:00:00-03:00",
        ]
    )
    assert code == 2
    assert str(missing) not in capsys.readouterr().err


def test_cli_prints_summary(dataset, tmp_path, capsys):
    code = main(
        [
            "--dataset",
            str(dataset),
            "--output",
            str(tmp_path / "out"),
            "--selection-start",
            "2025-01-01T00:00:00-03:00",
            "--min-examples",
            "3",
        ]
    )
    summary = json.loads(capsys.readouterr().out)
    assert code == 0
    assert summary["runtime_enabled"] is False
    assert "adoption_check" in summary
