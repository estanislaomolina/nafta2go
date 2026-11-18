"""Estimación rotulada de precios de 31 a 120 días (ADR-020), sin base ni red."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from nafta2go.adapters.routing import Point
from nafta2go.application.stale_price_estimate import (
    ESTIMATE_VERSION,
    MAX_AGE_DAYS,
    METHOD,
    brand_recent_median,
    estimate_stale_prices,
)
from nafta2go.ml.temporal import build_temporal_dataset

LOCAL = ZoneInfo("America/Argentina/Buenos_Aires")
NOW = datetime(2026, 10, 26, 12, tzinfo=UTC)
NOW_LOCAL = NOW.astimezone(LOCAL).replace(tzinfo=None)


def row(station_id, days_ago, price, brand="YPF", **overrides):
    values = {
        "id": station_id * 10,
        "source_row": station_id,
        "station_id": station_id,
        "company": f"EMPRESA {station_id}",
        "brand": brand,
        "address": f"CALLE {station_id}",
        "product_id": 2,
        "fuel_type": "super",
        "schedule_id": 2,
        "price": Decimal(str(price)),
        "valid_from": NOW_LOCAL - timedelta(days=days_ago),
        "lat": -34.60 - station_id * 0.001,
        "lon": -58.40,
        "alerts": "",
    }
    return values | overrides


def estimate(rows, **options):
    return estimate_stale_prices(
        rows, fuel_type="super", schedule_id=2, reference_at=NOW, **options
    )


def test_stale_station_gets_brand_median_in_separate_fields():
    rows = [row(1, 45, 1500), row(2, 1, 1700), row(3, 2, 1800), row(4, 3, 1900)]
    (item,) = estimate(rows)
    assert item.station_id == "1"
    assert item.official_price_ars_per_l == Decimal("1500")
    assert item.official_published_at_local == NOW_LOCAL - timedelta(days=45)
    assert item.official_age_days == 45
    assert item.estimate_ars_per_l == Decimal("1800.000")
    assert item.reference_count == 3
    assert item.reference_from_local == NOW_LOCAL - timedelta(days=7)
    assert item.reference_to_local == NOW_LOCAL
    assert (item.method, item.version) == (METHOD, ESTIMATE_VERSION)


@pytest.mark.parametrize(
    ("days_ago", "estimated"),
    [(29, False), (30, False), (30.5, True), (MAX_AGE_DAYS, True), (MAX_AGE_DAYS + 0.5, False)],
)
def test_only_ages_above_thirty_and_up_to_one_hundred_twenty_days(days_ago, estimated):
    rows = [row(1, days_ago, 1500), row(2, 1, 1700)]
    assert bool(estimate(rows)) is estimated


def test_configured_vigencia_above_thirty_days_is_not_estimated():
    rows = [row(1, 40, 1500), row(2, 1, 1700)]
    assert estimate(rows, max_age_days=45) == ()
    assert len(estimate(rows, max_age_days=35)) == 1


def test_abstains_without_recent_prices_of_the_same_brand():
    rows = [row(1, 45, 1500), row(2, 1, 1700, brand="SHELL C.A.P.S.A."), row(3, 8, 1650)]
    assert estimate(rows) == ()


def test_abstains_without_brand():
    rows = [row(1, 45, 1500, brand=""), row(2, 1, 1700, brand="")]
    assert estimate(rows) == ()


def test_station_with_a_newer_current_price_is_not_estimated():
    rows = [row(1, 45, 1500), row(1, 2, 1750, id=11, source_row=11), row(2, 1, 1700)]
    assert estimate(rows) == ()


def test_reference_ignores_other_products_schedules_and_outside_caba():
    rows = [
        row(1, 45, 1500),
        row(2, 1, 1700),
        row(3, 1, 9000, product_id=3, fuel_type="premium"),
        row(4, 1, 9000, schedule_id=3),
        row(5, 1, 9000, lat=-35.5),
    ]
    (item,) = estimate(rows)
    assert (item.estimate_ars_per_l, item.reference_count) == (Decimal("1700.000"), 1)


def test_corridor_applies_to_estimated_stations_but_not_to_the_brand_reference():
    far = row(1, 45, 1500, lat=-34.70, lon=-58.50)
    near = row(3, 45, 1500)
    reference = row(2, 1, 1700, lat=-34.70, lon=-58.52)
    origin, destination = Point(-34.60, -58.40), Point(-34.61, -58.40)
    items = estimate(
        [far, near, reference], origin=origin, destination=destination, max_detour_km=2
    )
    assert [item.station_id for item in items] == ["3"]
    assert items[0].reference_count == 1


def test_most_recent_official_prices_come_first_and_limit_applies():
    rows = [row(i, 30 + i * 10, 1500) for i in range(1, 6)] + [row(9, 1, 1700)]
    items = estimate(rows, limit=2)
    assert [item.station_id for item in items] == ["1", "2"]


def test_naive_reference_is_rejected():
    with pytest.raises(ValueError):
        estimate_stale_prices(
            [], fuel_type="super", schedule_id=2, reference_at=datetime(2026, 1, 1)
        )


def test_median_matches_the_feature_used_in_the_evaluation():
    history = [
        row(2, 6, 1650),
        row(3, 3, 1700),
        row(4, 2, 1810),
        row(5, 1, 1990),
        row(6, 20, 1200),
        row(7, 2, 9000, brand="AXION"),
    ]
    target = row(1, 0, 1777)
    examples, _ = build_temporal_dataset(
        [*history, target], NOW + timedelta(days=1), window_days=30, min_history=3
    )
    feature = next(e for e in examples if e["station_id"] == 1)["features"]
    value, count = brand_recent_median(history, "YPF", 2, 2, NOW_LOCAL)
    assert float(value) == pytest.approx(feature["brand_recent_median"])
    assert count == feature["brand_recent_count"]
