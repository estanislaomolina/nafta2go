"""Publicaciones sintéticas controladas: ninguna métrica representa calidad real."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest

from nafta2go.ml.temporal import build_temporal_dataset

START = datetime(2026, 1, 1, 12)
CUTOFF = datetime(2026, 1, 3, tzinfo=UTC)


def row(station, day, price, **options):
    return {
        "station_id": station,
        "source_row": station * 100 + day,
        "valid_from": START + timedelta(days=day),
        "product_id": 2,
        "schedule_id": 2,
        "lat": -34.60,
        "lon": -58.40,
        "price": price,
        "brand": "PRUEBA",
        **options,
    }


def history():
    return [
        row(1, 0, 100),
        row(2, 0, 110),
        row(3, 0, 120),
        row(1, 1, 125),
        row(4, 1, 135),
        row(1, 2, 150),
    ]


def test_same_time_targets_never_enter_each_others_features():
    examples, report = build_temporal_dataset(history(), CUTOFF, min_history=3)
    assert len(examples) == 3
    assert examples[0]["features"]["prior_median"] == examples[1]["features"]["prior_median"] == 110
    assert examples[0]["features"]["prior_count"] == examples[1]["features"]["prior_count"] == 3
    assert examples[0]["features"]["previous_station_price"] == 100
    assert examples[0]["features"]["previous_station_age_days"] == 1
    assert examples[1]["features"]["previous_station_price"] is None
    assert report["partitions"]["train"]["abstained"] == 3
    assert examples[-1]["partition"] == "validation"


def test_future_and_target_prices_do_not_change_past_or_same_time_features():
    original = history()
    baseline, _ = build_temporal_dataset(original, CUTOFF, min_history=3)
    changed = deepcopy(original)
    changed[3]["price"], changed[-1]["price"] = 99999, 88888
    result, _ = build_temporal_dataset(changed, CUTOFF, min_history=3)
    assert [r["features"] for r in result[:2]] == [r["features"] for r in baseline[:2]]
    assert result[0]["target_price_ars_per_l"] != baseline[0]["target_price_ars_per_l"]
    assert result[-1]["features"] != baseline[-1]["features"]
    shuffled, report = build_temporal_dataset(list(reversed(original)), CUTOFF, min_history=3)
    assert shuffled == baseline
    assert report["partitions"]["validation"]["baseline_mae_ars_per_l"] == 30


def test_window_expires_old_prices_and_falls_back_to_caba():
    rows = history()[:3] + [row(4, 1, 140, lat=-34.56), row(5, 31, 150)]
    examples, report = build_temporal_dataset(rows, CUTOFF, min_history=3, window_days=1)
    assert len(examples) == 1 and examples[0]["baseline_scope"] == "caba"
    assert report["partitions"]["validation"]["examples"] == 0
    assert report["partitions"]["validation"]["baseline_mae_ars_per_l"] is None


def test_products_and_schedules_do_not_share_prices_and_coordinates_are_filtered():
    rows = history()[:3] + [
        row(4, 1, 200, product_id=3),
        row(5, 1, 250, schedule_id=3),
        row(6, 1, 300, lat=None),
        row(7, 1, 350, lon=-60),
    ]
    examples, report = build_temporal_dataset(rows, CUTOFF, min_history=3)
    assert examples == [] and report["excluded_geometry_or_product"] == 2


def test_partition_boundary_is_instant_accurate_and_not_random():
    boundary = (START + timedelta(days=1)).replace(tzinfo=UTC) + timedelta(hours=3)
    examples, _ = build_temporal_dataset(history(), boundary, min_history=3)
    assert all(row["partition"] == "validation" for row in examples)
    assert "alertas" not in examples[0]["features"]


@pytest.mark.parametrize("options", [{"window_days": 0}, {"window_days": True}, {"min_history": 2}])
def test_invalid_parameters_are_rejected(options):
    with pytest.raises(ValueError):
        build_temporal_dataset([], CUTOFF, **options)


def test_bad_dates_duplicates_or_targets_are_rejected():
    for rows, cutoff in [
        (history(), CUTOFF.replace(tzinfo=None)),
        ([row(1, 0, 100, valid_from=START.replace(tzinfo=UTC))], CUTOFF),
        ([row(1, 0, 100), row(1, 0, 110)], CUTOFF),
        ([row(1, 0, float("nan"))], CUTOFF),
    ]:
        with pytest.raises(ValueError):
            build_temporal_dataset(rows, cutoff)
