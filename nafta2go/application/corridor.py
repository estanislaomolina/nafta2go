"""Corredor en línea recta alrededor de un recorrido, sin consultar rutas.

Sirve para contar y preseleccionar estaciones cercanas antes de enrutar. El
desvío real lo calcula después el motor con las distancias del proveedor.
"""

import math

from nafta2go.adapters.routing import Point

EARTH_RADIUS_KM = 6371.0088


def haversine_km(a: Point, b: Point) -> float:
    lat_a, lon_a, lat_b, lon_b = map(math.radians, (a.lat, a.lon, b.lat, b.lon))
    h = (
        math.sin((lat_b - lat_a) / 2) ** 2
        + math.cos(lat_a) * math.cos(lat_b) * math.sin((lon_b - lon_a) / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))


def straight_detour_km(origin: Point, station: Point, destination: Point | None) -> float:
    """Kilómetros extra de pasar por la estación; sin destino, la distancia desde el origen."""
    if destination is None:
        return haversine_km(origin, station)
    extra = (
        haversine_km(origin, station)
        + haversine_km(station, destination)
        - haversine_km(origin, destination)
    )
    # Por redondeo, una estación sobre el segmento puede dar un valor apenas negativo.
    return max(0.0, extra)
