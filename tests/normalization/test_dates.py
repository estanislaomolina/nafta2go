"""Tests del parseo y la validación de fechas por origen."""

import pandas as pd
import pytest

from nafta2go.normalization.dates import date_reasons, local_now, parse_dates


def test_vigente_iso_format():
    s = parse_dates(pd.Series(["2026-09-22 09:05:00"]), "vigente")
    assert s.iloc[0] == pd.Timestamp("2026-09-22 09:05:00")


def test_historico_is_day_first():
    s = parse_dates(pd.Series(["01/05/2026 12:43"]), "historico")
    assert s.iloc[0] == pd.Timestamp("2026-05-01 12:43")


def test_historico_mistyped_year_is_nat():
    s = parse_dates(pd.Series(["30/07/0025 14:15", "07/02/6202 06:00"]), "historico")
    assert s.isna().all()


def test_wrong_format_is_nat():
    assert parse_dates(pd.Series(["2026-05-01 12:43:00"]), "historico").isna().all()


def test_unknown_source_raises():
    with pytest.raises(ValueError, match="source"):
        parse_dates(pd.Series(["2026-05-01 12:43:00"]), "otro")


def test_reasons_order_and_values():
    ingested = pd.Timestamp("2026-10-24 18:00")
    dates = pd.Series(
        pd.to_datetime(["2026-10-23 10:00", None, "2044-01-01 00:00", "2026-05-01 12:43"])
    )
    anio = pd.Series(["2026", "2026", "2044", "2026"])
    mes = pd.Series(["10", "1", "1", "6"])
    assert date_reasons(dates, ingested, anio, mes).tolist() == [
        None,
        "fecha_invalida",
        "fecha_futura",
        "fecha_inconsistente_anio_mes",
    ]


def test_future_uses_local_time():
    # 23:00 locales del 24/10 con ingesta a las 23:30 locales (02:30 UTC del 25/10): no es futura
    ingested = (
        pd.Timestamp("2026-10-25 02:30", tz="UTC")
        .tz_convert("America/Argentina/Buenos_Aires")
        .tz_localize(None)
    )
    assert date_reasons(pd.Series([pd.Timestamp("2026-10-24 23:00")]), ingested).tolist() == [None]


def test_local_now_is_naive_argentina_time():
    now = local_now()
    utc = pd.Timestamp.now(tz="UTC").tz_localize(None)
    assert now.tz is None
    # Argentina no tiene horario de verano: siempre UTC-3.
    assert abs((utc - now).total_seconds() - 3 * 3600) < 60
