"""Enlaces a estaciones públicas sin red ni ubicaciones del conductor."""

from copy import deepcopy
from urllib.parse import parse_qs, urlsplit

import pytest

from nafta2go.presentation.navigation import NOTICE, google_maps_url, present_recommendation


@pytest.mark.parametrize(
    "lat,lon", [(-34.6037, -58.3816), (90, 180), (-90, -180), (0, 0), (1e-7, -2e-7)]
)
def test_maps_url_encodes_only_a_station_destination(lat, lon):
    url = google_maps_url(lat, lon)
    split = urlsplit(url)
    query = parse_qs(split.query)
    assert (split.scheme, split.netloc, split.path) == ("https", "www.google.com", "/maps/dir/")
    assert set(query) == {"api", "destination", "travelmode", "dir_action"}
    assert query["api"] == ["1"] and query["travelmode"] == ["driving"]
    assert query["dir_action"] == ["navigate"]
    assert tuple(map(float, query["destination"][0].split(","))) == (lat, lon)
    assert "%2C" in url and "e" not in query["destination"][0]


@pytest.mark.parametrize(
    "lat,lon",
    [
        (91, 0),
        (0, -181),
        (float("nan"), 0),
        (0, float("inf")),
        (True, 0),
        (0, False),
        (None, 0),
        (0, "-58.3&origin=privado"),
        (10**400, 0),
    ],
)
def test_invalid_coordinates_do_not_produce_a_link(lat, lon):
    with pytest.raises(ValueError, match="Coordenadas de estación inválidas"):
        google_maps_url(lat, lon)


def sample():
    return {
        "status": "historical_scenario",
        "alternatives": [{"station_id": "one", "priorities": ["equilibrio"]}],
        "evaluations": [
            {"station_id": "one", "brand": "Marca", "address": "Av. Prueba 1"},
            {"station_id": "two", "brand": "Otra", "address": "Av. Prueba 2"},
        ],
        "navigation_destinations": {
            "one": {"lat": -34.61, "lon": -58.40},
            "two": {"lat": -34.62, "lon": -58.41},
        },
    }


def test_only_chosen_stations_have_links_without_mutating_the_result():
    payload = sample()
    before = deepcopy(payload)
    shown = present_recommendation(payload)
    assert payload == before
    assert shown["alternatives"] == payload["alternatives"]
    assert shown["evaluations"] == payload["evaluations"]
    assert shown["status"] == "historical_scenario"
    assert "navigation_destinations" not in shown
    assert len(shown["navigation"]) == 1
    assert shown["navigation"][0]["label"] == "Cómo llegar a Marca — Av. Prueba 1"
    assert shown["navigation"][0]["station_id"] == "one"
    assert shown["navigation_notice"] == NOTICE


@pytest.mark.parametrize("legacy", [False, True])
def test_no_links_without_winners_or_locations(legacy):
    payload = sample()
    if legacy:
        del payload["navigation_destinations"]
    else:
        payload["alternatives"] = []
    shown = present_recommendation(payload)
    assert shown["navigation"] == [] and shown["navigation_notice"] is None


def test_label_falls_back_to_station_identifier():
    payload = sample()
    payload["evaluations"][0].update(brand="", address="")
    assert (
        present_recommendation(payload)["navigation"][0]["label"]
        == "Cómo llegar a la estación — one"
    )


def test_stale_stations_get_their_own_link_apart_from_the_alternatives():
    payload = sample()
    payload["stale_price_estimates"] = {
        "status": "available",
        "items": [
            {"station_id": "501", "brand": "Bandera", "address": "Calle 1"},
            {"station_id": "502", "brand": "", "address": ""},
        ],
    }
    payload["stale_navigation_destinations"] = {"501": {"lat": -34.6, "lon": -58.45}}
    before = deepcopy(payload)
    shown = present_recommendation(payload)
    assert payload == before and "stale_navigation_destinations" not in shown
    first, second = shown["stale_price_estimates"]["items"]
    assert first["navigation"]["label"] == "Cómo llegar a Bandera — Calle 1"
    assert first["navigation"]["url"].startswith("https://www.google.com/maps/dir/?api=1")
    assert "navigation" not in second
    assert [link["station_id"] for link in shown["navigation"]] == ["one"]


def test_a_stale_link_alone_still_shows_the_navigation_notice():
    payload = sample()
    payload["alternatives"] = []
    payload["stale_price_estimates"] = {
        "status": "available",
        "items": [{"station_id": "501", "brand": "B", "address": "A"}],
    }
    payload["stale_navigation_destinations"] = {"501": {"lat": -34.6, "lon": -58.45}}
    shown = present_recommendation(payload)
    assert shown["navigation"] == [] and shown["navigation_notice"] == NOTICE
