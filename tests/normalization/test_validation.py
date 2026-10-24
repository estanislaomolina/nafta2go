"""Tests de las validaciones de precio, coordenadas, atípicos y duplicados."""

import pandas as pd

from nafta2go.normalization.validation import (
    alerts,
    parse_prices,
    price_reasons,
    resolve_duplicates,
)


def _frame(prices, lat=None, lon=None, month="2026-05", fuel="super"):
    n = len(prices)
    return pd.DataFrame(
        {
            "precio": [float(p) for p in prices],
            "fecha_vigencia": pd.to_datetime([f"{month}-{day + 1:02d} 10:00" for day in range(n)]),
            "tipo_nafta": [fuel] * n,
            "latitud": [-34.60] * n if lat is None else lat,
            "longitud": [-58.40] * n if lon is None else lon,
        }
    )


def _dups(prices):
    n = len(prices)
    return pd.DataFrame(
        {
            "fila_origen": list(range(1, n + 1)),
            "idempresa": ["9930"] * n,
            "idproducto": ["2"] * n,
            "idtipohorario": ["2"] * n,
            "fecha_vigencia": [pd.Timestamp("2026-05-01 12:43")] * n,
            "precio": [float(p) for p in prices],
        }
    )


def test_parse_prices_formats():
    assert parse_prices(pd.Series(["2354", "45.67"])).tolist() == [2354.0, 45.67]
    assert parse_prices(pd.Series(["1.234,5", "s/d", ""])).isna().all()


def test_parse_prices_rejects_signs_and_exponents():
    assert parse_prices(pd.Series(["-5", "1e3", " 12", "12.", ".5"])).isna().all()


def test_price_reasons():
    assert price_reasons(pd.Series([2000.0, 0.0, -1.0, float("nan")])).tolist() == [
        None,
        "precio_no_positivo",
        "precio_no_positivo",
        "precio_invalido",
    ]


def test_outlier_x100_alert():
    df = _frame(prices=[190, 192, 193, 194, 196, 19320])  # mismo mes y tipo_nafta
    assert alerts(df).tolist()[-1] == "precio_atipico"
    assert alerts(df).tolist()[0] == ""


def test_outlier_too_low_alert():
    df = _frame(prices=[1900, 1920, 1930, 1940, 1960, 19.3])
    assert alerts(df).tolist() == ["", "", "", "", "", "precio_atipico"]


def test_no_outlier_alert_in_small_group():
    assert alerts(_frame(prices=[190, 192, 19320])).tolist() == ["", "", ""]


def test_outlier_groups_by_month_and_fuel():
    super_may = _frame(prices=[190, 192, 193, 194, 196])
    premium_may = _frame(prices=[2400], fuel="premium")
    super_june = _frame(prices=[2400], month="2026-06")
    df = pd.concat([super_may, premium_may, super_june], ignore_index=True)
    assert alerts(df).tolist() == [""] * 7


def test_outside_caba_and_missing_coordinates_alerts():
    df = _frame(prices=[200, 200], lat=[-34.70175, None], lon=[-58.58013, None])
    assert alerts(df).tolist() == ["fuera_de_caba", "sin_coordenadas"]


def test_alerts_are_joined_in_order():
    df = _frame(prices=[190, 192, 193, 194, 196, 19320])
    df.loc[5, ["latitud", "longitud"]] = [-34.70175, -58.58013]
    assert alerts(df).tolist()[-1] == "precio_atipico;fuera_de_caba"


def test_alerts_of_empty_frame_is_empty_series():
    result = alerts(_frame(prices=[]))
    assert isinstance(result, pd.Series) and result.empty


def test_exact_duplicate_keeps_one():
    kept, rejected, exact = resolve_duplicates(_dups(prices=[2000, 2000]))
    assert len(kept) == 1 and rejected.empty and exact == 1
    assert kept["fila_origen"].tolist() == [1]


def test_conflicting_duplicate_rejects_all():
    kept, rejected, _ = resolve_duplicates(_dups(prices=[2000, 2100]))
    assert kept.empty
    assert rejected["motivo"].tolist() == ["clave_duplicada_conflicto"] * 2


def test_distinct_keys_are_kept():
    df = _dups(prices=[2000, 2100])
    df.loc[1, "idtipohorario"] = "3"
    kept, rejected, exact = resolve_duplicates(df)
    assert len(kept) == 2 and rejected.empty and exact == 0
