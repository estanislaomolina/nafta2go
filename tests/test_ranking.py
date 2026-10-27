"""Prioridades de RF06 con resultados calculados por el motor."""

from dataclasses import replace
from decimal import Decimal

from nafta2go.domain.engine import Evaluation, FuelRequest, Route, evaluate_candidate
from nafta2go.domain.ranking import rank_alternatives


def evaluation(net, detour, minutes=0):
    result = evaluate_candidate(
        FuelRequest(10, 50, 10, 12000, 2), Decimal(1200), Route(1, 1, 1, 1, 1, 1)
    )
    return replace(
        result,
        metrics=replace(
            result.metrics,
            net_gain_l=Decimal(net),
            extra_km=Decimal(detour),
            extra_min=Decimal(minutes),
        ),
    )


def test_distinct_priorities_and_balanced_middle():
    ranked = rank_alternatives(
        {"a": evaluation(10, 10), "b": evaluation(0, 0), "c": evaluation(8, 2)}
    )
    assert [(r.station_id, r.priorities) for r in ranked] == [
        ("a", ("combustible_neto",)),
        ("b", ("menor_desvio",)),
        ("c", ("equilibrio",)),
    ]


def test_same_station_is_shown_once_with_all_priorities():
    ranked = rank_alternatives({"a": evaluation(10, 0), "b": evaluation(5, 2)})
    assert len(ranked) == 1
    assert ranked[0].station_id == "a"
    assert len(ranked[0].priorities) == 3


def test_ties_are_independent_of_input_order():
    rows = {"b": evaluation(10, 1), "a": evaluation(10, 1)}
    assert rank_alternatives(rows) == rank_alternatives(dict(reversed(list(rows.items()))))
    assert rank_alternatives(rows)[0].station_id == "a"


def test_discarded_stations_never_win():
    invalid = Evaluation(("route_unavailable",), None)
    assert rank_alternatives({"a": invalid}) == ()
    assert rank_alternatives({"a": invalid, "b": evaluation(1, 1)})[0].station_id == "b"


def test_less_time_breaks_equal_distance_tie():
    ranked = rank_alternatives({"a": evaluation(10, 1, 5), "b": evaluation(9, 1, 1)})
    assert next(r for r in ranked if "menor_desvio" in r.priorities).station_id == "b"
