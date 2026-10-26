"""Una matriz guardada solo sirve para las mismas coordenadas y el mismo orden."""

import json

import pytest

from nafta2go.adapters.recorded_routes import CapturedRoutes, RecordedRoutes
from nafta2go.adapters.routing import Point, ProviderUnavailable


def write_matrix(tmp_path, **changes):
    payload = {
        "provider": "openrouteservice",
        "captured_at_utc": "2026-10-26T12:00:00+00:00",
        "units": {"distances": "m", "durations": "s"},
        "sources": [{"lat": -34.60, "lon": -58.38}],
        "destinations": [{"lat": -34.56, "lon": -58.45}],
        "distances_m": [[1000]],
        "durations_s": [[60]],
        **changes,
    }
    path = tmp_path / "matrix.json"
    path.write_text(json.dumps(payload))
    return path


def test_replays_exact_coordinates_without_network(tmp_path):
    provider = RecordedRoutes(write_matrix(tmp_path))
    matrix = provider.matrix([Point(-34.60, -58.38)], [Point(-34.56, -58.45)])
    assert matrix.distances_m == [[1000]]
    assert len(provider.sha256) == 64


def test_different_coordinate_or_order_is_rejected(tmp_path):
    provider = RecordedRoutes(write_matrix(tmp_path))
    with pytest.raises(ProviderUnavailable, match="coordenadas"):
        provider.matrix([Point(-34.61, -58.38)], [Point(-34.56, -58.45)])


@pytest.mark.parametrize(
    "changes",
    [
        {"units": {"distances": "km", "durations": "s"}},
        {"captured_at_utc": "2026-10-26T12:00:00"},
        {"sources": [{"lat": 100, "lon": 0}]},
    ],
)
def test_invalid_recording_is_rejected(tmp_path, changes):
    with pytest.raises(ProviderUnavailable, match="inválida"):
        RecordedRoutes(write_matrix(tmp_path, **changes))


def test_credentials_are_only_read_when_a_matrix_is_needed(monkeypatch):
    monkeypatch.delenv("ORS_API_KEY", raising=False)
    assert CapturedRoutes().evidence is None
