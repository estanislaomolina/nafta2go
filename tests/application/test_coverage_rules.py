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
    assert reference.astimezone(UTC).isoformat() == "2026-10-24T21:00:00+00:00"


@pytest.mark.parametrize(
    "value", ["", "0", "31", "-1", "14.0", "True", "١", " 14", "secreto", "10000"]
)
def test_invalid_environment_policy_is_rejected_without_echo(monkeypatch, value):
    monkeypatch.setenv("NAFTA2GO_MAX_PRICE_AGE_DAYS", value)
    with pytest.raises(coverage_rules.CoverageConfigurationError, match="entero") as caught:
        coverage_rules.configured_max_price_age_days()
    assert "secreto" not in str(caught.value)


@pytest.mark.parametrize("value", [1, 14, 30])
def test_environment_policy_has_closed_bounds(monkeypatch, value):
    monkeypatch.setenv("NAFTA2GO_MAX_PRICE_AGE_DAYS", str(value))
    assert coverage_rules.configured_max_price_age_days() == value


def test_missing_policy_keeps_thirty_day_default(monkeypatch):
    monkeypatch.delenv("NAFTA2GO_MAX_PRICE_AGE_DAYS", raising=False)
    assert coverage_rules.configured_max_price_age_days() == 30
