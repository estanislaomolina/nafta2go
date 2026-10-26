"""Consulta la última ingesta vigente y conecta sus precios con rutas y motor."""

import math
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo

from sqlalchemy import Connection

from nafta2go.adapters.routing import Point, RoutingProvider
from nafta2go.application.corridor import straight_detour_km
from nafta2go.application.coverage_rules import (
    MAX_DETOUR_KM,
    MAX_PRICE_AGE_DAYS,
    MIN_RECENT_CANDIDATES,
)
from nafta2go.application.recommendation import (
    MAX_POC_CANDIDATES,
    Candidate,
    StationEvaluation,
    evaluate_stations,
)
from nafta2go.application.scenario import ScenarioPrices, load_scenario
from nafta2go.domain.engine import FuelRequest
from nafta2go.normalization.rules import (
    ALERT_SEPARATOR,
    CABA_BBOX,
    LOCAL_TIMEZONE,
    MISSING_COORDINATES,
    NAPHTHA_PRODUCTS,
    OUTSIDE_CABA,
)
from nafta2go.persistence import repository

LOCAL_ZONE = ZoneInfo(LOCAL_TIMEZONE)
PRODUCT_IDS = {fuel: product_id for product_id, fuel in NAPHTHA_PRODUCTS.items()}


class CoverageStatus(StrEnum):
    READY = "ready"
    NO_SUCCESSFUL_INGESTION = "no_successful_ingestion"
    INSUFFICIENT_COVERAGE = "insufficient_coverage"
    # Precios de la captura congelada: nunca se presentan como actuales.
    HISTORICAL_SCENARIO = "historical_scenario"


@dataclass(frozen=True)
class StoredPrice:
    candidate: Candidate
    price_id: int | None
    source_row: int
    published_at_local: datetime
    alerts: tuple[str, ...]


@dataclass(frozen=True)
class ScenarioRef:
    """Rótulo del escenario histórico que originó una selección."""

    scenario_id: str
    reference_at: datetime
    extract_sha256: str
    source_sha256: str


@dataclass(frozen=True)
class CandidateSelection:
    status: CoverageStatus
    data_run_id: int | None
    reference_at: datetime
    items: tuple[StoredPrice, ...]
    eligible_station_count: int
    minimum_candidates: int
    exclusions: dict[str, int]
    scenario: ScenarioRef | None = None

    @property
    def candidates(self) -> tuple[Candidate, ...]:
        return tuple(item.candidate for item in self.items)


@dataclass(frozen=True)
class StoredQueryResult:
    selection: CandidateSelection
    evaluations: tuple[StationEvaluation, ...]


@dataclass(frozen=True)
class CoverageQueryResult:
    """Consulta con escenario automático: `selection` es la que se usó para enrutar."""

    status: CoverageStatus
    selection: CandidateSelection
    current: CandidateSelection
    historical: CandidateSelection | None
    evaluations: tuple[StationEvaluation, ...]


def _filter_reason(
    row: dict, product_id: int, schedule_id: int, now: datetime, age: timedelta
) -> str | None:
    if row["product_id"] != product_id or row["fuel_type"] not in PRODUCT_IDS:
        return "incompatible_product"
    if PRODUCT_IDS[row["fuel_type"]] != product_id:
        return "incompatible_product"
    if row["schedule_id"] != schedule_id:
        return "incompatible_schedule"
    published_at = row["valid_from"].replace(tzinfo=LOCAL_ZONE).astimezone(UTC)
    if published_at > now:
        return "future_price"
    if now - published_at > age:
        return "stale_price"
    if not row["price"].is_finite() or row["price"] <= 0:
        return "invalid_price"
    alerts = {value.strip() for value in row["alerts"].split(ALERT_SEPARATOR)}
    lat, lon = row["lat"], row["lon"]
    if MISSING_COORDINATES in alerts or lat is None or lon is None:
        return "missing_coordinates"
    if not math.isfinite(lat) or not math.isfinite(lon):
        return "invalid_coordinates"
    if OUTSIDE_CABA in alerts or not (
        CABA_BBOX["lat_min"] <= lat <= CABA_BBOX["lat_max"]
        and CABA_BBOX["lon_min"] <= lon <= CABA_BBOX["lon_max"]
    ):
        return "outside_caba"
    return None


