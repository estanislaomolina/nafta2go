"""Estimación rotulada para precios oficiales de 31 a 120 días (ADR-020).

La estimación nunca reemplaza el precio oficial, no renueva su vigencia y no entra al
ranking. Usa la mediana reciente de la bandera, el método elegido en la evaluación de
reingresos (`docs/evidencia/estimacion-antiguos-2026-11`); sin esa referencia se abstiene.
"""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from statistics import median

from nafta2go.adapters.routing import Point
from nafta2go.application.corridor import straight_detour_km
from nafta2go.application.coverage_rules import MAX_DETOUR_KM, MAX_PRICE_AGE_DAYS
from nafta2go.application.recommendation import DEFAULT_CANDIDATE_LIMIT
from nafta2go.application.stored_query import LOCAL_ZONE, PRODUCT_IDS, _filter_reason
from nafta2go.ml.temporal import RECENT_DAYS

ESTIMATE_VERSION = "stale-estimate-v1"
METHOD = "bandera_reciente"
EVIDENCE = "evidencia/estimacion-antiguos-2026-11"
# Rango evaluado en ADR-020: más de 30 días (estricto) y hasta 120 días inclusive.
MIN_AGE_DAYS = 30
MAX_AGE_DAYS = 120


@dataclass(frozen=True)
class StaleEstimate:
    station_id: str
    company: str
    brand: str
    address: str
    official_price_ars_per_l: Decimal
    official_published_at_local: datetime
    official_age_days: float
    estimate_ars_per_l: Decimal
    reference_from_local: datetime
    reference_to_local: datetime
    reference_count: int
    method: str = METHOD
    version: str = ESTIMATE_VERSION
    # Coordenadas públicas de la estación, sólo para el enlace de navegación: no se persisten.
    location: Point | None = field(default=None, compare=False)


def _local(moment: datetime) -> datetime:
    return moment.astimezone(LOCAL_ZONE).replace(tzinfo=None)


def brand_recent_medians(
    rows: Iterable[dict], product_id: int, schedule_id: int, now_local: datetime
) -> dict[str, tuple[Decimal, int]]:
    """Mediana y cantidad por bandera en los últimos RECENT_DAYS, sin el instante actual.

    Replica `brand_recent_median` de `ml.temporal`: mismo producto y franja, geometría
    válida en CABA y ventana cerrada al inicio. Se calcula una vez por consulta.
    """
    now = now_local.replace(tzinfo=LOCAL_ZONE).astimezone(UTC)
    window = timedelta(days=RECENT_DAYS)
    prices = defaultdict(list)
    for row in rows:
        if (
            row["brand"]
            and row["valid_from"] < now_local
            and _filter_reason(row, product_id, schedule_id, now, window) is None
        ):
            prices[row["brand"]].append(row["price"])
    return {brand: (Decimal(median(values)), len(values)) for brand, values in prices.items()}


def brand_recent_median(
    rows: Iterable[dict], brand: str, product_id: int, schedule_id: int, now_local: datetime
) -> tuple[Decimal, int] | None:
    return brand_recent_medians(rows, product_id, schedule_id, now_local).get(brand)


def estimate_stale_prices(
    rows: Iterable[dict],
    *,
    fuel_type: str,
    schedule_id: int,
    reference_at: datetime,
    origin: Point | None = None,
    destination: Point | None = None,
    max_detour_km: float = MAX_DETOUR_KM,
    max_age_days: int = MAX_PRICE_AGE_DAYS,
    limit: int = DEFAULT_CANDIDATE_LIMIT,
) -> tuple[StaleEstimate, ...]:
    """Estaciones cuyo último precio quedó fuera de la vigencia, dentro del rango evaluado."""
    if not isinstance(reference_at, datetime) or reference_at.utcoffset() is None:
        raise ValueError("reference_at: debe ser una fecha con zona horaria")
    rows = list(rows)
    product_id = PRODUCT_IDS[fuel_type]
    now = reference_at.astimezone(UTC)
    now_local = _local(reference_at)
    latest = {}
    for row in rows:
        if _filter_reason(row, product_id, schedule_id, now, timedelta(days=MAX_AGE_DAYS)):
            continue
        tie = row["id"] if row["id"] is not None else row["source_row"]
        previous = latest.get(row["station_id"])
        if previous is None or (row["valid_from"], tie) > previous[0]:
            latest[row["station_id"]] = ((row["valid_from"], tie), row)

    threshold = timedelta(days=max(MIN_AGE_DAYS, max_age_days))
    references = brand_recent_medians(rows, product_id, schedule_id, now_local)
    estimates = []
    for _, row in sorted(latest.values(), key=lambda item: item[0], reverse=True):
        age = now_local - row["valid_from"]
        if age <= threshold:
            continue
        if origin is not None:
            station = Point(row["lat"], row["lon"])
            if straight_detour_km(origin, station, destination) > max_detour_km:
                continue
        reference = references.get(row["brand"])
        if reference is None:
            continue
        value, count = reference
        estimates.append(
            StaleEstimate(
                station_id=str(row["station_id"]),
                company=row.get("company", ""),
                brand=row["brand"],
                address=row.get("address", ""),
                official_price_ars_per_l=row["price"],
                official_published_at_local=row["valid_from"],
                official_age_days=round(age.total_seconds() / 86400, 1),
                estimate_ars_per_l=value.quantize(Decimal("0.001")),
                reference_from_local=now_local - timedelta(days=RECENT_DAYS),
                reference_to_local=now_local,
                reference_count=count,
                location=Point(row["lat"], row["lon"]),
            )
        )
        if len(estimates) == limit:
            break
    return tuple(estimates)
