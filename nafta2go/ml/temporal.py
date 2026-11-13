"""Features retrospectivas de precios publicados, sin persistencia ni entrenamiento."""

import math
from bisect import bisect_left, insort
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta
from itertools import groupby
from zoneinfo import ZoneInfo

from nafta2go.normalization.rules import CABA_BBOX, LOCAL_TIMEZONE

FEATURES_VERSION = "price-temporal-v1"
ZONE_DEGREES = 0.02


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


def build_temporal_dataset(rows, cutoff: datetime, *, window_days=30, min_history=5):
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
    ordered = sorted(
        rows,
        key=lambda r: (
            r["valid_from"],
            r["station_id"],
            r["product_id"],
            r["schedule_id"],
            r["source_row"],
        ),
    )
    for date, batch in groupby(ordered, key=lambda row: row["valid_from"]):
        if date.utcoffset() is not None:
            raise ValueError("Las fechas normalizadas deben ser locales sin zona")
        when = date.replace(tzinfo=ZoneInfo(LOCAL_TIMEZONE)).astimezone(UTC)
        partition = "train" if when < cutoff else "validation"
        pending, seen = [], set()
        for row in batch:
            key = (row["product_id"], row["schedule_id"])
            identity = (row["station_id"], *key)
            if identity in seen:
                raise ValueError("Observación duplicada en una misma fecha")
            seen.add(identity)
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
            totals[partition] += 1
            zone = (math.floor(lat / ZONE_DEGREES), math.floor(lon / ZONE_DEGREES))
            regional, city = windows[(*key, *zone)], windows[key]
            for window in (regional, city):
                window.expire(when - timedelta(days=window_days))
            history = regional if len(regional.prices) >= min_history else city
            scope = "zone" if history is regional else "caba"
            if len(history.prices) >= min_history:
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
            pending.append((identity, price, regional, city))
        # Primero predecir todo el instante; después incorporar sus precios al historial.
        for identity, price, regional, city in pending:
            regional.add(when, price)
            city.add(when, price)
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
