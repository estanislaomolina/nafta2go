"""Cartografía pública y cupo: sin consultas de red ni coordenadas de conductores."""

import pytest

from nafta2go.adapters.public_communes import inside, polygons, station_commune
from scripts.prepare_communes import transform


def test_public_stations_are_classified_and_outside_is_unknown():
    assert len(polygons()) == 15
    assert station_commune(-34.5875, -58.3974) == "2"
    assert station_commune(-34.5636, -58.4565) == "13"
    assert station_commune(None, None) == "unknown"
    assert station_commune(0, 0) == "unknown"
    assert inside(1, 1, [[0, 0], [0, 2], [2, 2], [2, 0]])
    with pytest.raises(ValueError):
        transform(b"fuente diferente")


def test_transform_normalizes_polygon_and_multipolygon(monkeypatch):
    import hashlib
    import json

    from scripts import prepare_communes as source

    ring = [[0, 0], [0, 2], [2, 2], [2, 0]]
    raw = json.dumps(
        {
            "features": [
                {
                    "properties": {"comuna": 1},
                    "geometry": {"type": "Polygon", "coordinates": [ring]},
                },
                {
                    "properties": {"comuna": 2},
                    "geometry": {"type": "MultiPolygon", "coordinates": [[ring]]},
                },
            ]
        }
    ).encode()
    monkeypatch.setattr(source, "EXPECTED_SHA", hashlib.sha256(raw).hexdigest())
    result = source.transform(raw)
    assert result[0]["polygons"] == result[1]["polygons"] == [[ring]]
