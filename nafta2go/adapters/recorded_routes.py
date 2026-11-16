"""Captura y reproducción explícita de una matriz real, sin sustituir coordenadas."""

import hashlib
import json
import logging
import os
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock

from nafta2go.adapters.openrouteservice import client_from_env
from nafta2go.adapters.route_cache import RouteCache
from nafta2go.adapters.routing import DistanceMatrix, Point, ProviderUnavailable

logger = logging.getLogger(__name__)
_runtime_lock = Lock()
_runtime = None
_settings = None


def shared_cache():
    global _runtime, _settings
    names = (
        "ORS_CACHE_TTL_SECONDS",
        "ORS_CACHE_MAX_ENTRIES",
        "ORS_REQUESTS_PER_MINUTE",
        "ORS_REQUESTS_PER_DAY",
    )
    try:
        settings = tuple(
            int(os.environ.get(name, default))
            for name, default in zip(names, (300, 128, 30, 450), strict=True)
        )
        with _runtime_lock:
            if settings != _settings:
                _runtime = RouteCache(*settings)
                _settings = settings
            return _runtime
    except ValueError as exc:
        raise ProviderUnavailable("Configuración local de caché o cupo inválida") from exc


class CapturedRoutes:
    """Cliente diferido: sin cobertura no requiere credenciales ni hace solicitudes."""

    def __init__(self, cache=None):
        self.evidence: dict | None = None
        self.sha256: str | None = None
        self.cache_hit = False
        self._cache = cache

    def matrix(self, sources, destinations):
        self.evidence, self.sha256, self.cache_hit = None, None, False
        cache = self._cache if self._cache is not None else shared_cache()
        client = client_from_env()

        def load():
            matrix = client.matrix(sources, destinations)
            evidence = {
                "provider": "openrouteservice",
                "endpoint": client.matrix_url,
                "captured_at_utc": datetime.now(UTC).isoformat(),
                "units": {"distances": "m", "durations": "s"},
                **asdict(matrix),
            }
            return matrix, evidence

        key = (
            client.matrix_url,
            client.credential_scope,
            "duration-distance-m",
            tuple(sources),
            tuple(destinations),
        )
        try:
            (matrix, self.evidence), self.cache_hit = cache.get(key, client.credential_scope, load)
        finally:
            client.close()
            logger.info("Estado de caché de rutas", extra={"route_cache": cache.snapshot()})
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
