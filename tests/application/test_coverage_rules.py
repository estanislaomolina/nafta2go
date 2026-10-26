"""Los parámetros de cobertura viven en un solo módulo y las funciones los toman de ahí."""

import inspect
from datetime import UTC

import pytest

from nafta2go.application import coverage_rules
from nafta2go.application.stored_query import (
    evaluate_from_database,
    select_candidates,
    select_stored_candidates,
)


@pytest.mark.parametrize(
    "function", [select_candidates, select_stored_candidates, evaluate_from_database]
)
@pytest.mark.parametrize(
    ("parameter", "constant"),
    [
        ("max_age_days", "MAX_PRICE_AGE_DAYS"),
        ("minimum_candidates", "MIN_RECENT_CANDIDATES"),
        ("max_detour_km", "MAX_DETOUR_KM"),
    ],
)
def test_defaults_come_from_coverage_rules(function, parameter, constant):
    default = inspect.signature(function).parameters[parameter].default
    assert default == getattr(coverage_rules, constant)


def test_decided_values():
    assert coverage_rules.MAX_PRICE_AGE_DAYS == 30
    assert coverage_rules.MIN_RECENT_CANDIDATES == 3
    assert coverage_rules.MAX_DETOUR_KM == 5.0


def test_scenario_reference_has_timezone():
    reference = coverage_rules.HISTORICAL_SCENARIO_REFERENCE_AT
    assert reference.utcoffset() is not None
    assert reference.astimezone(UTC).isoformat() == "2026-10-24T20:30:00+00:00"
