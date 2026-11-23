"""Clasificar únicamente coordenadas públicas de estaciones con cartografía GCBA."""

import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def polygons():
    return json.loads((Path(__file__).resolve().parents[1] / "resources/communes.json").read_text())


def inside(x, y, ring):
    hit = False
    for a, b in zip(ring, ring[1:] + ring[:1], strict=True):
        if (a[1] > y) != (b[1] > y) and x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]:
            hit = not hit
    return hit


@lru_cache(maxsize=512)
def station_commune(lat, lon):
    if lat is None or lon is None:
        return "unknown"
    for feature in polygons():
        for rings in feature["polygons"]:
            if inside(lon, lat, rings[0]) and not any(inside(lon, lat, ring) for ring in rings[1:]):
                return feature["commune"]
    return "unknown"
