"""La publicación estática no depende de rutas absolutas ni incluye secretos."""

import pytest
from fastapi.testclient import TestClient

from scripts.build_pages import build


def test_build_publishes_both_pages_with_fixed_https_api_and_relative_assets(tmp_path):
    build(tmp_path, "https://192.0.2.1.sslip.io")
    for file, prefix in (("index.html", "./"), ("operacion/index.html", "../")):
        page = (tmp_path / file).read_text()
        assert 'content="https://192.0.2.1.sslip.io"' in page
        assert prefix + "assets/api-config.js" in page
        assert '"/assets/' not in page
        assert "Content-Security-Policy" in page
        assert "no-referrer" in page
    assert (tmp_path / "assets/app.js").is_file()
    assert (tmp_path / ".nojekyll").is_file()
    assert not (tmp_path / ".env").exists()
    assert not (tmp_path / "data").exists()


@pytest.mark.parametrize(
    "origin",
    [
        "http://api.test",
        "https://api.test/path",
        "https://user:pass@api.test",
        "https://api.test?token=x",
    ],
)
def test_build_rejects_insecure_or_credential_bearing_api(tmp_path, origin):
    with pytest.raises(ValueError):
        build(tmp_path, origin)


def test_cors_allows_only_pages_origin_and_preserves_authentication(engine, monkeypatch):
    from nafta2go.presentation.http import create_app

    origin = "https://estanislaomolina.github.io"
    monkeypatch.setenv("NAFTA2GO_WEB_ORIGIN", origin)
    monkeypatch.setenv("NAFTA2GO_API_TOKEN", "codigo-solo-de-prueba")
    with TestClient(create_app(engine)) as client:
        response = client.options(
            "/api/v1/recommendations",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == origin
        assert "access-control-allow-credentials" not in response.headers
        rejected = client.post("/api/v1/recommendations", headers={"Origin": origin}, json={})
        assert rejected.status_code == 401
        assert rejected.headers["access-control-allow-origin"] == origin
        foreign = client.options(
            "/api/v1/recommendations",
            headers={
                "Origin": "https://evil.test",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert foreign.status_code == 400
        assert "access-control-allow-origin" not in foreign.headers


def test_cors_misconfiguration_fails_closed(engine, monkeypatch):
    from nafta2go.presentation.http import create_app

    monkeypatch.setenv("NAFTA2GO_WEB_ORIGIN", "https://pages.test/path")
    with pytest.raises(ValueError):
        create_app(engine)
