"""API local del recomendador: uvicorn nafta2go.presentation.http:app."""

import logging
import os
from collections.abc import Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from secrets import compare_digest
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError

from nafta2go.adapters.recorded_routes import CapturedRoutes
from nafta2go.adapters.routing import (
    InvalidCredentials,
    ProviderTimeout,
    QuotaExceeded,
    RoutingError,
)
from nafta2go.application.query import recommend_from_database
from nafta2go.application.scenario import ScenarioIntegrityError
from nafta2go.persistence.database import create_db_engine, database_is_ready
from nafta2go.presentation.models import ErrorOutput, RecommendationInput, RecommendationOutput
from nafta2go.presentation.navigation import present_recommendation
from nafta2go.presentation.web import install_web

logger = logging.getLogger(__name__)
bearer = HTTPBearer(auto_error=False)


def authorize(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> None:
    expected = os.environ.get("NAFTA2GO_API_TOKEN", "").strip()
    if not expected:
        raise HTTPException(503, detail={"code": "api_not_configured"})
    if credentials is None or not compare_digest(
        credentials.credentials.encode(), expected.encode()
    ):
        raise HTTPException(
            401, detail={"code": "unauthorized"}, headers={"WWW-Authenticate": "Bearer"}
        )


def dependency_error(_request, exc: Exception) -> JSONResponse:
    status, code = 503, "data_unavailable"
    if isinstance(exc, RoutingError):
        status, code = 502, "routes_unavailable"
        if isinstance(exc, ProviderTimeout):
            status, code = 504, "routes_timeout"
        elif isinstance(exc, QuotaExceeded):
            status, code = 503, "routes_quota_exceeded"
        elif isinstance(exc, InvalidCredentials):
            status, code = 503, "routes_not_configured"
    logger.warning(
        "Dependencia de la consulta no disponible", extra={"error_type": type(exc).__name__}
    )
    return JSONResponse(status_code=status, content={"detail": {"code": code}})


def validation_error(_request, exc: RequestValidationError) -> JSONResponse:
    # No repetir el input ni ctx: pueden contener ubicaciones u otros datos enviados.
    errors = []
    for error in exc.errors():
        message = {"missing": "Campo obligatorio", "extra_forbidden": "Campo no admitido"}.get(
            error["type"], "Tipo o valor fuera del rango admitido"
        )
        if error["type"] == "value_error":
            message = str(error.get("ctx", {}).get("error", message))
        errors.append({"field": ".".join(map(str, error["loc"])), "message": message})
    return JSONResponse(
        status_code=422, content={"detail": {"code": "invalid_request", "errors": errors}}
    )


def create_app(
    engine: Engine | None = None,
    provider_factory: Callable = CapturedRoutes,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    routing_provider: str = "openrouteservice",
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application):
        application.state.engine = engine if engine is not None else create_db_engine()
        try:
            yield
        finally:
            if engine is None:
                application.state.engine.dispose()

    application = FastAPI(title="Nafta2Go", version="0.1.0", lifespan=lifespan)
    install_web(application)
    application.add_exception_handler(RequestValidationError, validation_error)
    for error in (RoutingError, SQLAlchemyError, ScenarioIntegrityError, OSError):
        application.add_exception_handler(error, dependency_error)

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

    @application.post(
        "/api/v1/recommendations",
        dependencies=[Depends(authorize)],
        response_model=RecommendationOutput,
        responses={status: {"model": ErrorOutput} for status in (401, 422, 502, 503, 504)},
    )
    def recommendations(body: RecommendationInput) -> dict:
        try:
            result = recommend_from_database(
                application.state.engine,
                body.fuel_request(),
                body.origin.point(),
                body.destination.point() if body.destination else None,
                provider_factory(),
                fuel_type=body.fuel_type,
                schedule_id=body.schedule_id,
                reference_at=clock(),
                routing_provider=routing_provider,
                max_candidates=body.max_candidates,
            )
            return present_recommendation(result)
        except ValueError as exc:
            if isinstance(exc, ScenarioIntegrityError):
                raise
            raise HTTPException(
                422,
                detail={
                    "code": "invalid_request",
                    "message": "Verificá las coordenadas de CABA y los parámetros del vehículo.",
                },
            ) from exc

    return application


app = create_app()
