"""Tests del congelado del escenario histórico (sin red)."""

import hashlib
import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from nafta2go.normalization.pipeline import normalize
from nafta2go.normalization.reading import read_raw
from scripts.freeze_scenario import ChecksumMismatch, freeze, main

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "vigente_sample.csv"
SHA = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
FETCHED = datetime(2026, 10, 24, 17, 57, 10)
URL = "http://datos.energia.gob.ar/vigentes.csv"


def test_extract_keeps_only_caba_naphtha_with_original_header(tmp_path):
    scenario = freeze(FIXTURE, SHA, URL, FETCHED, tmp_path)
    extract = tmp_path / "precios_caba_nafta.csv"
    original_header = FIXTURE.read_text(encoding="utf-8-sig").splitlines()[0]
    assert extract.read_text(encoding="utf-8-sig").splitlines()[0] == original_header
    assert scenario["extract"]["rows"] == 2
    df = pd.read_csv(extract, dtype=str, encoding="utf-8-sig", keep_default_na=False)
    assert set(df["provincia"]) == {"CAPITAL FEDERAL"} and set(df["idproducto"]) == {"2", "3"}


def test_scenario_records_hashes_and_reference(tmp_path):
    freeze(FIXTURE, SHA, URL, FETCHED, tmp_path)
    scenario = json.loads((tmp_path / "escenario.json").read_text(encoding="utf-8"))
    extract = (tmp_path / "precios_caba_nafta.csv").read_bytes()
    assert scenario["source"]["sha256"] == SHA
    assert scenario["source"]["bytes"] == FIXTURE.stat().st_size
    assert scenario["source"]["fetched_at_local"] == "2026-10-24T17:57:10"
    assert scenario["extract"]["sha256"] == hashlib.sha256(extract).hexdigest()
    assert scenario["reference_at"] == "2026-10-24T18:00:00-03:00"


def test_wrong_checksum_writes_nothing(tmp_path):
    with pytest.raises(ChecksumMismatch):
        freeze(FIXTURE, "0" * 64, URL, FETCHED, tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_freezing_twice_gives_the_same_bytes(tmp_path):
    freeze(FIXTURE, SHA, URL, FETCHED, tmp_path / "a")
    freeze(FIXTURE, SHA, URL, FETCHED, tmp_path / "b")
    for name in ("precios_caba_nafta.csv", "escenario.json"):
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()


def test_extract_normalizes_like_the_original(tmp_path):
    freeze(FIXTURE, SHA, URL, FETCHED, tmp_path)
    ingested = pd.Timestamp(FETCHED)
    full = normalize(read_raw(FIXTURE, "vigente"), "vigente", ingested).rows
    cut = normalize(read_raw(tmp_path / "precios_caba_nafta.csv", "vigente"), "vigente", ingested)
    # fila_origen cambia porque el recorte tiene menos filas; el resto es idéntico.
    strip = [{k: v for k, v in row.items() if k != "fila_origen"} for row in full]
    assert strip == [{k: v for k, v in row.items() if k != "fila_origen"} for row in cut.rows]


def test_main_returns_error_on_wrong_checksum(tmp_path, capsys):
    argv = ["--file", str(FIXTURE), "--sha256", "0" * 64, "--url", URL]
    assert main([*argv, "--fetched-at", FETCHED.isoformat(), "--out", str(tmp_path)]) == 1
    assert "SHA-256" in capsys.readouterr().err
