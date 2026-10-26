"""Consulta la última ingesta vigente y conecta sus precios con rutas y motor."""

import math
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo

from sqlalchemy import Connection

from nafta2go.adapters.routing import Point, RoutingProvider
from nafta2go.application.coverage_rules import MAX_PRICE_AGE_DAYS, MIN_RECENT_CANDIDATES
from nafta2go.application.recommendation import (
    MAX_POC_CANDIDATES,
    Candidate,
    StationEvaluation,
    evaluate_stations,
)
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


@dataclass(frozen=True)
class StoredPrice:
    candidate: Candidate
    price_id: int
    source_row: int
    published_at_local: datetime
    alerts: tuple[str, ...]


@dataclass(frozen=True)
class CandidateSelection:
    status: CoverageStatus
    data_run_id: int | None
    reference_at: datetime
    items: tuple[StoredPrice, ...]
    eligible_station_count: int
    minimum_candidates: int
    exclusions: dict[str, int]

    @property
    def candidates(self) -> tuple[Candidate, ...]:
        return tuple(item.candidate for item in self.items)


@dataclass(frozen=True)
class StoredQueryResult:
    selection: CandidateSelection
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
    max_age_days: int = MAX_PRICE_AGE_DAYS,
    limit: int = MAX_POC_CANDIDATES,
    minimum_candidates: int = MIN_RECENT_CANDIDATES,
) -> CandidateSelection:
    """Selecciona precios válidos de una única versión de datos vigente.

    reference_at debe incluir zona horaria. valid_from se interpreta como hora
    local argentina sin zona, según el contrato de persistencia/normalización.
    La preselección es por recencia e ID; no representa un ranking de conveniencia.
    """
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
        age = timedelta(days=max_age_days)
    except OverflowError as exc:
        raise ValueError("max_age_days: fuera de rango") from exc
    reference_at = reference_at.astimezone(UTC)
    run_id = repository.latest_successful_run(conn, "vigente")
    if run_id is None:
        return CandidateSelection(
            CoverageStatus.NO_SUCCESSFUL_INGESTION,
            None,
            reference_at,
            (),
            0,
            minimum_candidates,
            {},
        )

    exclusions = Counter()
    latest = {}
    for row in repository.prices_for_run(conn, run_id):
        reason = _filter_reason(row, PRODUCT_IDS[fuel_type], schedule_id, reference_at, age)
        if reason:
            exclusions[reason] += 1
            continue
        station_id = row["station_id"]
        previous = latest.get(station_id)
        if previous is not None:
            exclusions["superseded_price"] += 1
            if (row["valid_from"], row["id"]) <= (previous["valid_from"], previous["id"]):
                continue
        latest[station_id] = row

    rows = sorted(latest.values(), key=lambda row: row["station_id"])
    rows.sort(key=lambda row: row["valid_from"], reverse=True)
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
        for row in rows[:limit]
    )
    status = (
        CoverageStatus.READY
        if len(items) >= minimum_candidates
        else CoverageStatus.INSUFFICIENT_COVERAGE
    )
    return CandidateSelection(
        status,
        run_id,
        reference_at,
        items,
        len(rows),
        minimum_candidates,
        dict(sorted(exclusions.items())),
    )


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
