"""Tests del corredor en línea recta alrededor del recorrido."""

import pytest

from nafta2go.adapters.routing import Point
from nafta2go.application.corridor import haversine_km, straight_detour_km

OBELISCO = Point(-34.6037, -58.3816)
CABILDO = Point(-34.5627, -58.4565)


def test_haversine_obelisco_cabildo():
    assert haversine_km(OBELISCO, CABILDO) == pytest.approx(8.23, abs=0.01)


def test_haversine_is_symmetric_and_zero_on_same_point():
    assert haversine_km(OBELISCO, CABILDO) == pytest.approx(haversine_km(CABILDO, OBELISCO))
    assert haversine_km(OBELISCO, OBELISCO) == 0


def test_one_degree_of_latitude_is_about_111_km():
    assert haversine_km(Point(-34.0, -58.4), Point(-35.0, -58.4)) == pytest.approx(111.2, abs=0.1)


def test_station_on_the_segment_has_no_detour():
    middle = Point((OBELISCO.lat + CABILDO.lat) / 2, (OBELISCO.lon + CABILDO.lon) / 2)
    assert straight_detour_km(OBELISCO, middle, CABILDO) == pytest.approx(0, abs=0.01)


def test_detour_adds_the_extra_distance():
    # Ir y volver hasta el Obelisco desde Cabildo equivale a recorrer dos veces el tramo.
    assert straight_detour_km(CABILDO, OBELISCO, CABILDO) == pytest.approx(2 * 8.23, abs=0.02)


def test_without_destination_detour_is_distance_from_origin():
    assert straight_detour_km(OBELISCO, CABILDO, None) == pytest.approx(8.23, abs=0.01)


def test_detour_is_never_negative():
    assert straight_detour_km(OBELISCO, OBELISCO, CABILDO) >= 0
