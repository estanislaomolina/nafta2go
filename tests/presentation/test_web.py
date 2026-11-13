"""Entrega de la pantalla y assets sin filtrar configuración ni consultar rutas."""

from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from nafta2go.presentation.http import create_app


@pytest.mark.parametrize("page", ["/", "/operacion"])
def test_web_is_public_but_has_no_embedded_token(engine, monkeypatch, page):
    monkeypatch.setenv("NAFTA2GO_API_TOKEN", "privado-no-incrustar")
    provider = Mock()
    with TestClient(create_app(engine, provider_factory=provider)) as client:
        response = client.get(page)
    assert response.status_code == 200
    assert 'lang="es-AR"' in response.text and "Nafta2Go" in response.text
    assert "privado-no-incrustar" not in response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert "unsafe-inline" not in response.headers["content-security-policy"]
    provider.assert_not_called()


@pytest.mark.parametrize(
    "asset,mime",
    [("app.js", "javascript"), ("operation.js", "javascript"), ("styles.css", "text/css")],
)
def test_assets_are_served_and_parent_directory_is_not(engine, asset, mime):
    with TestClient(create_app(engine)) as client:
        response = client.get(f"/assets/{asset}")
        assert response.status_code == 200 and mime in response.headers["content-type"]
        assert client.get("/assets/%2e%2e/index.html").status_code == 404
