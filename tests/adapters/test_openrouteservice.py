"""Tests del adaptador de OpenRouteService con una sesión HTTP falsa (sin red)."""

import pytest
import requests

from nafta2go.adapters.openrouteservice import (
    MAX_LOCATIONS,
    OpenRouteServiceClient,
    client_from_env,
)
from nafta2go.adapters.routing import (
    InvalidCredentials,
    InvalidRequest,
    Point,
    ProviderTimeout,
    ProviderUnavailable,
    QuotaExceeded,
    trip_matrix,
)

OBELISCO = Point(lat=-34.6037, lon=-58.3816)
CABILDO = Point(lat=-34.5627, lon=-58.4565)
STATIONS = [
    Point(lat=-34.640861, lon=-58.389601),
    Point(lat=-34.652935, lon=-58.517138),
    Point(lat=-34.598, lon=-58.42),
]


class FakeResponse:
    def __init__(self, status_code=200, payload=None, headers=None, raw_text=None):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}
        self.text = raw_text if raw_text is not None else str(payload)

    def json(self):
        if self._payload is None:
            raise ValueError("sin JSON")
        return self._payload


class FakeSession:
    def __init__(self, response=None, exception=None):
        self.response = response
        self.exception = exception
        self.calls = []

    def post(self, url, json=None, headers=None, timeout=None):
        self.calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        if self.exception is not None:
            raise self.exception
        return self.response


def ok_response(n_sources, n_destinations, headers=None):
    return FakeResponse(
        200,
        {
            "durations": [[60.0] * n_destinations for _ in range(n_sources)],
            "distances": [[1000.0] * n_destinations for _ in range(n_sources)],
        },
        headers,
    )


def client(session, api_key="k"):
    return OpenRouteServiceClient(api_key=api_key, session=session)


def test_request_targets_matrix_endpoint_with_auth():
    session = FakeSession(ok_response(1, 1))
    client(session).matrix([OBELISCO], [CABILDO])
    call = session.calls[0]
    assert call["url"] == "https://api.openrouteservice.org/v2/matrix/driving-car"
    assert call["headers"]["Authorization"] == "k"
    assert call["json"]["metrics"] == ["duration", "distance"]
    assert call["json"]["units"] == "m"
    assert call["timeout"] == (5, 15)


def test_request_body_uses_lon_lat_order():
    session = FakeSession(ok_response(1, 1))
    client(session).matrix([OBELISCO], [CABILDO])
    assert session.calls[0]["json"]["locations"][0] == [-58.3816, -34.6037]


def test_trip_matrix_with_destination_shape():
    session = FakeSession(ok_response(4, 4))
    trip_matrix(client(session), OBELISCO, STATIONS, CABILDO)
    body = session.calls[0]["json"]
    assert len(body["locations"]) == 5
    assert body["sources"] == [0, 1, 2, 3]
    assert body["destinations"] == [1, 2, 3, 4]


def test_round_trip_reuses_origin_index():
    session = FakeSession(ok_response(4, 4))
    result = trip_matrix(client(session), OBELISCO, STATIONS, None)
    body = session.calls[0]["json"]
    assert len(body["locations"]) == 1 + len(STATIONS)
    assert body["destinations"] == [1, 2, 3, 0]
    assert result.destinations[-1] == OBELISCO


def test_parses_durations_and_distances():
    session = FakeSession(
        FakeResponse(200, {"durations": [[0.0, 420.5]], "distances": [[0.0, 3100.2]]})
    )
    result = client(session).matrix([OBELISCO], [OBELISCO, CABILDO])
    assert result.durations_s == [[0.0, 420.5]]
    assert result.distances_m == [[0.0, 3100.2]]
    assert result.sources == [OBELISCO]
    assert result.destinations == [OBELISCO, CABILDO]


def test_null_pairs_become_none():
    session = FakeSession(
        FakeResponse(200, {"durations": [[None, 300.0]], "distances": [[None, 2000.0]]})
    )
    result = client(session).matrix([OBELISCO], [STATIONS[0], CABILDO])
    assert result.durations_s[0][0] is None
    assert result.distances_m[0][0] is None


