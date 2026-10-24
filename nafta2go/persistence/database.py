"""Conexión a la base y migraciones.

La URL sale de DATABASE_URL; por defecto es un SQLite local en data/, relativo
a la raíz desde donde se ejecuta.
"""

import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url

DEFAULT_URL = "sqlite:///data/nafta2go.db"
ROOT = Path(__file__).resolve().parents[2]


def database_url() -> str:
    return os.environ.get("DATABASE_URL", "").strip() or DEFAULT_URL


def create_db_engine(url: str | None = None) -> Engine:
    url = url or database_url()
    engine = create_engine(url)
    if _is_sqlite(url):
        _ensure_sqlite_directory(url)
        event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    return engine


def alembic_config(url: str | None = None) -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    # configparser interpreta "%" como interpolación.
    config.set_main_option("sqlalchemy.url", (url or database_url()).replace("%", "%%"))
    return config


def upgrade_to_head(url: str | None = None) -> None:
    command.upgrade(alembic_config(url), "head")


def _is_sqlite(url: str) -> bool:
    return make_url(url).get_backend_name() == "sqlite"


def _ensure_sqlite_directory(url: str) -> None:
    path = make_url(url).database
    if path and path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)


def _enable_sqlite_foreign_keys(dbapi_connection, _record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
