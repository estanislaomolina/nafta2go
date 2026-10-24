"""Pruebas de conexión entre matriz y motor, sin red ni precios reales."""

from copy import deepcopy
from dataclasses import replace
from decimal import Decimal

import pytest

from nafta2go.adapters.routing import DistanceMatrix, Point, ProviderTimeout, ProviderUnavailable
from nafta2go.application.recommendation import Candidate, evaluate_stations, route_from_matrix
from nafta2go.domain.engine import DiscardReason, FuelRequest

ORIGIN = Point(lat=-34.60, lon=-58.38)
DESTINATION = Point(lat=-34.56, lon=-58.45)
STATIONS = [Point(lat=-34.61, lon=-58.39), Point(lat=-34.62, lon=-58.40)]
REQUEST = FuelRequest(10, 50, 10, 12000, 2)
CANDIDATES = [
    Candidate("a", STATIONS[0], Decimal(1200)),
    Candidate("b", STATIONS[1], Decimal(1500)),
]


@pytest.fixture
def matrix():
    return DistanceMatrix(
        durations_s=[[900, 1200, 1800], [0, 999, 1500], [999, 0, 900]],
        distances_m=[[10000, 20000, 25000], [0, 999, 20000], [999, 0, 10000]],
        sources=[ORIGIN, *STATIONS],
        destinations=[*STATIONS, DESTINATION],
    )


class FakeProvider:
    def __init__(self, matrix):
        self.result = matrix
        self.calls = []

    def matrix(self, sources, destinations):
        self.calls.append((list(sources), list(destinations)))
        return self.result


def test_conversion_uses_correct_cells_and_units(matrix):
    route = route_from_matrix(matrix, 0, has_destination=True)
    assert route.to_station_km == 10
    assert route.after_station_km == 20
    assert route.to_station_min == 15
    assert route.after_station_min == 25
    assert route.direct_km == 25
    assert route.direct_min == 30
    assert matrix.distances_m[0][0] == 10000  # no modifica la respuesta


def test_fractional_units_are_preserved(matrix):
    matrix.distances_m[0][0] = 1234.5
    matrix.durations_s[0][0] = 90
    route = route_from_matrix(matrix, 0, has_destination=True)
    assert route.to_station_km == Decimal("1.2345")
    assert route.to_station_min == Decimal("1.5")


def test_two_stations_use_one_request_and_keep_price_identity(matrix):
    provider = FakeProvider(matrix)
    results = evaluate_stations(REQUEST, CANDIDATES, ORIGIN, DESTINATION, provider)
    assert provider.calls == [([ORIGIN, *STATIONS], [*STATIONS, DESTINATION])]
    assert [result.candidate.station_id for result in results] == ["a", "b"]
    assert all(result.evaluation.feasible for result in results)
    assert results[0].evaluation.metrics.purchased_l == 10
    assert results[0].evaluation.metrics.final_l == 17
    assert results[0].evaluation.metrics.extra_min == 10
    assert results[1].evaluation.metrics.purchased_l == 8
    assert results[1].evaluation.metrics.final_l == 15
    assert results[1].evaluation.metrics.extra_min == 5


@pytest.mark.parametrize(
    "table,row,col",
    [
        ("distances_m", 0, 0),
        ("durations_s", 0, 0),
        ("distances_m", 1, 2),
        ("durations_s", 1, 2),
    ],
)
def test_missing_leg_discards_only_affected_station(matrix, table, row, col):
    getattr(matrix, table)[row][col] = None
    results = evaluate_stations(REQUEST, CANDIDATES, ORIGIN, DESTINATION, FakeProvider(matrix))
    assert results[0].evaluation.reasons == (DiscardReason.ROUTE_UNAVAILABLE,)
    assert results[0].evaluation.metrics is None
    assert results[1].evaluation.feasible


@pytest.mark.parametrize("table", ["distances_m", "durations_s"])
def test_missing_direct_reference_discards_all_stations(matrix, table):
    getattr(matrix, table)[0][-1] = None
    results = evaluate_stations(REQUEST, CANDIDATES, ORIGIN, DESTINATION, FakeProvider(matrix))
    assert all(item.evaluation.reasons == (DiscardReason.ROUTE_UNAVAILABLE,) for item in results)


