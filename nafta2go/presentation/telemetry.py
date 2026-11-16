"""Telemetría HTTP acotada por proceso; nunca inspecciona entradas del conductor."""

import json
import logging
from collections import Counter
from datetime import UTC, datetime
from threading import Lock
from time import monotonic
from uuid import uuid4

from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)
OUTCOMES = {"recommended", "no_feasible_stations", "insufficient_coverage"}


class QueryTelemetry:
    def __init__(self):
        self._lock = Lock()
        self._statuses = Counter()
        self._outcomes = Counter()
        self._duration_ms = 0.0

    def record(self, status, outcome, duration_ms):
        with self._lock:
            self._statuses[str(status)] += 1
            self._outcomes[outcome] += 1
            self._duration_ms += duration_ms

    def snapshot(self):
        with self._lock:
            return {
                "completed": sum(self._statuses.values()),
                "http_status": dict(self._statuses),
                "outcome": dict(self._outcomes),
                "duration_ms_total": round(self._duration_ms, 3),
            }


class QueryTelemetryMiddleware:
    def __init__(self, app, telemetry):
        self.app, self.telemetry = app, telemetry

    async def __call__(self, scope, receive, send):
        if (
            scope["type"] != "http"
            or scope["method"] != "POST"
            or scope["path"] != "/api/v1/recommendations"
        ):
            return await self.app(scope, receive, send)
        request_id, started = uuid4().hex, monotonic()
        timestamp = datetime.now(UTC).isoformat()
        status, failed, response_started = 500, True, False
        error_type = None

        async def send_response(message):
            nonlocal status, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status = message["status"]
                message = {
                    **message,
                    "headers": [
                        *message.get("headers", []),
                        (b"x-request-id", request_id.encode()),
                    ],
                }
            await send(message)

        try:
            await self.app(scope, receive, send_response)
            failed = False
        except Exception as exc:
            error_type = type(exc).__name__
            # No propagar mensajes arbitrarios al servidor ni devolver trazas al cliente.
            if response_started:
                raise RuntimeError("Respuesta de consulta interrumpida") from None
            await JSONResponse(status_code=500, content={"detail": {"code": "internal_error"}})(
                scope, receive, send_response
            )
        finally:
            status = 500 if failed else status
            outcome = scope.get("nafta2go.outcome")
            if status >= 400:
                outcome = "http_error"
            elif outcome not in OUTCOMES:
                outcome = "other"
            duration = max(0.0, (monotonic() - started) * 1000)
            self.telemetry.record(status, outcome, duration)
            logger.info(
                json.dumps(
                    {
                        "event": "query_completed",
                        "request_id": request_id,
                        "started_at_utc": timestamp,
                        "duration_ms": round(duration, 3),
                        "http_status": status,
                        "outcome": outcome,
                        **({"error_type": error_type} if error_type else {}),
                    }
                )
            )