def select_stored_candidates(
    conn: Connection,
    *,
    fuel_type: str,
    schedule_id: int,
    reference_at: datetime,
    origin: Point | None = None,
    destination: Point | None = None,
    max_detour_km: float = MAX_DETOUR_KM,
    max_age_days: int = MAX_PRICE_AGE_DAYS,
    limit: int = MAX_POC_CANDIDATES,
    minimum_candidates: int = MIN_RECENT_CANDIDATES,
) -> CandidateSelection:
    """Selecciona precios válidos de una única versión de datos vigente.

    reference_at debe incluir zona horaria. valid_from se interpreta como hora
    local argentina sin zona, según el contrato de persistencia/normalización.
    Con origen, solo cuentan las estaciones dentro del corredor del recorrido.
    La preselección es por recencia e ID; no representa un ranking de conveniencia.
    """
    options = dict(
        fuel_type=fuel_type,
        schedule_id=schedule_id,
        reference_at=reference_at,
        origin=origin,
        destination=destination,
        max_detour_km=max_detour_km,
        max_age_days=max_age_days,
        limit=limit,
        minimum_candidates=minimum_candidates,
    )
    _validate_options(**options)
    run_id = repository.latest_successful_run(conn, "vigente")
    if run_id is None:
        return CandidateSelection(
            CoverageStatus.NO_SUCCESSFUL_INGESTION,
            None,
            reference_at.astimezone(UTC),
            (),
            0,
            minimum_candidates,
            {},
        )
    return select_candidates(repository.prices_for_run(conn, run_id), data_run_id=run_id, **options)


def select_candidates(
    rows: Iterable[dict],
    *,
    fuel_type: str,
    schedule_id: int,
    reference_at: datetime,
    origin: Point | None = None,
    destination: Point | None = None,
    max_detour_km: float = MAX_DETOUR_KM,
    max_age_days: int = MAX_PRICE_AGE_DAYS,
    limit: int = MAX_POC_CANDIDATES,
    minimum_candidates: int = MIN_RECENT_CANDIDATES,
    data_run_id: int | None = None,
) -> CandidateSelection:
    """Aplica los filtros de vigencia, calidad y corredor a filas con forma de station_prices.

    Las filas pueden venir de una ingesta (data_run_id) o de un escenario sin base,
    en cuyo caso id es None y el desempate usa source_row.
    """
    _validate_options(
        fuel_type=fuel_type,
        schedule_id=schedule_id,
        reference_at=reference_at,
        origin=origin,
        destination=destination,
        max_detour_km=max_detour_km,
        max_age_days=max_age_days,
        limit=limit,
        minimum_candidates=minimum_candidates,
    )
    age = timedelta(days=max_age_days)
    reference_at = reference_at.astimezone(UTC)

    exclusions = Counter()
    latest = {}
    for row in rows:
        reason = _filter_reason(row, PRODUCT_IDS[fuel_type], schedule_id, reference_at, age)
        if reason is None and origin is not None:
            station = Point(row["lat"], row["lon"])
            if straight_detour_km(origin, station, destination) > max_detour_km:
                reason = "outside_corridor"
        if reason:
            exclusions[reason] += 1
            continue
        station_id = row["station_id"]
        previous = latest.get(station_id)
        if previous is not None:
            exclusions["superseded_price"] += 1
            if _recency(row) <= _recency(previous):
                continue
        latest[station_id] = row

    selected = sorted(latest.values(), key=lambda row: row["station_id"])
    selected.sort(key=lambda row: row["valid_from"], reverse=True)
    items = tuple(
        StoredPrice(
            candidate=Candidate(
                str(row["station_id"]), Point(row["lat"], row["lon"]), row["price"]
            ),
            price_id=row["id"],
            source_row=row["source_row"],
            published_at_local=row["valid_from"],
            alerts=tuple(
                value.strip() for value in row["alerts"].split(ALERT_SEPARATOR) if value.strip()
            ),
        )
        for row in selected[:limit]
    )
    status = (
        CoverageStatus.READY
        if len(items) >= minimum_candidates
        else CoverageStatus.INSUFFICIENT_COVERAGE
    )
    return CandidateSelection(
        status,
        data_run_id,
        reference_at,
        items,
        len(selected),
        minimum_candidates,
        dict(sorted(exclusions.items())),
    )


def _recency(row: dict) -> tuple:
    tie = row["id"] if row["id"] is not None else row["source_row"]
    return (row["valid_from"], tie)


