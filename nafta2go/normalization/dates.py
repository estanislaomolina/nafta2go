"""Parseo de fechas según el formato real de cada origen y motivos de rechazo."""

import pandas as pd

from nafta2go.normalization.rules import (
    DATE_FORMAT,
    FUTURE_DATE,
    INCONSISTENT_YEAR_MONTH,
    INVALID_DATE,
    LOCAL_TIMEZONE,
)


def parse_dates(raw: pd.Series, source: str) -> pd.Series:
    """Devuelve datetime64[ns]; NaT si no respeta el formato o el año queda fuera de rango."""
    if source not in DATE_FORMAT:
        raise ValueError(f"source: {source!r} no es un origen conocido")
    return pd.to_datetime(raw, format=DATE_FORMAT[source], errors="coerce")


def date_reasons(
    dates: pd.Series,
    ingested_at: pd.Timestamp,
    anio: pd.Series | None = None,
    mes: pd.Series | None = None,
) -> pd.Series:
    """Primer motivo de rechazo de cada fecha, o None si es aceptable."""
    reasons = pd.Series([None] * len(dates), index=dates.index, dtype=object)
    invalid = dates.isna()
    future = ~invalid & (dates > ingested_at)
    reasons[invalid] = INVALID_DATE
    reasons[future] = FUTURE_DATE
    if anio is not None and mes is not None:
        year = pd.to_numeric(anio, errors="coerce").to_numpy()
        month = pd.to_numeric(mes, errors="coerce").to_numpy()
        mismatch = (dates.dt.year.to_numpy() != year) | (dates.dt.month.to_numpy() != month)
        reasons[~invalid & ~future & mismatch] = INCONSISTENT_YEAR_MONTH
    return reasons


def local_now() -> pd.Timestamp:
    """Hora actual de Argentina sin zona, comparable con las fechas de la fuente."""
    return pd.Timestamp.now(tz=LOCAL_TIMEZONE).tz_localize(None)
