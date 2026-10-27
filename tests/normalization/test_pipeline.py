"""Tests del pipeline de normalización y su contrato con la ingesta (POC-06)."""

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd

from nafta2go.normalization.pipeline import normalize, normalize_capture
from nafta2go.normalization.reading import read_raw
from nafta2go.normalization.rules import RULES_VERSION
from nafta2go.persistence import repository as repo
from nafta2go.persistence.models import RawCapture
from nafta2go.services.ingestion import ingest

FIX = Path(__file__).resolve().parents[1] / "fixtures"
INGESTED = pd.Timestamp("2026-10-24 18:00")


def _historico():
    return normalize(read_raw(FIX / "historico_sample.csv", "historico"), "historico", INGESTED)


def test_historico_sample_end_to_end():
    r = _historico()
    assert r.report["filas_leidas"] == 7
    assert r.report["rechazos_por_motivo"] == {
        "fecha_invalida": 1,
        "fecha_futura": 1,
        "precio_no_positivo": 1,
    }
    assert r.report["filas_validas"] == len(r.rows) == 4
    assert r.report["filas_rechazadas"] == len(r.rejections) == 3
    assert r.report["alertas_por_tipo"] == {"fuera_de_caba": 1, "sin_coordenadas": 1}
    assert r.report["estaciones"] == 3
    assert r.report["fecha_min"] == "2015-07-01T09:00:00"
    assert r.report["fecha_max"] == "2019-03-01T11:31:00"
    assert r.rules_version == RULES_VERSION


def test_vigente_sample_end_to_end():
    raw = read_raw(FIX / "vigente_sample.csv", "vigente")
    r = normalize(raw, "vigente", INGESTED)
    assert r.report["filas_validas"] == 2
    assert r.rejections == []
    assert {row["tipo_nafta"] for row in r.rows} == {"super", "premium"}


def test_rows_match_persistence_contract():
    r = _historico()
    assert set(r.rows[0]) == {
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
    }
    assert {"fila_origen", "motivo"} <= set(r.rejections[0])


def test_keeps_original_values():
    rows = {row["fila_origen"]: row for row in _historico().rows}
    assert rows[2]["fecha_vigencia_original"] == "01/03/2019 11:31"
    assert rows[2]["precio_original"] == "45.67"
    assert rows[2]["fecha_vigencia"] == datetime(2019, 3, 1, 11, 31)
    assert rows[2]["precio"] == 45.67


def test_missing_coordinates_become_none():
    rows = {row["fila_origen"]: row for row in _historico().rows}
    assert rows[9]["latitud"] is None and rows[9]["longitud"] is None
    assert rows[9]["alertas"] == "sin_coordenadas"


def test_rejections_keep_raw_values_and_one_reason():
    rejections = {r["fila_origen"]: r for r in _historico().rejections}
    assert {k: r["motivo"] for k, r in rejections.items()} == {
        5: "fecha_invalida",
        6: "fecha_futura",
        7: "precio_no_positivo",
    }
    assert rejections[5]["fecha_vigencia"] == "30/07/0025 14:15"
    assert rejections[7]["precio"] == "0"


def test_invalid_date_wins_over_invalid_price():
    raw = read_raw(FIX / "historico_sample.csv", "historico")
    raw.loc[raw["fila_origen"] == 5, "precio"] = "s/d"
    rejections = {
        r["fila_origen"]: r["motivo"] for r in normalize(raw, "historico", INGESTED).rejections
    }
    assert rejections[5] == "fecha_invalida"


def test_conflicting_duplicates_are_rejected_and_exact_ones_counted():
    raw = read_raw(FIX / "vigente_sample.csv", "vigente")
    exact = raw.iloc[[0]].assign(fila_origen=10)
    conflict = raw.iloc[[1]].assign(fila_origen=11, precio="2200")
    r = normalize(pd.concat([raw, exact, conflict], ignore_index=True), "vigente", INGESTED)
    assert r.report["duplicados_exactos"] == 1
    assert r.report["rechazos_por_motivo"] == {"clave_duplicada_conflicto": 2}
    assert [row["fila_origen"] for row in r.rows] == [1]


def test_year_month_mismatch_is_only_checked_for_historico():
    raw = read_raw(FIX / "historico_sample.csv", "historico")
    raw.loc[raw["fila_origen"] == 1, "mes"] = "4"
    rejections = {
        r["fila_origen"]: r["motivo"] for r in normalize(raw, "historico", INGESTED).rejections
    }
    assert rejections[1] == "fecha_inconsistente_anio_mes"


def test_empty_input_gives_empty_result():
    raw = read_raw(FIX / "vigente_sample.csv", "vigente").iloc[0:0]
    r = normalize(raw, "vigente", INGESTED)
    assert r.rows == [] and r.rejections == []
    assert r.report["filas_leidas"] == 0
    assert r.report["fecha_min"] is None
    json.dumps(r.report)


def test_report_is_json_serializable():
    json.dumps(_historico().report)


def test_ingest_accepts_normalize_capture(engine, tmp_path):
    stored = tmp_path / "historico.csv"
    shutil.copy(FIX / "historico_sample.csv", stored)
    content = stored.read_bytes()
    capture = RawCapture(
        source="historico",
        url="http://datos.energia.gob.ar/precios-historicos.csv",
        sha256=hashlib.sha256(content).hexdigest(),
        size_bytes=len(content),
        stored_path=str(stored),
        fetched_at=INGESTED.to_pydatetime(),
    )
    run_id = ingest(engine, capture, normalize_capture)
    with engine.connect() as conn:
        assert repo.get_run(conn, run_id)["status"] == "succeeded"
        prices = repo.prices_for_run(conn, run_id)
        assert len(prices) == 4
        assert len(repo.rejections_for_run(conn, run_id)) == 3
    assert stored.read_bytes() == content
