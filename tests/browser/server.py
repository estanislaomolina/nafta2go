"""Servidor de QA: precios históricos y distancias sintéticas, no usar en producción."""

import os
from datetime import UTC, datetime
from tempfile import TemporaryDirectory

import uvicorn

from nafta2go.adapters.routing import DistanceMatrix
from nafta2go.persistence.database import create_db_engine, upgrade_to_head
from nafta2go.presentation.http import create_app


class FixtureRoutes:
    def matrix(self, sources, destinations):
        return DistanceMatrix(
            [[60.0] * len(destinations) for _ in sources],
            [[1000.0] * len(destinations) for _ in sources],
            list(sources),
            list(destinations),
        )


if __name__ == "__main__":
    with TemporaryDirectory(prefix="nafta2go-web-qa-") as directory:
        url = f"sqlite:///{directory}/qa.db"
        upgrade_to_head(url)
        engine = create_db_engine(url)
        os.environ["NAFTA2GO_API_TOKEN"] = "codigo-web-de-prueba"
        os.environ["NAFTA2GO_MAX_PRICE_AGE_DAYS"] = "29"
        application = create_app(
            engine,
            FixtureRoutes,
            lambda: datetime(2026, 10, 26, 12, tzinfo=UTC),
            routing_provider="synthetic-web-test-fixture",
        )
        try:
            uvicorn.run(
                application, host="127.0.0.1", port=int(os.environ.get("WEB_TEST_PORT", "0"))
            )
        finally:
            engine.dispose()
