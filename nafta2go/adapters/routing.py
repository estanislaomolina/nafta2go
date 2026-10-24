"""Contrato neutral para proveedores de rutas.

El dominio depende de este contrato y no de un proveedor concreto, para poder
reemplazar OpenRouteService por OSRM u otro motor sin tocar las reglas.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Point:
    lat: float
    lon: float

    def __post_init__(self) -> None:
        if not (math.isfinite(self.lat) and -90 <= self.lat <= 90):
            raise ValueError(f"lat: fuera de rango ({self.lat})")
        if not (math.isfinite(self.lon) and -180 <= self.lon <= 180):
            raise ValueError(f"lon: fuera de rango ({self.lon})")


@dataclass(frozen=True)
class DistanceMatrix:
    """Duraciones en segundos y distancias en metros, fila por origen.

    `None` indica que el proveedor no encontró ruta para ese par.
    """

    durations_s: list[list[float | None]]
    distances_m: list[list[float | None]]
    sources: list[Point]
    destinations: list[Point]


class RoutingError(Exception):
    def __init__(self, message: str, status: int | None = None, provider_code: int | None = None):
        super().__init__(message)
        self.status = status
        self.provider_code = provider_code


class InvalidCredentials(RoutingError):
    """Falta la credencial o el proveedor la rechazó."""


class QuotaExceeded(RoutingError):
    """Se agotó la cuota diaria o el límite por minuto."""


class InvalidRequest(RoutingError):
    """La solicitud no es válida para el proveedor (puntos, tamaño o parámetros)."""


class ProviderTimeout(RoutingError):
    """El proveedor no respondió dentro del tiempo máximo."""


class ProviderUnavailable(RoutingError):
    """El proveedor falló, no está disponible o respondió algo inesperado."""


class RoutingProvider(Protocol):
    def matrix(self, sources: Sequence[Point], destinations: Sequence[Point]) -> DistanceMatrix: ...


def trip_matrix(
    provider: RoutingProvider,
    origin: Point,
    stations: Sequence[Point],
    destination: Point | None,
) -> DistanceMatrix:
    """Pide en una sola matriz todos los tramos para evaluar las candidatas.

    La fila 0 contiene origen→estación y, en la última columna, la ruta de
    referencia origen→destino. Las filas siguientes contienen estación→destino.
    Sin destino, el segundo tramo es la vuelta al origen.
    """
    end = destination if destination is not None else origin
    return provider.matrix([origin, *stations], [*stations, end])
