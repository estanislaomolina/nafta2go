"""Tests del comando de ingesta con un CSV ya descargado (sin red)."""

import json
import os
import shutil
from datetime import datetime
from pathlib import Path

from nafta2go.normalization.__main__ import capture_from_file, main
from nafta2go.persistence import repository as repo
from nafta2go.persistence.database import create_db_engine

FIX = Path(__file__).resolve().parents[1] / "fixtures"


def test_ingests_file_and_prints_report(tmp_path, monkeypatch, capsys):
    url = f"sqlite:///{tmp_path / 'cli.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    assert main(["--source", "historico", "--file", str(FIX / "historico_sample.csv")]) == 0

    out = capsys.readouterr().out
    run_id = int(out.splitlines()[0].removeprefix("run_id: "))
    report = json.loads(out.split("\n", 1)[1])
    assert report["filas_validas"] == 4
    engine = create_db_engine(url)
    with engine.connect() as conn:
        assert repo.get_run(conn, run_id)["status"] == "succeeded"
    engine.dispose()


def test_failed_ingest_returns_error_code(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'cli.db'}")
    broken = tmp_path / "roto.csv"
    broken.write_text("idempresa,precio\n1,2\n", encoding="utf-8")
    assert main(["--source", "vigente", "--file", str(broken)]) == 1
    assert "faltan las columnas" in capsys.readouterr().err


def test_capture_from_file_uses_local_mtime(tmp_path):
    stored = tmp_path / "vigente.csv"
    shutil.copy(FIX / "vigente_sample.csv", stored)
    # 2026-10-24 21:30:05 UTC son las 18:30:05 en Argentina.
    os.utime(stored, (1792877405, 1792877405))
    capture = capture_from_file(stored, "vigente")
    assert capture.fetched_at == datetime(2026, 10, 24, 18, 30, 5)
    assert capture.size_bytes == stored.stat().st_size
    assert capture.stored_path == str(stored.resolve())
