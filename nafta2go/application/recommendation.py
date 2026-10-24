"""Conecta rutas y motor para candidatas previamente normalizadas y filtradas."""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation, localcontext

from nafta2go.adapters.routing import (
    DistanceMatrix,
    Point,
    ProviderUnavailable,
    RoutingProvider,
    trip_matrix,
)
from nafta2go.domain.engine import Evaluation, FuelRequest, Route, evaluate_candidate

MAX_POC_CANDIDATES = 10


@dataclass(frozen=True)
class Candidate:
    station_id: str
    location: Point
    price_ars_per_l: Decimal


@dataclass(frozen=True)
class StationEvaluation:
    candidate: Candidate
    evaluation: Evaluation


def _convert(value: float | None, divisor: int) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ProviderUnavailable("La matriz contiene una distancia o duración inválida")
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise ProviderUnavailable("La matriz contiene una distancia o duración inválida") from exc
    if not number.is_finite() or number < 0:
        raise ProviderUnavailable("La matriz contiene una distancia o duración inválida")
    with localcontext() as context:
        context.prec = 28
        context.rounding = ROUND_HALF_EVEN
        return number / divisor


def route_from_matrix(
    matrix: DistanceMatrix, station_index: int, *, has_destination: bool
) -> Route | None:
    """Extrae origen-estación-fin de una matriz generada por trip_matrix.

    station_index comienza en cero y corresponde al orden de las candidatas.
    Un tramo necesario ausente produce None. Sin destino la referencia es cero.
    """
    size = len(matrix.sources)
    if (
        size < 2
        or len(matrix.destinations) != size
        or matrix.sources[1:] != matrix.destinations[:-1]
        or any(
            len(table) != size or any(len(row) != size for row in table)
            for table in (matrix.distances_m, matrix.durations_s)
        )
    ):
        raise ProviderUnavailable("La matriz no respeta el contrato de trip_matrix")
    if isinstance(station_index, bool) or not isinstance(station_index, int):
        raise ValueError("station_index: se requiere un índice entero")
    if not 0 <= station_index < size - 1:
        raise ValueError("station_index: fuera del rango de candidatas")

    row = station_index + 1
    values = (
        _convert(matrix.distances_m[0][station_index], 1000),
        _convert(matrix.distances_m[row][-1], 1000),
        _convert(matrix.durations_s[0][station_index], 60),
        _convert(matrix.durations_s[row][-1], 60),
        _convert(matrix.distances_m[0][-1], 1000) if has_destination else Decimal(0),
        _convert(matrix.durations_s[0][-1], 60) if has_destination else Decimal(0),
    )
    if any(value is None for value in values):
        return None
    return Route(*values)


def evaluate_stations(
    request: FuelRequest,
    candidates: Sequence[Candidate],
    origin: Point,
    destination: Point | None,
    provider: RoutingProvider,
) -> tuple[StationEvaluation, ...]:
    """Pide una matriz y evalúa hasta diez candidatas, conservando su orden.

    El llamador valida producto, CABA, precio, vigencia y cobertura antes de llamar.
    Los errores globales del proveedor se propagan como RoutingError; un par sin
    ruta descarta sólo las candidatas que necesitan ese par. No realiza ranking.
    """
    candidates = tuple(candidates)
    if len(candidates) > MAX_POC_CANDIDATES:
        raise ValueError("candidates: la POC admite hasta diez estaciones por consulta")
    if not candidates:
        return ()
    locations = [item.location for item in candidates]
    matrix = trip_matrix(provider, origin, locations, destination)
    expected_end = destination if destination is not None else origin
    if matrix.sources != [origin, *locations] or matrix.destinations != [*locations, expected_end]:
        raise ProviderUnavailable("La matriz no corresponde a las ubicaciones solicitadas")
    return tuple(
        StationEvaluation(
            candidate,
            evaluate_candidate(
                request,
                candidate.price_ars_per_l,
                route_from_matrix(matrix, index, has_destination=destination is not None),
            ),
        )
        for index, candidate in enumerate(candidates)
    )
