"""Captura y reproducción explícita de una matriz real, sin sustituir coordenadas."""

import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from nafta2go.adapters.openrouteservice import client_from_env
from nafta2go.adapters.routing import DistanceMatrix, Point, ProviderUnavailable


class CapturedRoutes:
    """Cliente diferido: sin cobertura no requiere credenciales ni hace solicitudes."""

    def __init__(self):
        self.evidence: dict | None = None
        self.sha256: str | None = None

    def matrix(self, sources, destinations):
        client = client_from_env()
        matrix = client.matrix(sources, destinations)
        self.evidence = {
            "provider": "openrouteservice",
            "endpoint": client.matrix_url,
            "captured_at_utc": datetime.now(UTC).isoformat(),
            "units": {"distances": "m", "durations": "s"},
            **asdict(matrix),
        }
        self.sha256 = hashlib.sha256(matrix_bytes(self.evidence)).hexdigest()
        return matrix


class RecordedRoutes:
    def __init__(self, path: Path):
        raw = path.read_bytes()
        try:
            self.evidence = json.loads(raw)
            if self.evidence["units"] != {"distances": "m", "durations": "s"}:
                raise ValueError("unidades incompatibles")
            self.sources = [Point(**point) for point in self.evidence["sources"]]
            self.destinations = [Point(**point) for point in self.evidence["destinations"]]
            self.matrix_value = DistanceMatrix(
                self.evidence["durations_s"],
                self.evidence["distances_m"],
                self.sources,
                self.destinations,
            )
            captured = datetime.fromisoformat(self.evidence["captured_at_utc"])
            if captured.utcoffset() is None:
                raise ValueError("fecha sin zona")
        except (KeyError, TypeError, ValueError) as exc:
            raise ProviderUnavailable("Captura de rutas inválida") from exc
        self.sha256 = hashlib.sha256(raw).hexdigest()

    def matrix(self, sources, destinations):
        if list(sources) != self.sources or list(destinations) != self.destinations:
            raise ProviderUnavailable(
                "La captura no corresponde a las coordenadas y orden solicitados"
            )
        return self.matrix_value


def matrix_bytes(evidence: dict) -> bytes:
    return (json.dumps(evidence, indent=2) + "\n").encode("utf-8")
