"""Regresiones de #34: entradas precisas y límites físicos/económicos exactos."""

from dataclasses import fields, replace
from decimal import Decimal, localcontext
from fractions import Fraction

import pytest

from nafta2go.domain.engine import DiscardReason, FuelRequest, Route, evaluate_candidate

REQUEST = FuelRequest(10, 50, 10, 12000, 2)
ZERO_ROUTE = Route(0, 0, 0, 0, 0, 0)
TOO_PRECISE = Decimal("1.0000000000000000000000000001")


def test_original_issue_rejects_budget_instead_of_approving_rounded_reserve():
    budget = Decimal("1199.9999999999999999999999999")
    with pytest.raises(ValueError, match="budget_ars.*28"):
        FuelRequest(10, 50, 1, budget, 2)


@pytest.mark.parametrize("field", [item.name for item in fields(FuelRequest)])
def test_excess_precision_is_rejected_for_each_request_field(field):
    with pytest.raises(ValueError, match=field + ".*28"):
        replace(REQUEST, **{field: TOO_PRECISE})


@pytest.mark.parametrize("field", [item.name for item in fields(Route)])
def test_excess_precision_is_rejected_for_each_route_field(field):
    with pytest.raises(ValueError, match=field + ".*28"):
        replace(ZERO_ROUTE, **{field: TOO_PRECISE})


def test_excess_precision_in_price_is_rejected_even_when_route_is_missing():
    with pytest.raises(ValueError, match="price_ars_per_l.*28"):
        evaluate_candidate(REQUEST, TOO_PRECISE, None)


def test_28_digit_budget_does_not_reach_reserve_by_rounding():
    budget = Decimal("1199." + "9" * 24)
    request = FuelRequest(10, 50, 1, budget, 2)
    result = evaluate_candidate(request, 1200, ZERO_ROUTE)
    actual_final = Fraction(1) + Fraction(result.metrics.purchased_l)
    assert actual_final < 2
    assert not result.feasible
    assert result.reasons == (DiscardReason.INSUFFICIENT_FUEL_FOR_TRIP,)
    assert Fraction(result.metrics.purchased_l) * 1200 <= Fraction(budget)


def test_exact_reserve_boundary_is_still_feasible():
    request = FuelRequest(10, 50, 1, 1200, 2)
    assert evaluate_candidate(request, 1200, ZERO_ROUTE).feasible


def test_arrival_below_reserve_is_not_rounded_into_feasibility():
    request = FuelRequest(3, 50, 3, 1200, 2)
    route = Route("33.33333333333333333333333334", 0, 0, 0, 0, 0)
    result = evaluate_candidate(request, 1200, route)
    assert result.reasons == (DiscardReason.RESERVE_AT_STATION,)


def test_unreachable_station_is_not_rounded_into_reachability():
    request = FuelRequest(3, 50, 1, 1200, 0)
    route = Route("33.33333333333333333333333334", 0, 0, 0, 0, 0)
    result = evaluate_candidate(request, 1200, route)
    assert result.reasons == (DiscardReason.STATION_UNREACHABLE,)


def test_final_reserve_uses_exact_trip_consumption():
    request = FuelRequest(3, 50, 3, 1200, 3)
    route = Route(0, "33.33333333333333333333333334", 0, 0, 0, 0)
    result = evaluate_candidate(request, 1200, route)
    assert result.reasons == (DiscardReason.INSUFFICIENT_FUEL_FOR_TRIP,)
    assert Fraction(4) - Fraction(route.after_station_km) * Fraction(3, 100) < 3


@pytest.mark.parametrize(
    "consumption,distance",
    [
        ("12.34567890123456789012345678", "1.234567890123456789012345678"),
        ("9.876543210987654321098765432", "1.987654321098765432109876543"),
        ("1.000000000000000000000000009", "1.000000000000000000000000009"),
    ],
)
def test_exact_arrival_and_purchase_do_not_overfill_tank(consumption, distance):
    request = FuelRequest(consumption, 50, 10, 1000000, 0)
    route = Route(distance, 0, 0, 0, 0, 0)
    result = evaluate_candidate(request, 1200, route)
    exact_arrival = (
        Fraction(request.remaining_l)
        - Fraction(request.consumption_l_per_100km) * Fraction(route.to_station_km) / 100
    )
    assert result.feasible
    assert exact_arrival + Fraction(result.metrics.purchased_l) <= request.tank_capacity_l
    assert Fraction(result.metrics.purchased_l) * 1200 <= request.budget_ars


def test_precision_policy_is_independent_of_caller_context():
    with localcontext() as context:
        context.prec = 4
        with pytest.raises(ValueError, match="budget_ars.*28"):
            replace(REQUEST, budget_ars=TOO_PRECISE)
        result = evaluate_candidate(FuelRequest(10, 50, 1, 1200, 2), 1200, ZERO_ROUTE)
        assert result.feasible


def test_zero_exponents_do_not_require_extreme_scale_arithmetic():
    request = replace(REQUEST, reserve_l=Decimal("0e-999999"))
    assert evaluate_candidate(request, 1200, ZERO_ROUTE).feasible
