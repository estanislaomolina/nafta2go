"""Métricas del diagnóstico por proceso, sin estación, URL ni contenido del cliente."""

import json
import logging
from collections import Counter
from datetime import UTC, datetime
from threading import Lock
from time import monotonic
from uuid import uuid4

from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)
METHODS = {"mediana_previa", "ultimo_precio", "bandera_reciente"}


class DiagnosticTelemetry:
    def __init__(self):
        self.lock = Lock()
        self.statuses, self.outcomes = Counter(), Counter()
        self.duration = 0.0
        self.state, self.last_at, self.last_reference = "not_observed", None, None

    def record(self, status, outcome, duration, reference):
        now = datetime.now(UTC).isoformat()
        with self.lock:
            self.statuses[str(status)] += 1
            self.outcomes[outcome] += 1
            self.duration += duration
            self.last_at = now
            if status in {200, 404} or status >= 500:
                self.state = "degraded" if status >= 500 else "observed"
            if outcome == "reference_only" and reference:
                method, version = reference.get("method"), reference.get("version")
                if (
                    isinstance(method, str)
                    and method in METHODS
                    and isinstance(version, str)
                    and len(version) == 64
                    and all(c in "0123456789abcdef" for c in version)
                ):
                    self.last_reference = {
                        "method": method,
                        "version": version,
                        "observed_at_utc": now,
                    }

    def snapshot(self):
        with self.lock:
            return {
                "scope": "process",
                "status": self.state,
                "completed": sum(self.statuses.values()),
                "http_status": dict(self.statuses),
                "outcome": dict(self.outcomes),
                "duration_ms_total": round(self.duration, 3),
                "last_completed_at_utc": self.last_at,
                "last_reference": dict(self.last_reference) if self.last_reference else None,
            }


class DiagnosticTelemetryMiddleware:
    def __init__(self, app, telemetry):
        self.app, self.telemetry = app, telemetry

    async def __call__(self, scope, receive, send):
        prefix = "/api/v1/price-diagnostics/"
        tail = scope.get("path", "").removeprefix(prefix)
        if (
            scope["type"] != "http"
            or scope["method"] != "GET"
            or not scope["path"].startswith(prefix)
            or not tail
            or "/" in tail
        ):
            return await self.app(scope, receive, send)
        request_id, start = uuid4().hex, monotonic()
        status, response_started, failed = 500, False, True

        async def send_response(message):
            nonlocal status, response_started
            if message["type"] == "http.response.start":
                status, response_started = message["status"], True
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
        except Exception:
            if response_started:
                raise RuntimeError("Respuesta de diagnóstico interrumpida") from None
            await JSONResponse(status_code=500, content={"detail": {"code": "internal_error"}})(
                scope, receive, send_response
            )
        finally:
            status = 500 if failed else status
            result = scope.get("nafta2go.diagnostic") or {}
            outcome = {
                401: "unauthorized",
                404: "not_found",
                422: "invalid_request",
                503: "dependency_unavailable",
            }.get(status, "internal_error" if status >= 500 else "other")
            if status == 200 and result.get("status") in {"reference_only", "unavailable"}:
                outcome = result["status"]
            duration = max(0.0, (monotonic() - start) * 1000)
            self.telemetry.record(status, outcome, duration, result)
            logger.info(
                json.dumps(
                    {
                        "event": "price_diagnostic_completed",
                        "request_id": request_id,
                        "http_status": status,
                        "outcome": outcome,
                        "completed_at_utc": datetime.now(UTC).isoformat(),
                        "duration_ms": round(duration, 3),
                    }
                )
            )
