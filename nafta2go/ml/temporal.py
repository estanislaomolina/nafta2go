"""Features retrospectivas de precios publicados, sin persistencia ni entrenamiento."""

import math
from bisect import bisect_left, insort
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta
from itertools import groupby
from zoneinfo import ZoneInfo

from nafta2go.normalization.rules import CABA_BBOX, LOCAL_TIMEZONE

FEATURES_VERSION = "price-temporal-v2"
ZONE_DEGREES = 0.02
# Con inflación alta, 30 días de historia quedan desactualizados: v2 agrega el mercado
# y la bandera de la última semana (docs/ML.md).
RECENT_DAYS = 7


class _Window:
    def __init__(self):
        self.events, self.prices = deque(), []

    def expire(self, before):
        while self.events and self.events[0][0] < before:
            _, price = self.events.popleft()
            self.prices.pop(bisect_left(self.prices, price))

    def add(self, when, price):
        self.events.append((when, price))
        insort(self.prices, price)

    def quantile(self, fraction):
        position = (len(self.prices) - 1) * fraction
        low, high = math.floor(position), math.ceil(position)
        return self.prices[low] + (self.prices[high] - self.prices[low]) * (position - low)


def build_temporal_dataset(rows, cutoff: datetime, *, window_days=30, min_history=5, targets=None):
    """Con targets emite sólo esas publicaciones, sin agregarlas al contexto."""
    if cutoff.utcoffset() is None:
        raise ValueError("El corte requiere zona horaria")
    if any(isinstance(v, bool) or not isinstance(v, int) for v in (window_days, min_history)):
        raise ValueError("Los parámetros temporales requieren enteros")
    if not (1 <= window_days <= 365 and 3 <= min_history <= 100):
        raise ValueError("Parámetros temporales fuera de rango")
    cutoff = cutoff.astimezone(UTC)
    windows, previous = defaultdict(_Window), {}
    examples, totals = [], {"train": 0, "validation": 0}
    discarded = 0
    events = [(row, False) for row in rows]
    if targets is not None:
        events.extend((row, True) for row in targets)
    ordered = sorted(
        events,
        key=lambda item: (
            item[0]["valid_from"],
            item[0]["station_id"],
            item[0]["product_id"],
            item[0]["schedule_id"],
            item[0]["source_row"],
        ),
    )
    for date, batch in groupby(ordered, key=lambda item: item[0]["valid_from"]):
        if date.utcoffset() is not None:
            raise ValueError("Las fechas normalizadas deben ser locales sin zona")
        when = date.replace(tzinfo=ZoneInfo(LOCAL_TIMEZONE)).astimezone(UTC)
        partition = "train" if when < cutoff else "validation"
        pending, seen = [], set()
        for row, is_target in batch:
            key = (row["product_id"], row["schedule_id"])
            identity = (row["station_id"], *key)
            seen_key = (identity, is_target)
            if seen_key in seen:
                raise ValueError("Observación duplicada en una misma fecha")
            seen.add(seen_key)
            lat, lon, price = row["lat"], row["lon"], float(row["price"])
            if not math.isfinite(price) or price <= 0:
                raise ValueError("El objetivo debe ser un precio positivo y finito")
            if (
                key[0] not in (2, 3)
                or key[1] not in (2, 3)
                or lat is None
                or lon is None
                or not CABA_BBOX["lat_min"] <= lat <= CABA_BBOX["lat_max"]
                or not CABA_BBOX["lon_min"] <= lon <= CABA_BBOX["lon_max"]
            ):
                discarded += 1
                continue
            if targets is None or is_target:
                totals[partition] += 1
            zone = (math.floor(lat / ZONE_DEGREES), math.floor(lon / ZONE_DEGREES))
            regional, city = windows[(*key, *zone)], windows[key]
            for window in (regional, city):
                window.expire(when - timedelta(days=window_days))
            recent, brand = windows[("recent", *key)], windows[("brand", *key, row["brand"])]
            for window in (recent, brand):
                window.expire(when - timedelta(days=RECENT_DAYS))
            history = regional if len(regional.prices) >= min_history else city
            scope = "zone" if history is regional else "caba"
            if (targets is None or is_target) and len(history.prices) >= min_history:
                last = previous.get(identity)
                features = {
                    "product_id": key[0],
                    "schedule_id": key[1],
                    "brand": row["brand"],
                    "zone_lat": zone[0],
                    "zone_lon": zone[1],
                    "time_days": (when - datetime(2015, 1, 1, tzinfo=UTC)).total_seconds() / 86400,
                    "prior_median": history.quantile(0.5),
                    "prior_count": len(history.prices),
                    "prior_iqr": history.quantile(0.75) - history.quantile(0.25),
                    "previous_station_price": last[1] if last else None,
                    "previous_station_age_days": (when - last[0]).total_seconds() / 86400
                    if last
                    else None,
                    "recent_median": recent.quantile(0.5) if recent.prices else None,
                    "recent_count": len(recent.prices),
                    "brand_recent_median": brand.quantile(0.5) if brand.prices else None,
                    "brand_recent_count": len(brand.prices),
                }
                examples.append(
                    {
                        "source_row": row["source_row"],
                        "station_id": row["station_id"],
                        "target_at_utc": when.isoformat(),
                        "partition": partition,
                        "target_price_ars_per_l": price,
                        "baseline_scope": scope,
                        "features": features,
                    }
                )
            if not is_target:
                pending.append((identity, price, (regional, city, recent, brand)))
        # Primero predecir todo el instante; después incorporar sus precios al historial.
        for identity, price, histories in pending:
            for window in histories:
                window.add(when, price)
            previous[identity] = (when, price)
    report = {"excluded_geometry_or_product": discarded, "partitions": {}}
    for partition, total in totals.items():
        selected = [row for row in examples if row["partition"] == partition]
        errors = [
            abs(row["target_price_ars_per_l"] - row["features"]["prior_median"]) for row in selected
        ]
        report["partitions"][partition] = {
            "observations": total,
            "examples": len(selected),
            "abstained": total - len(selected),
            "baseline_coverage": len(selected) / total if total else 0,
            "baseline_mae_ars_per_l": math.fsum(errors) / len(errors) if errors else None,
        }
    return examples, report