def _validate_options(
    *,
    fuel_type: str,
    schedule_id: int,
    reference_at: datetime,
    origin: Point | None,
    destination: Point | None,
    max_detour_km: float,
    max_age_days: int,
    limit: int,
    minimum_candidates: int,
) -> None:
    if not isinstance(fuel_type, str) or fuel_type not in PRODUCT_IDS:
        raise ValueError("fuel_type: debe ser super o premium")
    if (
        isinstance(schedule_id, bool)
        or not isinstance(schedule_id, int)
        or schedule_id not in (2, 3)
    ):
        raise ValueError("schedule_id: debe ser 2 (diurno) o 3 (nocturno)")
    if not isinstance(reference_at, datetime) or reference_at.utcoffset() is None:
        raise ValueError("reference_at: debe ser una fecha con zona horaria")
    if (
        isinstance(limit, bool)
        or not isinstance(limit, int)
        or not 1 <= limit <= MAX_POC_CANDIDATES
    ):
        raise ValueError("limit: debe estar entre 1 y 10")
    if (
        isinstance(minimum_candidates, bool)
        or not isinstance(minimum_candidates, int)
        or not 1 <= minimum_candidates <= limit
    ):
        raise ValueError("minimum_candidates: debe estar entre 1 y limit")
    if isinstance(max_age_days, bool) or not isinstance(max_age_days, int) or max_age_days < 0:
        raise ValueError("max_age_days: debe ser un entero no negativo")
    try:
        timedelta(days=max_age_days)
    except OverflowError as exc:
        raise ValueError("max_age_days: fuera de rango") from exc
    if origin is None and destination is not None:
        raise ValueError("destination: requiere origin")
    if (
        isinstance(max_detour_km, bool)
        or not isinstance(max_detour_km, int | float)
        or not math.isfinite(max_detour_km)
        or max_detour_km < 0
    ):
        raise ValueError("max_detour_km: debe ser un número finito no negativo")


def evaluate_from_database(
    conn: Connection,
    request: FuelRequest,
    origin: Point,
    destination: Point | None,
    provider: RoutingProvider,
    *,
    fuel_type: str,
    schedule_id: int,
    reference_at: datetime,
    max_detour_km: float = MAX_DETOUR_KM,
    max_age_days: int = MAX_PRICE_AGE_DAYS,
    limit: int = MAX_POC_CANDIDATES,
    minimum_candidates: int = MIN_RECENT_CANDIDATES,
) -> StoredQueryResult:
    """Lee una versión de precios y enruta sólo si alcanza el mínimo configurado."""
    selection = select_stored_candidates(
        conn,
        fuel_type=fuel_type,
        schedule_id=schedule_id,
        reference_at=reference_at,
        origin=origin,
        destination=destination,
        max_detour_km=max_detour_km,
        max_age_days=max_age_days,
        limit=limit,
        minimum_candidates=minimum_candidates,
    )
    if selection.status != CoverageStatus.READY:
        return StoredQueryResult(selection, ())
    return StoredQueryResult(
        selection,
        evaluate_stations(request, selection.candidates, origin, destination, provider),
    )


def select_with_coverage(
    conn: Connection,
    origin: Point,
    destination: Point | None,
    *,
    fuel_type: str,
    schedule_id: int,
    reference_at: datetime,
    scenario_loader: Callable[[], ScenarioPrices] = load_scenario,
) -> CoverageQueryResult:
    """Elige la captura actual si alcanza la cobertura; si no, el escenario histórico rotulado.

    No consulta rutas: `evaluations` queda vacío. Los parámetros de cobertura salen de
    coverage_rules. En el escenario, la vigencia se mide contra su fecha de referencia
    y la selección lleva el rótulo `scenario`.
    """
    options = {"fuel_type": fuel_type, "schedule_id": schedule_id}
    corridor = {"origin": origin, "destination": destination}
    current = select_stored_candidates(conn, reference_at=reference_at, **options, **corridor)
    if current.status == CoverageStatus.READY:
        return CoverageQueryResult(CoverageStatus.READY, current, current, None, ())

    scenario = scenario_loader()
    historical = select_candidates(
        scenario.rows, reference_at=scenario.reference_at, **options, **corridor
    )
    label = ScenarioRef(
        scenario.scenario_id,
        scenario.reference_at,
        scenario.extract_sha256,
        scenario.source_sha256,
    )
    historical = replace(historical, scenario=label)
    if historical.status != CoverageStatus.READY:
        return CoverageQueryResult(
            CoverageStatus.INSUFFICIENT_COVERAGE, historical, current, historical, ()
        )
    historical = replace(historical, status=CoverageStatus.HISTORICAL_SCENARIO)
    return CoverageQueryResult(
        CoverageStatus.HISTORICAL_SCENARIO, historical, current, historical, ()
    )


def evaluate_with_coverage(
    conn: Connection,
    request: FuelRequest,
    origin: Point,
    destination: Point | None,
    provider: RoutingProvider,
    *,
    fuel_type: str,
    schedule_id: int,
    reference_at: datetime,
    scenario_loader: Callable[[], ScenarioPrices] = load_scenario,
) -> CoverageQueryResult:
    """Como select_with_coverage, y enruta y evalúa solo si hay cobertura en algún origen."""
    result = select_with_coverage(
        conn,
        origin,
        destination,
        fuel_type=fuel_type,
        schedule_id=schedule_id,
        reference_at=reference_at,
        scenario_loader=scenario_loader,
    )
    if result.status == CoverageStatus.INSUFFICIENT_COVERAGE:
        return result
    candidates = result.selection.candidates
    evaluations = evaluate_stations(request, candidates, origin, destination, provider)
    return replace(result, evaluations=evaluations)
