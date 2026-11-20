"""Concurrencia y errores ASGI del diagnóstico; no se inspecciona el cuerpo."""

import asyncio
from concurrent.futures import ThreadPoolExecutor

import pytest

from nafta2go.presentation.diagnostic_telemetry import (
    DiagnosticTelemetry,
    DiagnosticTelemetryMiddleware,
)


def test_diagnostic_counters_are_atomic_and_metadata_is_bounded():
    telemetry = DiagnosticTelemetry()
    with ThreadPoolExecutor(max_workers=8) as executor:
        list(
            executor.map(
                lambda _: telemetry.record(
                    200, "reference_only", 2, {"method": "bandera_reciente", "version": "a" * 64}
                ),
                range(80),
            )
        )
    telemetry.record(200, "reference_only", 2, {"method": ["secreto"], "version": "<img>"})
    result = telemetry.snapshot()
    assert result["completed"] == 81 and result["duration_ms_total"] == 162
    assert result["last_reference"]["version"] == "a" * 64
    result["last_reference"]["method"] = "modificado"
    assert telemetry.snapshot()["last_reference"]["method"] == "bandera_reciente"


@pytest.mark.parametrize("interrupted", [False, True])
def test_diagnostic_asgi_error_hides_details_and_never_reads_input(interrupted, caplog):
    telemetry, sent = DiagnosticTelemetry(), []
    caplog.set_level("INFO", logger="nafta2go.presentation.diagnostic_telemetry")

    async def app(scope, receive, send):
        if interrupted:
            await send({"type": "http.response.start", "status": 200})
        raise RuntimeError("url-token-privado")

    async def receive():
        pytest.fail("No debe leer el cuerpo")

    async def send(message):
        sent.append(message)

    call = DiagnosticTelemetryMiddleware(app, telemetry)(
        {"type": "http", "method": "GET", "path": "/api/v1/price-diagnostics/7"}, receive, send
    )
    if interrupted:
        with pytest.raises(RuntimeError, match="diagnóstico interrumpida"):
            asyncio.run(call)
    else:
        asyncio.run(call)
    assert telemetry.snapshot()["http_status"] == {"500": 1}
    assert "url-token-privado" not in caplog.text + str(sent)
