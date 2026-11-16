"""Límites ASGI que no se alcanzan con respuestas JSON normales."""

import asyncio

import pytest

from nafta2go.presentation.telemetry import QueryTelemetry, QueryTelemetryMiddleware


@pytest.mark.parametrize("interrupted", [False, True])
def test_unknown_results_are_bounded_and_interrupted_responses_hide_errors(
    interrupted, caplog, monkeypatch
):
    moments = iter((10, 10.125))
    monkeypatch.setattr("nafta2go.presentation.telemetry.monotonic", lambda: next(moments))
    caplog.set_level("INFO", logger="nafta2go.presentation.telemetry")
    telemetry = QueryTelemetry()
    sent = []

    async def send(message):
        sent.append(message)

    async def receive():
        pytest.fail("La telemetría no debe leer el cuerpo")

    async def app(scope, receive, send):
        scope["nafta2go.outcome"] = "secreto-no-admitido"
        await send({"type": "http.response.start", "status": 200})
        if interrupted:
            raise RuntimeError("secreto-original")
        await send({"type": "http.response.body", "body": b"ok"})

    call = QueryTelemetryMiddleware(app, telemetry)(
        {"type": "http", "method": "POST", "path": "/api/v1/recommendations"}, receive, send
    )
    if interrupted:
        with pytest.raises(RuntimeError, match="Respuesta de consulta interrumpida") as caught:
            asyncio.run(call)
        assert caught.value.__suppress_context__
    else:
        asyncio.run(call)
    assert len(sent[0]["headers"]) == 1
    snapshot = telemetry.snapshot()
    assert snapshot["duration_ms_total"] == 125
    assert snapshot["outcome"] == {"http_error" if interrupted else "other": 1}
    assert "secreto" not in caplog.text + str(snapshot)
