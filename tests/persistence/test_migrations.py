"""Tests de las migraciones y la configuración de la base."""

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

from nafta2go.persistence import schema
from nafta2go.persistence.database import (
    DEFAULT_URL,
    ROOT,
    alembic_config,
    create_db_engine,
    database_url,
    upgrade_to_head,
)

TABLES = {"ingestion_runs", "raw_captures", "station_prices", "rejected_rows", "recommendations"}


def test_upgrade_creates_all_tables(engine):
    assert TABLES <= set(inspect(engine).get_table_names())


def test_migration_matches_schema_metadata(engine):
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), schema.metadata)
    assert diff == []


def test_downgrade_to_base_removes_tables(database_url):
    upgrade_to_head(database_url)
    command.downgrade(alembic_config(database_url), "base")
    db = create_db_engine(database_url)
    assert set(inspect(db).get_table_names()) == {"alembic_version"}
    db.dispose()


def test_foreign_keys_are_enforced(engine):
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(
            schema.raw_captures.insert().values(
                run_id=999,
                url="http://x",
                sha256="0" * 64,
                size_bytes=1,
                stored_path="data/raw/x.csv",
                fetched_at=datetime(2026, 10, 24),
            )
        )


def test_database_url_from_env(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert database_url() == DEFAULT_URL
    monkeypatch.setenv("DATABASE_URL", "sqlite:///otra.db")
    assert database_url() == "sqlite:///otra.db"


def test_sqlite_engine_creates_parent_directory(tmp_path):
    url = f"sqlite:///{tmp_path / 'nuevo' / 'dir' / 'db.sqlite'}"
    upgrade_to_head(url)
    assert (tmp_path / "nuevo" / "dir" / "db.sqlite").exists()


def test_alembic_cli_upgrade_from_repo_root(tmp_path):
    db_file = tmp_path / "cli.db"
    env = os.environ | {"DATABASE_URL": f"sqlite:///{db_file}"}
    completed = subprocess.run(
        [str(Path(sys.executable).parent / "alembic"), "upgrade", "head"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert db_file.exists()
    assert "Running upgrade  -> 0001" in completed.stderr


def test_default_url_is_anchored_to_repo_root(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.chdir(tmp_path)
    path = Path(make_url(database_url()).database)
    assert path == ROOT / "data" / "nafta2go.db"