def test_unused_null_cell_does_not_discard_station(matrix):
    matrix.distances_m[1][1] = None
    matrix.durations_s[1][1] = None
    results = evaluate_stations(REQUEST, CANDIDATES, ORIGIN, DESTINATION, FakeProvider(matrix))
    assert all(item.evaluation.feasible for item in results)


def test_round_trip_has_zero_reference_and_asymmetric_return(matrix):
    matrix.destinations[-1] = ORIGIN
    matrix.distances_m[0][-1] = None
    matrix.durations_s[0][-1] = None
    provider = FakeProvider(matrix)
    results = evaluate_stations(REQUEST, CANDIDATES, ORIGIN, None, provider)
    assert provider.calls == [([ORIGIN, *STATIONS], [*STATIONS, ORIGIN])]
    assert results[0].evaluation.metrics.extra_km == 30
    assert results[0].evaluation.metrics.extra_min == 40
    assert results[0].evaluation.feasible


def test_empty_candidates_do_not_call_provider(matrix):
    provider = FakeProvider(matrix)
    assert evaluate_stations(REQUEST, [], ORIGIN, DESTINATION, provider) == ()
    assert provider.calls == []


def test_more_than_ten_candidates_do_not_call_provider(matrix):
    provider = FakeProvider(matrix)
    with pytest.raises(ValueError, match="hasta diez"):
        evaluate_stations(REQUEST, CANDIDATES * 6, ORIGIN, DESTINATION, provider)
    assert provider.calls == []


def test_exactly_ten_candidates_are_evaluated_in_one_call():
    locations = [Point(lat=-34.60 - index * 0.001, lon=-58.40) for index in range(10)]
    candidates = [
        Candidate(str(index), point, Decimal(1200)) for index, point in enumerate(locations)
    ]
    matrix = DistanceMatrix(
        durations_s=[[60] * 11 for _ in range(11)],
        distances_m=[[1000] * 11 for _ in range(11)],
        sources=[ORIGIN, *locations],
        destinations=[*locations, DESTINATION],
    )
    provider = FakeProvider(matrix)
    results = evaluate_stations(REQUEST, candidates, ORIGIN, DESTINATION, provider)
    assert len(results) == 10
    assert len(provider.calls) == 1
    assert all(result.evaluation.feasible for result in results)


def test_domain_discard_is_preserved(matrix):
    request = replace(REQUEST, remaining_l=0)
    results = evaluate_stations(request, CANDIDATES, ORIGIN, DESTINATION, FakeProvider(matrix))
    assert all(item.evaluation.reasons == (DiscardReason.STATION_UNREACHABLE,) for item in results)


def test_provider_failure_is_not_reported_as_no_stations():
    class UnavailableProvider:
        def matrix(self, sources, destinations):
            raise ProviderTimeout("sin respuesta")

    with pytest.raises(ProviderTimeout):
        evaluate_stations(REQUEST, CANDIDATES, ORIGIN, DESTINATION, UnavailableProvider())


@pytest.mark.parametrize("index", [-1, 2, True, 0.5])
def test_invalid_station_index(matrix, index):
    with pytest.raises(ValueError, match="station_index"):
        route_from_matrix(matrix, index, has_destination=True)


def test_malformed_matrix_is_rejected(matrix):
    matrix.distances_m.pop()
    with pytest.raises(ProviderUnavailable, match="contrato"):
        route_from_matrix(matrix, 0, has_destination=True)


def test_wrong_station_order_is_rejected(matrix):
    matrix.sources[1:] = reversed(STATIONS)
    with pytest.raises(ProviderUnavailable):
        evaluate_stations(REQUEST, CANDIDATES, ORIGIN, DESTINATION, FakeProvider(matrix))


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf"), True, "1000"])
def test_invalid_provider_distance_is_rejected(matrix, value):
    matrix.distances_m[0][0] = value
    with pytest.raises(ProviderUnavailable):
        route_from_matrix(matrix, 0, has_destination=True)


def test_repeated_evaluation_is_deterministic(matrix):
    before = deepcopy(matrix)
    first = evaluate_stations(REQUEST, CANDIDATES, ORIGIN, DESTINATION, FakeProvider(matrix))
    second = evaluate_stations(REQUEST, CANDIDATES, ORIGIN, DESTINATION, FakeProvider(matrix))
    assert first == second
    assert matrix == before
