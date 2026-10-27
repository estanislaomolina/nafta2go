"""Validaciones de precio, coordenadas, precios atípicos y claves duplicadas.

Las reglas no corrigen datos: rechazan con un motivo o marcan una alerta.
"""

import pandas as pd

from nafta2go.normalization.rules import (
    ALERT_SEPARATOR,
    CABA_BBOX,
    CONFLICTING_DUPLICATE,
    INVALID_PRICE,
    KEY,
    MISSING_COORDINATES,
    NON_POSITIVE_PRICE,
    OUTLIER_MIN_GROUP,
    OUTLIER_PRICE,
    OUTLIER_RATIO,
    OUTSIDE_CABA,
)

PRICE_PATTERN = r"^\d+(\.\d+)?$"


def parse_prices(raw: pd.Series) -> pd.Series:
    """Devuelve float64; NaN si el valor no es un número con punto decimal."""
    text = raw.astype(str)
    valid = text.str.fullmatch(PRICE_PATTERN)
    return pd.to_numeric(text.where(valid), errors="coerce").astype("float64")


def price_reasons(prices: pd.Series) -> pd.Series:
    """Motivo de rechazo de cada precio, o None si es aceptable."""
    reasons = pd.Series([None] * len(prices), index=prices.index, dtype=object)
    reasons[prices <= 0] = NON_POSITIVE_PRICE
    reasons[prices.isna()] = INVALID_PRICE
    return reasons


def alerts(df: pd.DataFrame) -> pd.Series:
    """Alertas de cada fila separadas por ';', en orden fijo, o '' si no hay ninguna."""
    flags = {
        OUTLIER_PRICE: _outlier_prices(df),
        OUTSIDE_CABA: _outside_caba(df),
        MISSING_COORDINATES: df["latitud"].isna() | df["longitud"].isna(),
    }
    labels = [flag.map({True: name, False: ""}).astype(str) for name, flag in flags.items()]
    joined = labels[0].str.cat(labels[1:], sep=ALERT_SEPARATOR)
    return joined.str.replace(f"{ALERT_SEPARATOR}+", ALERT_SEPARATOR, regex=True).str.strip(
        ALERT_SEPARATOR
    )


def resolve_duplicates(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, int]:
    """Descarta duplicados exactos y rechaza las claves repetidas con precios distintos."""
    exact = df.duplicated(KEY + ["precio"], keep="first")
    unique = df[~exact]
    conflict = unique.duplicated(KEY, keep=False)
    rejected = unique[conflict].assign(motivo=CONFLICTING_DUPLICATE)
    return unique[~conflict], rejected, int(exact.sum())


def _outlier_prices(df: pd.DataFrame) -> pd.Series:
    groups = df.groupby([df["fecha_vigencia"].dt.to_period("M"), df["tipo_nafta"]])["precio"]
    median = groups.transform("median")
    size = groups.transform("size")
    far = (df["precio"] > median * OUTLIER_RATIO) | (df["precio"] < median / OUTLIER_RATIO)
    return (size >= OUTLIER_MIN_GROUP) & far


def _outside_caba(df: pd.DataFrame) -> pd.Series:
    lat, lon = df["latitud"], df["longitud"]
    inside = lat.between(CABA_BBOX["lat_min"], CABA_BBOX["lat_max"]) & lon.between(
        CABA_BBOX["lon_min"], CABA_BBOX["lon_max"]
    )
    return lat.notna() & lon.notna() & ~inside
