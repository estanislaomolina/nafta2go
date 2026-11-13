"""Disponibilidad HTTP sin red, migraciones implícitas ni datos sensibles."""

from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect
from sqlalchemy.exc import OperationalError

from nafta2go.persistence.database import create_db_engine, upgrade_to_head
from nafta2go.presentation.http import create_app


@pytest.mark.parametrize(
    "migrated,token,expected", [(True, "prueba", 200), (True, "", 503), (False, "prueba", 503)]
)
def test_readiness(tmp_path, monkeypatch, migrated, token, expected):
    url = f"sqlite:///{tmp_path / 'api.db'}"
    if migrated:
        upgrade_to_head(url)
    engine = create_db_engine(url)
    before = inspect(engine).get_table_names()
    monkeypatch.setenv("NAFTA2GO_API_TOKEN", token)
    try:
        with TestClient(create_app(engine)) as client:
            assert client.get("/health").json() == {"status": "ok"}
            response = client.get("/ready")
            assert response.status_code == expected
            assert response.json() == {"status": "ready" if expected == 200 else "unavailable"}
        assert inspect(engine).get_table_names() == before
    finally:
        engine.dispose()


def test_connection_error_is_private(monkeypatch):
    engine = Mock()
    engine.connect.side_effect = OperationalError("privado", {}, Exception("secreto"))
    monkeypatch.setenv("NAFTA2GO_API_TOKEN", "token-privado")
    with TestClient(create_app(engine)) as client:
        response = client.get("/ready")
        assert response.status_code == 503
        assert response.json() == {"status": "unavailable"}
    engine.dispose.assert_not_called()


def test_application_disposes_owned_engine(monkeypatch):
    engine = Mock()
    monkeypatch.setattr("nafta2go.presentation.http.create_db_engine", lambda: engine)
    with TestClient(create_app()) as client:
        assert client.get("/health").status_code == 200
        assert "/health" in client.get("/openapi.json").json()["paths"]
        engine.dispose.assert_not_called()
    engine.dispose.assert_called_once_with()
