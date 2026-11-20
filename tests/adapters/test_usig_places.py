"""Contratos recortados de USIG, sin red ni datos privados."""

import json
from contextlib import nullcontext
from unittest.mock import Mock

import pytest
import requests

from nafta2go.adapters.usig_places import USIGPlaces
from nafta2go.domain.places import Place, PlaceUnavailable


def address(**changes):
    return {
        "direccion": "CORRIENTES 1234, CABA",
        "cod_partido": "caba",
        "coordenadas": {"srid": 4326, "x": "-58.384222", "y": "-34.603939"},
        **changes,
    }


def session(monkeypatch, payloads, status=200):
    fake = Mock(headers={})
    responses = []
    for payload in payloads:
        response = Mock(status_code=status)
        response.iter_content.return_value = [json.dumps(payload).encode()]
        responses.append(nullcontext(response))
    fake.get.side_effect = responses
    monkeypatch.setattr("nafta2go.adapters.usig_places.requests.Session", lambda: nullcontext(fake))
    return fake


def test_addresses_use_wgs84_and_only_caba(monkeypatch):
    fake = session(
        monkeypatch,
        [
            {
                "direccionesNormalizadas": [
                    address(),
                    address(cod_partido="moreno"),
                    address(coordenadas={"srid": 4326, "x": "nan", "y": "-34.6"}),
                    address(coordenadas={"srid": 22185, "x": 107469, "y": 102642}),
                    {},
                ]
            }
        ],
    )
    assert USIGPlaces()("Corrientes 1234") == [
        Place("CORRIENTES 1234, CABA", -34.603939, -58.384222)
    ]
    call = fake.get.call_args
    assert call.kwargs["allow_redirects"] is False and call.kwargs["stream"] is True
    assert call.kwargs["params"] == {"direccion": "Corrientes 1234", "geocodificar": "True"}
    assert fake.headers["User-Agent"].startswith("Nafta2Go/")


def test_named_place_is_resolved_through_its_normalized_address(monkeypatch):
    fake = session(
        monkeypatch,
        [
            {"direccionesNormalizadas": []},
            {"instancias": [{"id": "hospitales|1", "nombre": "Hospital de prueba"}]},
            {"direccionNormalizada": "Corrientes 1234"},
            {"direccionesNormalizadas": [address()]},
        ],
    )
    result = USIGPlaces()("Hospital de prueba")
    assert result[0].label == "Hospital de prueba — CORRIENTES 1234, CABA"
    assert fake.get.call_count == 4
    assert "getObjectContent" in fake.get.call_args_list[2].args[0]


@pytest.mark.parametrize("payload,status", [({}, 200), ({}, 429), ([], 200), ({}, 302)])
def test_invalid_provider_response_is_unavailable_without_retry(monkeypatch, payload, status):
    fake = session(monkeypatch, [payload], status)
    with pytest.raises(PlaceUnavailable):
        USIGPlaces()("Corrientes 1234")
    assert fake.get.call_count == 1


def test_empty_and_disabled_provider(monkeypatch):
    fake = session(monkeypatch, [{"direccionesNormalizadas": []}, {"instancias": []}])
    assert USIGPlaces()("Lugar inexistente") == []
    monkeypatch.setenv("NAFTA2GO_PLACE_SEARCH_ENABLED", "0")
    with pytest.raises(PlaceUnavailable):
        USIGPlaces()("Corrientes 1234")
    assert fake.get.call_count == 2


def test_network_error_is_wrapped_without_echoing_the_query(monkeypatch):
    fake = session(monkeypatch, [])
    fake.get.side_effect = requests.Timeout("direccion-privada")
    with pytest.raises(PlaceUnavailable) as error:
        USIGPlaces()("direccion-privada")
    assert "direccion-privada" not in str(error.value)
