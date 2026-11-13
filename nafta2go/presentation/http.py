"""Servidor HTTP local y controles de disponibilidad de Nafta2Go."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import Engine

from nafta2go.persistence.database import create_db_engine, database_is_ready


def create_app(engine: Engine | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application):
        application.state.engine = engine if engine is not None else create_db_engine()
        try:
            yield
        finally:
            if engine is None:
                application.state.engine.dispose()

    application = FastAPI(title="Nafta2Go", version="0.1.0", lifespan=lifespan)

    @application.get("/health")
    def health():
        return {"status": "ok"}

    @application.get("/ready")
    def ready():
        configured = bool(os.environ.get("NAFTA2GO_API_TOKEN", "").strip())
        available = configured and database_is_ready(application.state.engine)
        return JSONResponse(
            status_code=200 if available else 503,
            content={"status": "ready" if available else "unavailable"},
        )

    return application


app = create_app()
