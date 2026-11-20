"""Resultados de búsqueda de ubicaciones, independientes del proveedor."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Place:
    label: str
    lat: float
    lon: float


class PlaceUnavailable(RuntimeError):
    """No se pudo consultar el servicio de ubicaciones."""


class PlaceBusy(PlaceUnavailable):
    """La búsqueda debe esperar para no saturar al proveedor."""
