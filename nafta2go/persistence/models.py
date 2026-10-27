"""Objetos que cruzan la frontera entre la ingesta y la persistencia."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class RawCapture:
    """Referencia al archivo original descargado; su contenido no se guarda en la base."""

    source: str
    url: str
    sha256: str
    size_bytes: int
    stored_path: str
    fetched_at: datetime
    source_last_modified: str | None = None


@dataclass(frozen=True)
class NormalizationResult:
    """Salida del normalizador (POC-01): filas válidas, rechazos y reporte de calidad."""

    rows: list[Mapping[str, object]]
    rejections: list[Mapping[str, object]]
    report: dict
    rules_version: str