def test_rejects_more_than_max_locations_without_calling():
    session = FakeSession(ok_response(1, 1))
    many = [Point(lat=-34.6 + i * 0.001, lon=-58.4) for i in range(MAX_LOCATIONS)]
    with pytest.raises(InvalidRequest):
        client(session).matrix([OBELISCO], many)
    assert session.calls == []


@pytest.mark.parametrize(
    "status,error",
    [
        (401, InvalidCredentials),
        (403, InvalidCredentials),
        (429, QuotaExceeded),
        (400, InvalidRequest),
        (404, InvalidRequest),
        (413, InvalidRequest),
        (500, ProviderUnavailable),
        (503, ProviderUnavailable),
    ],
)
def test_http_errors_are_mapped(status, error):
    session = FakeSession(FakeResponse(status, {"error": "x"}))
    with pytest.raises(error) as exc:
        client(session).matrix([OBELISCO], [CABILDO])
    assert exc.value.status == status


def test_provider_error_code_is_kept():
    session = FakeSession(
        FakeResponse(404, {"error": {"code": 6010, "message": "Point not found"}})
    )
    with pytest.raises(InvalidRequest) as exc:
        client(session).matrix([OBELISCO], [CABILDO])
    assert exc.value.provider_code == 6010


def test_timeout_is_mapped():
    session = FakeSession(exception=requests.Timeout("lento"))
    with pytest.raises(ProviderTimeout):
        client(session).matrix([OBELISCO], [CABILDO])


def test_connection_error_is_mapped():
    session = FakeSession(exception=requests.ConnectionError("sin red"))
    with pytest.raises(ProviderUnavailable):
        client(session).matrix([OBELISCO], [CABILDO])


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {"distances": [[1.0]]},
        {"durations": [[1.0, 2.0]], "distances": [[1.0, 2.0]]},
        {"durations": [[1.0]], "distances": [["x"]]},
    ],
)
def test_malformed_response_raises_provider_unavailable(payload):
    session = FakeSession(FakeResponse(200, payload, raw_text="<html>"))
    with pytest.raises(ProviderUnavailable):
        client(session).matrix([OBELISCO], [CABILDO])


def test_rate_limit_headers_are_recorded():
    headers = {
        "x-ratelimit-limit": "500",
        "x-ratelimit-remaining": "499",
        "x-ratelimit-reset": "1793000000",
        "content-type": "application/json",
    }
    ors = client(FakeSession(ok_response(1, 1, headers)))
    ors.matrix([OBELISCO], [CABILDO])
    assert ors.last_rate_limit == {
        "x-ratelimit-limit": "500",
        "x-ratelimit-remaining": "499",
        "x-ratelimit-reset": "1793000000",
    }


def test_errors_do_not_leak_api_key():
    session = FakeSession(
        FakeResponse(403, {"error": "Access to this API has been disallowed SECRETO123"})
    )
    with pytest.raises(InvalidCredentials) as exc:
        client(session, api_key="SECRETO123").matrix([OBELISCO], [CABILDO])
    assert "SECRETO123" not in str(exc.value)


def test_client_from_env_requires_key(monkeypatch):
    monkeypatch.delenv("ORS_API_KEY", raising=False)
    with pytest.raises(InvalidCredentials):
        client_from_env()
    monkeypatch.setenv("ORS_API_KEY", "  ")
    with pytest.raises(InvalidCredentials):
        client_from_env()


def test_client_from_env_uses_key(monkeypatch):
    monkeypatch.setenv("ORS_API_KEY", "desde-entorno")
    session = FakeSession(ok_response(1, 1))
    client_from_env(session=session).matrix([OBELISCO], [CABILDO])
    assert session.calls[0]["headers"]["Authorization"] == "desde-entorno"


@pytest.mark.parametrize("lat,lon", [(-91, 0), (91, 0), (0, -181), (0, 181), (float("nan"), 0)])
def test_point_validates_ranges(lat, lon):
    with pytest.raises(ValueError):
        Point(lat=lat, lon=lon)
