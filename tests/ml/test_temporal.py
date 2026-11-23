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


def test_recent_market_and_brand_use_only_the_previous_week():
    rows = [
        row(1, 0, 100, brand="YPF"),
        row(2, 0, 110, brand="AXION"),
        row(3, 0, 120, brand="YPF"),
        row(4, 6, 140, brand="YPF"),
        row(5, 9, 160, brand="YPF"),  # objetivo: el día 0 quedó fuera de los 7 días
        row(6, 9, 999, brand="YPF"),  # mismo instante: no entra en las features del otro
    ]
    examples, _ = build_temporal_dataset(rows, CUTOFF, min_history=3, window_days=30)
    target = next(r for r in examples if r["station_id"] == 5)["features"]
    assert (target["recent_median"], target["recent_count"]) == (140, 1)
    assert (target["brand_recent_median"], target["brand_recent_count"]) == (140, 1)
    early = next(r for r in examples if r["station_id"] == 4)["features"]
    assert early["recent_median"] == 110 and early["recent_count"] == 3
    assert early["brand_recent_median"] == 110 and early["brand_recent_count"] == 2


def test_recent_features_are_empty_without_recent_publications():
    rows = history()[:3] + [row(4, 20, 130)]
    examples, _ = build_temporal_dataset(rows, CUTOFF, min_history=3, window_days=30)
    features = examples[0]["features"]
    assert features["recent_median"] is None and features["recent_count"] == 0
    assert features["brand_recent_median"] is None


def test_probe_batch_matches_individual_preparation_without_query_price_leakage():
    original = history() + [row(2, 2, 330), row(1, 3, 500), row(99, 9, 99999)]
    targets = [
        row(1, 1, 10000, source_row=9001),
        row(2, 2, 999999, source_row=9002),
        row(1, 3, 777, source_row=9003),
    ]
    snapshot = deepcopy((original, targets))
    batch, report = build_temporal_dataset(original, CUTOFF, targets=targets, min_history=3)
    expected = []
    for target in targets:
        past = [r for r in original if r["valid_from"] < target["valid_from"]]
        examples, _ = build_temporal_dataset([*past, target], CUTOFF, min_history=3)
        expected.append(next(e for e in examples if e["source_row"] == target["source_row"]))
    assert batch == expected
    assert sum(p["observations"] for p in report["partitions"].values()) == 3
    assert (original, targets) == snapshot
    targets[0]["price"] = 9999999999
    changed, _ = build_temporal_dataset(original, CUTOFF, targets=targets, min_history=3)
    assert [r["features"] for r in changed] == [r["features"] for r in batch]


def test_probe_batch_preserves_products_schedules_and_abstention():
    context = history()[:3] + [row(20 + i, 0, 400 + i, product_id=3) for i in range(3)]
    targets = [row(7, 1, 150), row(8, 1, 450, product_id=3), row(9, 1, 300, schedule_id=3)]
    examples, _ = build_temporal_dataset(context, CUTOFF, targets=targets, min_history=3)
    assert [e["station_id"] for e in examples] == [7, 8]
    assert [e["features"]["prior_median"] for e in examples] == [110, 401]
    with pytest.raises(ValueError, match="duplicada"):
        build_temporal_dataset(context, CUTOFF, targets=[targets[0], targets[0]], min_history=3)
