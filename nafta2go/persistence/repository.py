"""Lectura y escritura de ejecuciones, precios, rechazos y recomendaciones.

Las funciones reciben una conexión: la transacción la decide quien llama.
"""

import math
from collections.abc import Iterable, Mapping
from datetime import datetime
from decimal import Decimal
from typing import Literal

from sqlalchemy import Connection, select

from nafta2go.persistence.models import RawCapture
from nafta2go.persistence.schema import (
    ingestion_runs,
    raw_captures,
    recommendations,
    rejected_rows,
    station_prices,
)

SOURCES = ("vigente", "historico")
# Sólo parámetros del vehículo y del presupuesto: nunca origen ni destino (RNF03).
ALLOWED_REQUEST_KEYS = frozenset(
    {
        "fuel_type",
        "consumption_l_per_100km",
        "tank_capacity_l",
        "remaining_l",
        "budget_ars",
        "reserve_l",
        "max_candidates",
    }
)


def start_run(conn: Connection, source: str, started_at: datetime) -> int:
    if source not in SOURCES:
        raise ValueError(f"source: debe ser uno de {SOURCES}, no {source!r}")
    result = conn.execute(
        ingestion_runs.insert().values(source=source, status="running", started_at=started_at)
    )
    return result.inserted_primary_key[0]


def finish_run(
    conn: Connection,
    run_id: int,
    status: Literal["succeeded", "failed"],
    finished_at: datetime,
    report: dict | None = None,
    error: str | None = None,
    rules_version: str | None = None,
) -> None:
    if status not in ("succeeded", "failed"):
        raise ValueError(f"status: {status!r} no cierra una ejecución")
    conn.execute(
        ingestion_runs.update()
        .where(ingestion_runs.c.id == run_id)
        .values(
            status=status,
            finished_at=finished_at,
            report=report,
            error=error,
            rules_version=rules_version,
        )
    )


def get_run(conn: Connection, run_id: int) -> dict | None:
    row = conn.execute(select(ingestion_runs).where(ingestion_runs.c.id == run_id)).first()
    return dict(row._mapping) if row else None


def latest_successful_run(conn: Connection, source: str) -> int | None:
    return conn.execute(
        select(ingestion_runs.c.id)
        .where(ingestion_runs.c.source == source, ingestion_runs.c.status == "succeeded")
        .order_by(ingestion_runs.c.finished_at.desc(), ingestion_runs.c.id.desc())
        .limit(1)
    ).scalar()


def add_raw_capture(conn: Connection, run_id: int, capture: RawCapture) -> None:
    conn.execute(
        raw_captures.insert().values(
            run_id=run_id,
            url=capture.url,
            sha256=capture.sha256,
            size_bytes=capture.size_bytes,
            stored_path=capture.stored_path,
            fetched_at=capture.fetched_at,
            source_last_modified=capture.source_last_modified,
        )
    )


def find_run_by_sha256(conn: Connection, source: str, sha256: str) -> int | None:
    return conn.execute(
        select(ingestion_runs.c.id)
        .join(raw_captures, raw_captures.c.run_id == ingestion_runs.c.id)
        .where(
            ingestion_runs.c.source == source,
            ingestion_runs.c.status == "succeeded",
            raw_captures.c.sha256 == sha256,
        )
        .order_by(ingestion_runs.c.id.desc())
        .limit(1)
    ).scalar()


def add_prices(conn: Connection, run_id: int, rows: Iterable[Mapping[str, object]]) -> int:
    values = [
        {
            "run_id": run_id,
            "source_row": int(row["fila_origen"]),
            "station_id": int(row["idempresa"]),
            "company": str(row["empresa"]),
            "brand": str(row["empresabandera"]),
            "address": str(row["direccion"]),
            "product_id": int(row["idproducto"]),
            "fuel_type": str(row["tipo_nafta"]),
            "schedule_id": int(row["idtipohorario"]),
            "price": Decimal(str(row["precio"])),
            "valid_from": row["fecha_vigencia"],
            "lat": _optional_float(row["latitud"]),
            "lon": _optional_float(row["longitud"]),
            "valid_from_raw": str(row["fecha_vigencia_original"]),
            "price_raw": str(row["precio_original"]),
            "alerts": str(row.get("alertas") or ""),
        }
        for row in rows
    ]
    if values:
        conn.execute(station_prices.insert(), values)
    return len(values)


def prices_for_run(conn: Connection, run_id: int, fuel_type: str | None = None) -> list[dict]:
    query = select(station_prices).where(station_prices.c.run_id == run_id)
    if fuel_type is not None:
        query = query.where(station_prices.c.fuel_type == fuel_type)
    return [dict(row._mapping) for row in conn.execute(query.order_by(station_prices.c.id))]


def add_rejections(conn: Connection, run_id: int, rows: Iterable[Mapping[str, object]]) -> int:
    values = []
    for row in rows:
        raw = {k: _json_safe(v) for k, v in row.items() if k not in ("fila_origen", "motivo")}
        values.append(
            {
                "run_id": run_id,
                "source_row": int(row["fila_origen"]),
                "reason": str(row["motivo"]),
                "raw": raw,
            }
        )
    if values:
        conn.execute(rejected_rows.insert(), values)
    return len(values)


def rejections_for_run(conn: Connection, run_id: int) -> list[dict]:
    query = select(rejected_rows).where(rejected_rows.c.run_id == run_id)
    return [dict(row._mapping) for row in conn.execute(query.order_by(rejected_rows.c.id))]


def record_recommendation(
    conn: Connection,
    data_run_id: int,
    engine_version: str,
    routing_provider: str,
    request: Mapping[str, object],
    result: Mapping[str, object],
    created_at: datetime,
) -> int:
    forbidden = sorted(set(request) - ALLOWED_REQUEST_KEYS)
    if forbidden:
        raise ValueError(f"request: campos no permitidos {forbidden}; no se guardan ubicaciones")
    run = get_run(conn, data_run_id)
    if run is None or run["status"] != "succeeded":
        raise ValueError(f"data_run_id: la ejecución {data_run_id} no está succeeded")
    inserted = conn.execute(
        recommendations.insert().values(
            created_at=created_at,
            data_run_id=data_run_id,
            engine_version=engine_version,
            routing_provider=routing_provider,
            request={k: _json_safe(v) for k, v in request.items()},
            result=dict(result),
        )
    )
    return inserted.inserted_primary_key[0]


def get_recommendation(conn: Connection, recommendation_id: int) -> dict | None:
    query = select(recommendations).where(recommendations.c.id == recommendation_id)
    row = conn.execute(query).first()
    return dict(row._mapping) if row else None


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    number = float(value)
    return None if math.isnan(number) else number


def _json_safe(value: object) -> object:
    if value is None or isinstance(value, bool | int | str):
        return value
    if isinstance(value, float):
        return None if not math.isfinite(value) else value
    return str(value)
