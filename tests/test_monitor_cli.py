"""El monitor emite JSON seguro y códigos de salida para el supervisor."""

import json
from datetime import UTC, datetime

from nafta2go.monitor.__main__ import main
from nafta2go.persistence import repository as repo
from nafta2go.persistence.database import create_db_engine


def test_monitor_reports_missing_and_failed_ingestion(
    engine, database_url, monkeypatch, capsys, caplog
):
    monkeypatch.setenv("DATABASE_URL", database_url)
    assert main([]) == 1
    output = capsys.readouterr()
    assert json.loads(output.out)["alerts"][0]["kind"] == "missing"
    with engine.begin() as conn:
        now = datetime.now(UTC).replace(tzinfo=None)
        run_id = repo.start_run(conn, "vigente", now)
        repo.finish_run(conn, run_id, "failed", now, error="token=secreto")
    assert main([]) == 1
    output = capsys.readouterr()
    assert json.loads(output.out)["alerts"][0]["kind"] == "failed"
    assert "secreto" not in output.out + output.err
    assert "secreto" not in caplog.text


def test_monitor_healthy_exit_code(engine, database_url, monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", database_url)
    with engine.begin() as conn:
        now = datetime.now(UTC).replace(tzinfo=None)
        run_id = repo.start_run(conn, "vigente", now)
        repo.finish_run(conn, run_id, "succeeded", now)
    assert main([]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "healthy"


def test_unmigrated_database_is_monitor_error(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'empty.db'}")
    assert main([]) == 2
    summary = json.loads(capsys.readouterr().out)
    assert summary["status"] == "monitor_error"
    assert summary["error_type"] == "OperationalError"


def test_engine_creation_failure_is_safe(monkeypatch, capsys):
    def broken():
        raise ValueError("base://usuario:secreto@host")

    monkeypatch.setattr("nafta2go.monitor.__main__.create_db_engine", broken)
    assert main([]) == 2
    output = capsys.readouterr()
    assert json.loads(output.out)["status"] == "monitor_error"
    assert "secreto" not in output.out + output.err


def test_monitor_closes_engine(database_url, engine, monkeypatch, capsys):
    from unittest.mock import Mock

    db = create_db_engine(database_url)
    dispose = Mock(wraps=db.dispose)
    monkeypatch.setattr(db, "dispose", dispose)
    monkeypatch.setattr("nafta2go.monitor.__main__.create_db_engine", lambda: db)
    assert main([]) == 1
    dispose.assert_called_once()
