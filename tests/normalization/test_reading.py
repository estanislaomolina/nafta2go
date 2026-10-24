"""Tests de la lectura del CSV crudo con filtro de alcance."""

from pathlib import Path

import pytest

from nafta2go.normalization.reading import REQUIRED_COLUMNS, UnexpectedSchema, read_raw

FIX = Path(__file__).resolve().parents[1] / "fixtures"


def test_historico_filters_scope_and_numbers_rows():
    df = read_raw(FIX / "historico_sample.csv", "historico")
    assert len(df) == 7
    assert set(df["idproducto"]) == {"2", "3"}
    # Las filas 3 (gas oil de BUENOS AIRES) y 4 (GNC de CABA) quedan fuera del alcance.
    assert df["fila_origen"].tolist() == [1, 2, 5, 6, 7, 8, 9]


def test_vigente_filters_scope():
    df = read_raw(FIX / "vigente_sample.csv", "vigente")
    assert len(df) == 2
    assert df["fila_origen"].tolist() == [1, 3]


def test_keeps_only_required_columns_as_text():
    df = read_raw(FIX / "historico_sample.csv", "historico")
    assert list(df.columns) == REQUIRED_COLUMNS["historico"] + ["fila_origen"]
    assert df.loc[df["fila_origen"] == 9, "latitud"].item() == ""
    assert df.loc[df["fila_origen"] == 2, "precio"].item() == "45.67"


def test_row_numbers_survive_chunk_boundaries():
    whole = read_raw(FIX / "historico_sample.csv", "historico")
    chunked = read_raw(FIX / "historico_sample.csv", "historico", chunksize=2)
    assert chunked.equals(whole)


def test_missing_columns_clear_error(tmp_path):
    original = (FIX / "historico_sample.csv").read_text(encoding="utf-8-sig").splitlines()
    header = original[0].split(",")
    position = header.index("fecha_vigencia")
    rows = [",".join(header[:position] + header[position + 1 :])]
    broken = tmp_path / "sin_fecha.csv"
    broken.write_text("\n".join(rows) + "\n", encoding="utf-8")
    with pytest.raises(UnexpectedSchema, match="fecha_vigencia"):
        read_raw(broken, "historico")


def test_unknown_source_raises():
    with pytest.raises(ValueError, match="source"):
        read_raw(FIX / "vigente_sample.csv", "otro")


def test_no_rows_in_scope_returns_empty_frame(tmp_path):
    lines = (FIX / "vigente_sample.csv").read_text(encoding="utf-8-sig").splitlines()
    only_buenos_aires = tmp_path / "ba.csv"
    only_buenos_aires.write_text("\n".join([lines[0], lines[2]]) + "\n", encoding="utf-8")
    df = read_raw(only_buenos_aires, "vigente")
    assert df.empty
    assert list(df.columns) == REQUIRED_COLUMNS["vigente"] + ["fila_origen"]
