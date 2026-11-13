"""Una matriz guardada solo sirve para las mismas coordenadas y el mismo orden."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from nafta2go.adapters.openrouteservice import OpenRouteServiceClient
from nafta2go.adapters.recorded_routes import CapturedRoutes, RecordedRoutes, shared_cache
from nafta2go.adapters.route_cache import RouteCache
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


def session_with_matrix():
    def post(_url, *, json, **_options):
        table = [[1000.0] * len(json["destinations"]) for _ in json["sources"]]
        return SimpleNamespace(
            status_code=200, headers={}, json=lambda: {"durations": table, "distances": table}
        )

    return Mock(post=Mock(side_effect=post))


def test_live_capture_reuses_matrix_and_original_timestamp(monkeypatch, caplog):
    session = session_with_matrix()
    monkeypatch.setattr(
        "nafta2go.adapters.recorded_routes.client_from_env",
        lambda: OpenRouteServiceClient("credencial-de-prueba", session),
    )
    cache = RouteCache()
    first, second = CapturedRoutes(cache), CapturedRoutes(cache)
    a, b = [Point(-34.60, -58.38)], [Point(-34.56, -58.45)]
    with caplog.at_level("INFO"):
        matrix = first.matrix(a, b)
        matrix.distances_m[0][0] = 0
        result = second.matrix(a, b)
    assert result.distances_m == [[1000]] and second.cache_hit
    assert first.sha256 == second.sha256
    assert first.evidence["captured_at_utc"] == second.evidence["captured_at_utc"]
    assert session.post.call_count == 1
    events = [r.route_cache for r in caplog.records if hasattr(r, "route_cache")]
    assert events[-1]["hits"] == 1 and events[-1]["requests"] == 1
    assert set(events[-1]) == {"hits", "misses", "requests", "errors", "limited", "busy", "entries"}
    assert "credencial-de-prueba" not in caplog.text and "-34.60" not in caplog.text


@pytest.mark.parametrize("change", ["coordinate", "order", "profile", "endpoint", "credential"])
def test_cache_identity_includes_all_routing_inputs(monkeypatch, change):
    session = session_with_matrix()
    options = {"api_key": "credencial-de-prueba", "session": session}
    monkeypatch.setattr(
        "nafta2go.adapters.recorded_routes.client_from_env",
        lambda: OpenRouteServiceClient(**options),
    )
    cache = RouteCache()
    sources = [Point(-34.60, -58.38), Point(-34.61, -58.39)]
    destinations = [Point(-34.56, -58.45)]
    CapturedRoutes(cache).matrix(sources, destinations)
    if change == "coordinate":
        sources[0] = Point(-34.600001, -58.38)
    elif change == "order":
        sources.reverse()
    elif change == "profile":
        options["profile"] = "cycling-regular"
    elif change == "endpoint":
        options["base_url"] = "https://otro-proveedor.invalid"
    else:
        options["api_key"] = "otra-credencial-de-prueba"
    changed = CapturedRoutes(cache)
    changed.matrix(sources, destinations)
    assert not changed.cache_hit
    assert session.post.call_count == 2


def test_environment_settings_share_runtime_and_reject_invalid_configuration(monkeypatch):
    monkeypatch.setenv("ORS_CACHE_TTL_SECONDS", "100")
    first = shared_cache()
    assert shared_cache() is first
    monkeypatch.setenv("ORS_CACHE_TTL_SECONDS", "101")
    assert shared_cache() is not first
    monkeypatch.setenv("ORS_CACHE_TTL_SECONDS", "inválido")
    with pytest.raises(ProviderUnavailable, match="Configuración"):
        shared_cache()
    monkeypatch.setenv("ORS_CACHE_TTL_SECONDS", "-1")
    with pytest.raises(ProviderUnavailable, match="Configuración"):
        shared_cache()


def test_malformed_provider_response_is_not_cached(monkeypatch):
    session = session_with_matrix()
    valid = session.post.side_effect
    session.post.side_effect = None
    session.post.return_value = SimpleNamespace(status_code=200, headers={}, json=lambda: {})
    monkeypatch.setattr(
        "nafta2go.adapters.recorded_routes.client_from_env",
        lambda: OpenRouteServiceClient("prueba", session),
    )
    cache = RouteCache()
    provider = CapturedRoutes(cache)
    a, b = [Point(-34.60, -58.38)], [Point(-34.56, -58.45)]
    with pytest.raises(ProviderUnavailable):
        provider.matrix(a, b)
    assert provider.evidence is None and provider.sha256 is None
    session.post.side_effect = valid
    assert provider.matrix(a, b).distances_m == [[1000]]
    assert session.post.call_count == 2
