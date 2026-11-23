"""Conexiones SQLite: una lectura en curso no puede bloquear el guardado de otra consulta (#173)."""

import time

from sqlalchemy import text

from nafta2go.persistence.database import create_db_engine


def test_write_commits_while_another_connection_is_reading(tmp_path):
    engine = create_db_engine(f"sqlite:///{tmp_path / 'concurrencia.db'}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE t (id INTEGER PRIMARY KEY)"))
        conn.execute(text("INSERT INTO t VALUES (1)"))
    reader = engine.raw_connection()
    try:
        cursor = reader.cursor()
        cursor.execute("BEGIN")
        assert cursor.execute("SELECT id FROM t").fetchone() == (1,)
        started = time.monotonic()
        # Con el diario por defecto este commit espera a la lectura y falla por timeout.
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO t VALUES (2)"))
        assert time.monotonic() - started < 1
        # La lectura abierta conserva su instantánea.
        assert cursor.execute("SELECT count(*) FROM t").fetchone() == (1,)
        cursor.execute("COMMIT")
    finally:
        reader.close()
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM t")).scalar() == 2
    engine.dispose()


def test_file_databases_use_wal_and_an_explicit_busy_timeout(tmp_path):
    engine = create_db_engine(f"sqlite:///{tmp_path / 'pragmas.db'}")
    with engine.connect() as conn:
        assert conn.exec_driver_sql("PRAGMA journal_mode").scalar() == "wal"
        assert conn.exec_driver_sql("PRAGMA busy_timeout").scalar() == 5000
        assert conn.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
    engine.dispose()
