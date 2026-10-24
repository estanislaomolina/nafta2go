"""Pipeline de normalización: del CSV crudo filtrado al NormalizationResult de POC-06.

Orden de las reglas: fechas, precio, duplicados (solo entre las filas sin
motivo) y alertas. Cada fila rechazada lleva un único motivo, el primero que
aplica, y conserva sus valores crudos.
"""

from pathlib import Path

import pandas as pd

from nafta2go.normalization.dates import date_reasons, parse_dates
from nafta2go.normalization.reading import read_raw
from nafta2go.normalization.rules import ALERT_SEPARATOR, NAPHTHA_PRODUCTS, RULES_VERSION
from nafta2go.normalization.validation import (
    alerts,
    parse_prices,
    price_reasons,
    resolve_duplicates,
)
from nafta2go.persistence.models import NormalizationResult, RawCapture

ROW_COLUMNS = [
    "fila_origen",
    "idempresa",
    "empresa",
    "empresabandera",
    "direccion",
    "idproducto",
    "tipo_nafta",
    "idtipohorario",
    "precio",
    "fecha_vigencia",
    "latitud",
    "longitud",
    "fecha_vigencia_original",
    "precio_original",
    "alertas",
]


def normalize(raw: pd.DataFrame, source: str, ingested_at: pd.Timestamp) -> NormalizationResult:
    raw = raw.reset_index(drop=True)
    typed = _typed(raw, source)

    historico = source == "historico"
    reasons = date_reasons(
        typed["fecha_vigencia"],
        ingested_at,
        raw["anio"] if historico else None,
        raw["mes"] if historico else None,
    )
    reasons = reasons.where(reasons.notna(), price_reasons(typed["precio"]))

    kept, conflicts, exact_duplicates = resolve_duplicates(typed[reasons.isna()])
    reasons[conflicts.index] = conflicts["motivo"]
    kept = kept.assign(alertas=alerts(kept))

    rejected = reasons.dropna()
    rows = [_row(record) for record in kept[ROW_COLUMNS].to_dict("records")]
    rejections = raw.loc[rejected.index].assign(motivo=rejected).to_dict("records")
    report = _report(raw, kept, rejected, exact_duplicates)
    return NormalizationResult(rows, rejections, report, RULES_VERSION)


def normalize_capture(capture: RawCapture) -> NormalizationResult:
    """Normalizador que recibe `ingest()`: lee la captura guardada y aplica las reglas."""
    raw = read_raw(Path(capture.stored_path), capture.source)
    return normalize(raw, capture.source, ingested_at=pd.Timestamp(capture.fetched_at))


def _typed(raw: pd.DataFrame, source: str) -> pd.DataFrame:
    product_id = raw["idproducto"].astype(int)
    return pd.DataFrame(
        {
            "fila_origen": raw["fila_origen"].astype(int),
            "idempresa": raw["idempresa"].astype(int),
            "empresa": raw["empresa"],
            "empresabandera": raw["empresabandera"],
            "direccion": raw["direccion"],
            "idproducto": product_id,
            "tipo_nafta": product_id.map(NAPHTHA_PRODUCTS),
            "idtipohorario": raw["idtipohorario"].astype(int),
            "precio": parse_prices(raw["precio"]),
            "fecha_vigencia": parse_dates(raw["fecha_vigencia"], source),
            "latitud": pd.to_numeric(raw["latitud"], errors="coerce"),
            "longitud": pd.to_numeric(raw["longitud"], errors="coerce"),
            "fecha_vigencia_original": raw["fecha_vigencia"],
            "precio_original": raw["precio"],
        },
        index=raw.index,
    )


def _row(record: dict) -> dict:
    record["fecha_vigencia"] = record["fecha_vigencia"].to_pydatetime()
    for column in ("latitud", "longitud"):
        if pd.isna(record[column]):
            record[column] = None
    return record


def _report(raw: pd.DataFrame, kept: pd.DataFrame, rejected: pd.Series, exact: int) -> dict:
    alert_counts = kept["alertas"].str.split(ALERT_SEPARATOR).explode()
    alert_counts = alert_counts[alert_counts.astype(bool)].value_counts()
    dates = kept["fecha_vigencia"]
    return {
        "filas_leidas": len(raw),
        "filas_validas": len(kept),
        "filas_rechazadas": len(rejected),
        "duplicados_exactos": exact,
        "rechazos_por_motivo": {str(k): int(v) for k, v in rejected.value_counts().items()},
        "alertas_por_tipo": {str(k): int(v) for k, v in alert_counts.items()},
        "estaciones": int(kept["idempresa"].nunique()),
        "fecha_min": dates.min().isoformat() if len(dates) else None,
        "fecha_max": dates.max().isoformat() if len(dates) else None,
    }
