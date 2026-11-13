"""Tests del comando de ingesta con un CSV ya descargado (sin red)."""

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

import pytest
import requests

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


@pytest.mark.parametrize("stage", ["catalog", "download"])
def test_network_failures_have_run_id_and_json(tmp_path, monkeypatch, capsys, stage):
    url = f"sqlite:///{tmp_path / 'network.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    target = "nafta2go.normalization.__main__"
    monkeypatch.setattr(f"{target}.discover_resources", Mock(return_value={"vigente": object()}))
    monkeypatch.setattr("nafta2go.adapters.acquisition.time.sleep", lambda _: None)
    failing = "discover_resources" if stage == "catalog" else "download"
    monkeypatch.setattr(f"{target}.{failing}", Mock(side_effect=requests.Timeout("token=secreto")))
    assert main(["--source", "vigente", "--json"]) == 1
    output = capsys.readouterr()
    summary = json.loads(output.out)
    assert summary["status"] == "failed"
    assert summary["report"]["acquisition_attempts"] == 3
    assert summary["duration_seconds"] >= 0
    assert summary["started_at"].endswith("Z")
    assert "secreto" not in output.out + output.err
    engine = create_db_engine(url)
    with engine.connect() as conn:
        assert repo.get_run(conn, summary["run_id"])["status"] == "failed"
    engine.dispose()


def test_success_json_keeps_report_and_version(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'json.db'}")
    assert (
        main(["--source", "historico", "--file", str(FIX / "historico_sample.csv"), "--json"]) == 0
    )
    summary = json.loads(capsys.readouterr().out)
    assert summary["status"] == "succeeded"
    assert summary["report"]["filas_validas"] == 4
    assert summary["rules_version"]


def test_missing_file_is_registered(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'missing.db'}")
    assert main(["--source", "vigente", "--file", str(tmp_path / "missing.csv"), "--json"]) == 1
    assert json.loads(capsys.readouterr().out)["status"] == "failed"


def test_downloaded_capture_is_normalized(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'download.db'}")
    target = "nafta2go.normalization.__main__"
    resource = object()
    monkeypatch.setattr(f"{target}.discover_resources", Mock(return_value={"historico": resource}))
    download = Mock(return_value=capture_from_file(FIX / "historico_sample.csv", "historico"))
    monkeypatch.setattr(f"{target}.download", download)
    assert main(["--source", "historico", "--json"]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["status"] == "succeeded"
    assert summary["report"]["filas_validas"] == 4
    assert download.call_args.args[:2] == (resource, "historico")


@pytest.mark.parametrize("stage", ["catalog", "stream"])
def test_remote_retry_preserves_one_run_and_closes_sessions(tmp_path, monkeypatch, capsys, stage):
    from sqlalchemy import select

    from nafta2go.persistence.schema import ingestion_runs

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'retry.db'}")
    monkeypatch.setattr("nafta2go.normalization.__main__.DATA_DIR", tmp_path)
    sleep = Mock()
    monkeypatch.setattr("nafta2go.adapters.acquisition.time.sleep", sleep)
    content = (FIX / "historico_sample.csv").read_bytes()
    catalog = requests.Response()
    catalog.status_code = 200
    catalog._content = json.dumps(
        {
            "result": {
                "resources": [
                    {
                        "id": name,
                        "name": name,
                        "url": "https://example.test/file.csv",
                        "format": "CSV",
                        "size": len(content),
                    }
                    for name in ("Precios vigentes", "Precios historicos")
                ]
            }
        }
    ).encode()
    response = requests.Response()
    response.status_code = 200
    response.iter_content = Mock(return_value=iter([content]))
    response.close = Mock()
    sessions = [requests.Session(), requests.Session()]
    broken = requests.Response()
    broken.status_code = 200

    def interrupted(chunk_size):
        yield content[:12]
        raise requests.exceptions.ChunkedEncodingError("corte")

    broken.iter_content = interrupted
    broken.close = Mock()
    sessions[0].get = (
        Mock(side_effect=requests.ConnectionError("DNS"))
        if stage == "catalog"
        else Mock(side_effect=[catalog, broken])
    )
    sessions[1].get = Mock(side_effect=[catalog, response])
    for session in sessions:
        session.close = Mock(wraps=session.close)
    monkeypatch.setattr(
        "nafta2go.normalization.__main__.requests.Session", Mock(side_effect=sessions)
    )
    assert main(["--source", "historico", "--json"]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["report"]["acquisition_attempts"] == 2
    assert summary["report"]["filas_validas"] == 4
    sleep.assert_called_once_with(60)
    for session in sessions:
        session.close.assert_called_once_with()
    response.close.assert_called_once_with()
    if stage == "stream":
        broken.close.assert_called_once_with()
    files = list((tmp_path / "raw/historico").iterdir())
    assert len(files) == 1 and files[0].read_bytes() == content
    engine = create_db_engine(f"sqlite:///{tmp_path / 'retry.db'}")
    with engine.connect() as conn:
        assert len(conn.execute(select(ingestion_runs)).all()) == 1
        assert repo.raw_capture_for_run(conn, summary["run_id"])["stored_path"] == str(files[0])
    engine.dispose()
