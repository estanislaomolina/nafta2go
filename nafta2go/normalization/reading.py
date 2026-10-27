"""Lectura por chunks del CSV crudo, filtrada a CABA y nafta.

El histórico pesa unos 780 MB: se lee en chunks y solo se conservan las
columnas necesarias, todas como texto, para que las reglas vean el valor
original sin conversiones de pandas.
"""

from pathlib import Path

import pandas as pd

from nafta2go.normalization.rules import CABA_PROVINCE, NAPHTHA_PRODUCTS, SOURCES

_COMMON_COLUMNS = [
    "idempresa",
    "empresa",
    "direccion",
    "provincia",
    "idproducto",
    "producto",
    "idtipohorario",
    "precio",
    "fecha_vigencia",
    "empresabandera",
    "latitud",
    "longitud",
]
REQUIRED_COLUMNS = {
    "vigente": _COMMON_COLUMNS,
    "historico": _COMMON_COLUMNS + ["anio", "mes"],
}
_PRODUCT_IDS = {str(product_id) for product_id in NAPHTHA_PRODUCTS}
_CSV_OPTIONS = {"dtype": str, "encoding": "utf-8-sig", "keep_default_na": False}


class UnexpectedSchema(ValueError):
    """El CSV no trae las columnas que esperan las reglas."""


def read_raw(path: Path, source: str, chunksize: int = 500_000) -> pd.DataFrame:
    """Filas de CABA y nafta con `fila_origen`: la posición en el archivo antes de filtrar."""
    if source not in SOURCES:
        raise ValueError(f"source: {source!r} no es un origen conocido")
    columns = REQUIRED_COLUMNS[source]
    _check_columns(path, columns)

    selected = []
    offset = 0
    for chunk in pd.read_csv(path, usecols=columns, chunksize=chunksize, **_CSV_OPTIONS):
        chunk = chunk[columns].assign(fila_origen=range(offset + 1, offset + len(chunk) + 1))
        offset += len(chunk)
        in_scope = (chunk["provincia"].str.strip().str.upper() == CABA_PROVINCE) & chunk[
            "idproducto"
        ].str.strip().isin(_PRODUCT_IDS)
        selected.append(chunk[in_scope])

    if not selected:
        return pd.DataFrame(columns=columns + ["fila_origen"])
    return pd.concat(selected, ignore_index=True)


def _check_columns(path: Path, columns: list[str]) -> None:
    header = pd.read_csv(path, nrows=0, **_CSV_OPTIONS).columns
    missing = [column for column in columns if column not in header]
    if missing:
        raise UnexpectedSchema(f"{path.name}: faltan las columnas {', '.join(missing)}")
