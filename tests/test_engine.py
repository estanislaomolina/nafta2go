"""Casos de aceptación del motor: RF04 y RF05."""

import unittest
from dataclasses import replace
from decimal import Decimal as D
from decimal import localcontext

from nafta2go.domain.engine import DiscardReason as Reason
from nafta2go.domain.engine import FuelRequest, Route, evaluate_candidate


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.request = FuelRequest(10, 50, 10, 12000, 2)
        self.route = Route(10, 20, 15, 25, 25, 30)

    def evaluate(self, **changes):
        return evaluate_candidate(replace(self.request, **changes), 1200, self.route)

    def test_normal_trip_has_explainable_metrics(self):
        result = self.evaluate()
        self.assertTrue(result.feasible)
        metrics = result.metrics
        expected = dict(
            consumption_to_station_l=1,
            consumption_after_station_l=2,
            total_consumption_l=3,
            arrival_l=9,
            free_capacity_l=41,
            purchased_l=10,
            cost_ars=12000,
            final_l=17,
            net_gain_l=7,
            final_range_km=170,
            extra_km=5,
            extra_min=10,
        )
        for name, value in expected.items():
            with self.subTest(metric=name):
                self.assertEqual(getattr(metrics, name), D(value))

    def test_capacity_is_measured_after_driving_to_station(self):
        result = self.evaluate(remaining_l=50, budget_ars=120000)
        self.assertTrue(result.feasible)
        self.assertEqual(result.metrics.purchased_l, 1)
        self.assertEqual(result.metrics.cost_ars, 1200)
        self.assertEqual(result.metrics.final_l, 48)

    def test_unreachable_station_has_no_fabricated_metrics(self):
        result = self.evaluate(remaining_l="0.5")
        self.assertEqual(result.reasons, (Reason.STATION_UNREACHABLE,))
        self.assertIsNone(result.metrics)

    def test_reaching_station_below_reserve_is_rejected(self):
        result = self.evaluate(remaining_l="2.9")
        self.assertEqual(result.reasons, (Reason.RESERVE_AT_STATION,))

    def test_arrival_exactly_at_reserve_is_allowed(self):
        self.assertTrue(self.evaluate(remaining_l=3).feasible)

    def test_already_below_reserve_can_refuel_without_driving(self):
        request = replace(self.request, remaining_l=1)
        route = Route(0, 5, 0, 5, 5, 5)
        result = evaluate_candidate(request, 1200, route)
        self.assertTrue(result.feasible)
        self.assertEqual(result.metrics.final_l, D("10.5"))

    def test_already_below_reserve_cannot_spend_more_before_refueling(self):
        request = replace(self.request, remaining_l=1)
        route = Route(1, 5, 1, 5, 5, 5)
        result = evaluate_candidate(request, 1200, route)
        self.assertEqual(result.reasons, (Reason.RESERVE_AT_STATION,))

    def test_below_reserve_still_requires_final_reserve_after_refueling(self):
        request = replace(self.request, remaining_l=1, budget_ars=1200)
        route = Route(0, 5, 0, 5, 5, 5)
        result = evaluate_candidate(request, 1200, route)
        self.assertEqual(result.reasons, (Reason.INSUFFICIENT_FUEL_FOR_TRIP,))
        self.assertEqual(result.metrics.final_l, D("1.5"))

    def test_zero_fuel_at_station_can_restore_positive_reserve(self):
        request = replace(self.request, remaining_l=0)
        route = Route(0, 5, 0, 5, 5, 5)
        result = evaluate_candidate(request, 1200, route)
        self.assertTrue(result.feasible)
        self.assertEqual(result.metrics.final_l, D("9.5"))

    def test_final_reserve_exactly_met_is_allowed(self):
        result = self.evaluate(remaining_l=3, budget_ars=2400)
        self.assertTrue(result.feasible)
        self.assertEqual(result.metrics.final_l, 2)

    def test_budget_cannot_cover_remaining_trip(self):
        result = self.evaluate(remaining_l=3, budget_ars=1200)
        self.assertEqual(result.reasons, (Reason.INSUFFICIENT_FUEL_FOR_TRIP,))
        self.assertEqual(result.metrics.final_l, 1)

    def test_even_full_tank_cannot_complete_trip(self):
        route = replace(self.route, after_station_km=600)
        result = evaluate_candidate(self.request, 1200, route)
        self.assertIn(Reason.INSUFFICIENT_FUEL_FOR_TRIP, result.reasons)
        self.assertEqual(result.metrics.final_range_km, 0)

    def test_no_budget_is_explained_even_if_trip_is_reachable(self):
        self.assertEqual(self.evaluate(budget_ars=0).reasons, (Reason.NO_BUDGET,))

    def test_full_tank_at_station_has_no_space(self):
        route = replace(self.route, to_station_km=0, to_station_min=0)
        request = replace(self.request, remaining_l=50)
        result = evaluate_candidate(request, 1200, route)
        self.assertEqual(result.reasons, (Reason.NO_TANK_SPACE,))

    def test_multiple_discard_reasons_are_preserved(self):
        result = self.evaluate(remaining_l=3, budget_ars=0)
        self.assertEqual(result.reasons, (Reason.NO_BUDGET, Reason.INSUFFICIENT_FUEL_FOR_TRIP))

    def test_missing_route(self):
        result = evaluate_candidate(self.request, 1200, None)
        self.assertFalse(result.feasible)
        self.assertEqual(result.reasons, (Reason.ROUTE_UNAVAILABLE,))
        self.assertIsNone(result.metrics)

    def test_round_trip_without_destination(self):
        route = Route(10, 12, 15, 18, 0, 0)
        result = evaluate_candidate(self.request, 1200, route)
        self.assertEqual(result.metrics.extra_km, 22)
        self.assertEqual(result.metrics.extra_min, 33)
        self.assertEqual(result.metrics.final_l, D("17.8"))

    def test_shorter_route_does_not_produce_negative_detour(self):
        route = replace(self.route, direct_km=31, direct_min=41)
        result = evaluate_candidate(self.request, 1200, route)
        self.assertEqual(result.metrics.extra_km, 0)
        self.assertEqual(result.metrics.extra_min, 0)

    def test_zero_reserve_and_zero_initial_fuel_at_station(self):
        request = replace(self.request, remaining_l=0, reserve_l=0)
        route = Route(0, 0, 0, 0, 0, 0)
        self.assertTrue(evaluate_candidate(request, 1200, route).feasible)

    def test_invalid_request_numbers(self):
        for name in (
            "consumption_l_per_100km",
            "tank_capacity_l",
            "remaining_l",
            "budget_ars",
            "reserve_l",
        ):
            for value in (-1, "NaN", "Infinity", float("nan"), None, True, "abc"):
                with (
                    self.subTest(field=name, value=value),
                    self.assertRaisesRegex(ValueError, name),
                ):
                    replace(self.request, **{name: value})

    def test_impossible_request_values(self):
        for changes in (
            dict(consumption_l_per_100km=0),
            dict(tank_capacity_l=0),
            dict(remaining_l=51),
            dict(reserve_l=51),
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(self.request, **changes)

    def test_extreme_request_magnitudes_are_rejected_with_field_name(self):
        for name in (
            "consumption_l_per_100km",
            "tank_capacity_l",
            "remaining_l",
            "budget_ars",
            "reserve_l",
        ):
            for value in ("1e-999999", "1e999999", "1e-13", "1e13"):
                with (
                    self.subTest(field=name, value=value),
                    self.assertRaisesRegex(ValueError, name),
                ):
                    replace(self.request, **{name: value})

    def test_extreme_route_magnitudes_are_rejected_with_field_name(self):
        for name in (
            "to_station_km",
            "after_station_km",
            "to_station_min",
            "after_station_min",
            "direct_km",
            "direct_min",
        ):
            for value in ("1e-999999", "1e999999"):
                with (
                    self.subTest(field=name, value=value),
                    self.assertRaisesRegex(ValueError, name),
                ):
                    replace(self.route, **{name: value})

    def test_extreme_price_magnitudes_are_rejected_with_field_name(self):
        for value in ("1e-999999", "1e999999"):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "price_ars_per_l"):
                evaluate_candidate(self.request, value, self.route)

    def test_invalid_route_numbers(self):
        for name in (
            "to_station_km",
            "after_station_km",
            "to_station_min",
            "after_station_min",
            "direct_km",
            "direct_min",
        ):
            for value in (-1, "Infinity", "NaN", None, False, "abc"):
                with (
                    self.subTest(field=name, value=value),
                    self.assertRaisesRegex(ValueError, name),
                ):
                    replace(self.route, **{name: value})

    def test_invalid_price_is_contract_error(self):
        for price in (0, -1, "NaN", "Infinity", True, None, "abc"):
            with self.subTest(price=price), self.assertRaisesRegex(ValueError, "price_ars_per_l"):
                evaluate_candidate(self.request, price, self.route)

    def test_numeric_inputs_are_normalized(self):
        request = FuelRequest("10", 50.0, D("10"), "12000", 2)
        self.assertEqual(evaluate_candidate(request, "1200", self.route), self.evaluate())

    def test_caller_precision_does_not_change_result(self):
        expected = self.evaluate()
        with localcontext() as context:
            context.prec = 4
            self.assertEqual(self.evaluate(), expected)

    def test_caller_exponent_limits_do_not_change_result(self):
        expected = self.evaluate()
        with localcontext() as context:
            context.Emax = 3
            context.Emin = -3
            self.assertEqual(self.evaluate(), expected)

    def test_budget_and_tank_constraints_across_scenarios(self):
        for budget in (1, 2, 10, 12000, 1000000):
            for price in (3, 7, 1200, "1234.56"):
                with self.subTest(budget=budget, price=price):
                    request = replace(self.request, budget_ars=budget)
                    result = evaluate_candidate(request, price, self.route)
                    metrics = result.metrics
                    self.assertLessEqual(metrics.cost_ars, budget)
                    self.assertLessEqual(
                        metrics.arrival_l + metrics.purchased_l, request.tank_capacity_l
                    )
                    self.assertGreaterEqual(metrics.purchased_l, 0)
                    if result.feasible:
                        self.assertGreaterEqual(metrics.final_l, request.reserve_l)


if __name__ == "__main__":
    unittest.main()
