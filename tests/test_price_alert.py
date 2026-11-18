from decimal import Decimal

import pytest

from nafta2go.domain.price_alert import RULE_VERSION, THRESHOLDS, deviation


def test_rule_uses_audited_thresholds():
    assert RULE_VERSION == "conservative-v1"
    assert THRESHOLDS == {
        2: Decimal("0.05424409844299347"),
        3: Decimal("0.054570259208731244"),
    }


def test_deviation_is_relative_to_reference():
    result = deviation(Decimal("1100"), Decimal("1000"), 2)
    assert result.relative == Decimal("0.1")
    assert result.threshold == THRESHOLDS[2]
    assert result.above is True


def test_equal_to_threshold_is_not_above():
    official = Decimal("1000") * (1 + THRESHOLDS[2])
    assert deviation(official, Decimal("1000"), 2).above is False


@pytest.mark.parametrize(
    ("official", "above"),
    [("1030", False), ("970", False), ("1060", True), ("940", True)],
)
def test_threshold_applies_in_both_directions(official, above):
    assert deviation(Decimal(official), Decimal("1000"), 2).above is above


def test_premium_uses_its_threshold():
    assert deviation(Decimal("1000"), Decimal("1000"), 3).threshold == THRESHOLDS[3]


@pytest.mark.parametrize(
    ("official", "reference", "product_id"),
    [
        ("1000", "0", 2),
        ("-1", "1000", 2),
        ("NaN", "1000", 2),
        ("1000", "Infinity", 2),
        ("1000", "1000", 4),
    ],
)
def test_invalid_inputs_raise(official, reference, product_id):
    with pytest.raises(ValueError):
        deviation(Decimal(official), Decimal(reference), product_id)
