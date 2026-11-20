"""La búsqueda usa autenticación, POST y errores sin texto privado."""

from unittest.mock import Mock

from fastapi.testclient import TestClient

from nafta2go.domain.places import Place, PlaceBusy, PlaceUnavailable
from nafta2go.presentation.http import create_app


def test_authenticated_search_returns_only_places_and_does_not_save_recommendations(
    engine, monkeypatch, caplog
):
    monkeypatch.setenv("NAFTA2GO_API_TOKEN", "codigo-test")
    provider = Mock(return_value=[Place("Lugar elegido", -34.6, -58.4)])
    with TestClient(create_app(engine, place_provider=provider)) as client:
        assert client.post("/api/v1/places", json={"text": "Direccion privada"}).status_code == 401
        provider.assert_not_called()
        result = client.post(
            "/api/v1/places",
            json={"text": "Direccion privada"},
            headers={"Authorization": "Bearer codigo-test"},
        )
        assert result.status_code == 200 and result.headers["cache-control"] == "no-store"
        assert result.json()["items"] == [{"label": "Lugar elegido", "lat": -34.6, "lon": -58.4}]
        assert client.get("/api/v1/places").status_code == 405
    assert "Direccion privada" not in caplog.text
    from sqlalchemy import func, select

    from nafta2go.persistence.schema import recommendations

    with engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(recommendations)) == 0


def test_errors_and_input_validation_do_not_expose_search_text(engine, monkeypatch):
    monkeypatch.setenv("NAFTA2GO_API_TOKEN", "codigo-test")
    auth = {"Authorization": "Bearer codigo-test"}
    provider = Mock(side_effect=PlaceUnavailable("dato-privado"))
    with TestClient(create_app(engine, place_provider=provider)) as client:
        result = client.post("/api/v1/places", json={"text": "Direccion privada"}, headers=auth)
        assert result.status_code == 503 and "privad" not in result.text
        provider.side_effect = PlaceBusy()
        # Otra app evita que el cupo local oculte la excepción del proveedor.
    with TestClient(create_app(engine, place_provider=provider)) as client:
        assert (
            client.post("/api/v1/places", json={"text": "Otro lugar"}, headers=auth).status_code
            == 429
        )
        for body in [
            {"text": "a"},
            {"text": 123},
            {"text": "x" * 121},
            {"text": "Valida", "extra": "privado"},
        ]:
            assert client.post("/api/v1/places", json=body, headers=auth).status_code == 422
        assert (
            client.post(
                "/api/v1/places?text=privado", json={"text": "Valida"}, headers=auth
            ).status_code
            == 422
        )
