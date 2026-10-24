"""Cliente del servicio Matrix V2 de OpenRouteService."""

import logging
import math
import os
from collections.abc import Sequence

import requests

from nafta2go.adapters.routing import (
    DistanceMatrix,
    InvalidCredentials,
    InvalidRequest,
    Point,
    ProviderTimeout,
    ProviderUnavailable,
    QuotaExceeded,
    RoutingError,
)

BASE_URL = "https://api.openrouteservice.org"
# Origen + destino + hasta veinte candidatas (RF03).
MAX_LOCATIONS = 22
# Conexión y lectura en segundos.
DEFAULT_TIMEOUT = (5, 15)
RATE_LIMIT_HEADERS = ("x-ratelimit-limit", "x-ratelimit-remaining", "x-ratelimit-reset")

logger = logging.getLogger(__name__)


class OpenRouteServiceClient:
    def __init__(
        self,
        api_key: str,
        session: requests.Session | None = None,
        base_url: str = BASE_URL,
        profile: str = "driving-car",
        timeout: tuple[float, float] = DEFAULT_TIMEOUT,
    ) -> None:
        self._api_key = api_key
        self._session = session or requests.Session()
        self._url = f"{base_url.rstrip('/')}/v2/matrix/{profile}"
        self._timeout = timeout
        self.last_rate_limit: dict[str, str] = {}

    def matrix(self, sources: Sequence[Point], destinations: Sequence[Point]) -> DistanceMatrix:
        locations: list[Point] = []
        source_idx = [_index_of(locations, point) for point in sources]
        destination_idx = [_index_of(locations, point) for point in destinations]
        if len(locations) > MAX_LOCATIONS:
            raise InvalidRequest(
                f"{len(locations)} ubicaciones superan el máximo configurado de {MAX_LOCATIONS}"
            )

        body = {
            "locations": [[point.lon, point.lat] for point in locations],
            "sources": source_idx,
            "destinations": destination_idx,
            "metrics": ["duration", "distance"],
            "units": "m",
        }
        try:
            response = self._session.post(
                self._url,
                json=body,
                headers={"Authorization": self._api_key},
                timeout=self._timeout,
            )
        except requests.Timeout as exc:
            raise ProviderTimeout("OpenRouteService no respondió a tiempo") from exc
        except requests.RequestException as exc:
            raise ProviderUnavailable(
                f"No se pudo conectar con OpenRouteService: {type(exc).__name__}"
            ) from exc

        self.last_rate_limit = {
            name: response.headers[name] for name in RATE_LIMIT_HEADERS if name in response.headers
        }
        if response.status_code != 200:
            raise _error_for(response)

        durations, distances = _parse_matrix(response, len(source_idx), len(destination_idx))
        logger.info(
            "matriz de rutas obtenida",
            extra={"locations": len(locations), "elements": len(source_idx) * len(destination_idx)},
        )
        return DistanceMatrix(durations, distances, list(sources), list(destinations))


def client_from_env(session: requests.Session | None = None) -> OpenRouteServiceClient:
    api_key = os.environ.get("ORS_API_KEY", "").strip()
    if not api_key:
        raise InvalidCredentials("Falta la variable de entorno ORS_API_KEY")
    return OpenRouteServiceClient(api_key=api_key, session=session)


def _index_of(locations: list[Point], point: Point) -> int:
    if point not in locations:
        locations.append(point)
    return locations.index(point)


def _error_for(response: requests.Response) -> RoutingError:
    status = response.status_code
    code = _provider_code(response)
    # El cuerpo del proveedor no se incluye en el mensaje: puede repetir datos de la solicitud.
    message = f"OpenRouteService respondió {status}" + (f" (código {code})" if code else "")
    if status in (401, 403):
        return InvalidCredentials(message, status, code)
    if status == 429:
        return QuotaExceeded(message, status, code)
    if 400 <= status < 500:
        return InvalidRequest(message, status, code)
    return ProviderUnavailable(message, status, code)


def _provider_code(response: requests.Response) -> int | None:
    try:
        error = response.json().get("error")
    except (ValueError, AttributeError):
        return None
    if isinstance(error, dict) and isinstance(error.get("code"), int):
        return error["code"]
    return None


def _parse_matrix(
    response: requests.Response, rows: int, cols: int
) -> tuple[list[list[float | None]], list[list[float | None]]]:
    try:
        payload = response.json()
        return (
            _parse_table(payload["durations"], rows, cols),
            _parse_table(payload["distances"], rows, cols),
        )
    except (ValueError, KeyError, TypeError) as exc:
        raise ProviderUnavailable(
            "OpenRouteService devolvió una matriz con formato inesperado", 200
        ) from exc


def _parse_table(table: object, rows: int, cols: int) -> list[list[float | None]]:
    if not isinstance(table, list) or len(table) != rows:
        raise ValueError("cantidad de filas inesperada")
    parsed = []
    for row in table:
        if not isinstance(row, list) or len(row) != cols:
            raise ValueError("cantidad de columnas inesperada")
        parsed.append([_cell(value) for value in row])
    return parsed


def _cell(value: object) -> float | None:
    if value is None:
        return None
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
    ):
        raise ValueError(f"valor inválido en la matriz: {value!r}")
    return float(value)
