"""Tests de la prueba autenticada de OpenRouteService, sin red ni esperas reales."""

import json
import os

import pytest
import requests

from nafta2go.adapters.routing import Point
from scripts.probe_openrouteservice import (
    load_env_file,
    load_stations,
    run_minute_limit_probe,
    run_probe,
    summarize_latencies,
)

STATIONS = [Point(lat=-34.60 - i * 0.01, lon=-58.40) for i in range(3)]


class FakeResponse:
    def __init__(self, status_code, payload, headers=None):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}

    def json(self):
        return self._payload


class ScriptedSession:
    """Responde según la clave y los puntos de cada solicitud."""

    def __init__(self):
        self.calls = []

    def post(self, url, json=None, headers=None, timeout=None):
        self.calls.append({"json": json, "headers": headers})
        if headers["Authorization"] != "clave-valida":
            return FakeResponse(403, {"error": "Access to this API has been disallowed"})
        if [-58.20, -34.55] in json["locations"]:
            return FakeResponse(404, {"error": {"code": 6010, "message": "Point not found"}})
        rows, cols = len(json["sources"]), len(json["destinations"])
        return FakeResponse(
            200,
            {"durations": [[600.0] * cols] * rows, "distances": [[5000.0] * cols] * rows},
            {"x-ratelimit-limit": "500", "x-ratelimit-remaining": "490"},
        )


def fake_clock():
    ticks = iter(float(i) * 0.25 for i in range(1000))
    return lambda: next(ticks)


def test_summarize_latencies_uses_nearest_rank():
    summary = summarize_latencies([0.1, 0.2, 0.3, 0.4, 0.5])
    assert summary == {"n": 5, "p50_s": 0.3, "p95_s": 0.5, "max_s": 0.5}


def test_load_env_file_sets_only_missing_vars(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text(
        '# comentario\nORS_API_KEY="abc"\nOTRA=1\n\nYA_DEFINIDA=nuevo\n', encoding="utf-8"
    )
    monkeypatch.delenv("ORS_API_KEY", raising=False)
    monkeypatch.delenv("OTRA", raising=False)
    monkeypatch.setenv("YA_DEFINIDA", "original")
    load_env_file(env)
    assert os.environ["ORS_API_KEY"] == "abc"
    assert os.environ["OTRA"] == "1"
    assert os.environ["YA_DEFINIDA"] == "original"


def test_load_env_file_missing_file_is_ignored(tmp_path):
    load_env_file(tmp_path / "no-existe.env")


def test_load_stations_reads_sample():
    stations = load_stations(limit=20)
    assert len(stations) == 20
    assert all(-34.71 <= s.lat <= -34.52 and -58.54 <= s.lon <= -58.33 for s in stations)


def test_run_probe_records_matrix_runs_and_error_cases():
    session = ScriptedSession()
    evidence = run_probe(
        "clave-valida", STATIONS, runs=2, session=session, sleep=lambda s: None, clock=fake_clock()
    )
    assert len(session.calls) == 2 + 1 + 2
    assert evidence["matrix"]["locations"] == len(STATIONS) + 2
    assert evidence["matrix"]["elements"] == (len(STATIONS) + 1) ** 2
    assert evidence["matrix"]["null_pairs"] == 0
    assert evidence["latency"]["n"] == 2
    assert evidence["round_trip"]["ok"] is True
    assert evidence["rate_limit"] == {"x-ratelimit-limit": "500", "x-ratelimit-remaining": "490"}
    assert evidence["errors"]["invalid_key"] == {
        "error": "InvalidCredentials",
        "status": 403,
        "provider_code": None,
    }
    assert evidence["errors"]["point_in_river"]["provider_code"] == 6010
    assert evidence["reference_trip"] == {"duration_s": 600.0, "distance_m": 5000.0}


def test_run_probe_evidence_never_contains_key():
    evidence = run_probe(
        "clave-valida",
        STATIONS,
        runs=1,
        session=ScriptedSession(),
        sleep=lambda s: None,
        clock=fake_clock(),
    )
    assert "clave-valida" not in json.dumps(evidence)


def test_run_probe_requires_at_least_one_run():
    session = ScriptedSession()
    with pytest.raises(ValueError, match="runs"):
        run_probe("clave-valida", STATIONS, runs=0, session=session, sleep=lambda s: None)
    assert session.calls == []


def test_run_probe_records_the_queried_endpoint():
    evidence = run_probe(
        "clave-valida",
        STATIONS,
        runs=1,
        session=ScriptedSession(),
        sleep=lambda s: None,
        clock=fake_clock(),
    )
    assert evidence["endpoint"] == (
        "POST https://api.heigit.org/openrouteservice/v2/matrix/driving-car"
    )


class LimitSession:
    def __init__(self, successes=40, recover=True, remaining=450):
        self.calls = 0
        self.successes = successes
        self.recover = recover
        self.remaining = remaining

    def post(self, url, json=None, headers=None, timeout=None):
        self.calls += 1
        limited = self.calls > self.successes
        if self.calls == self.successes + 2 and self.recover:
            limited = False
        quota = {"x-ratelimit-limit": "500", "x-ratelimit-remaining": str(self.remaining)}
        if limited:
            return FakeResponse(429, {"error": "rate limit"}, quota)
        return FakeResponse(200, {"distances": [[1000]], "durations": [[60]]}, quota)


def test_minute_limit_requires_40_successes_429_and_recovery():
    session = LimitSession()
    waits = []
    evidence = run_minute_limit_probe(
        "clave-de-prueba", session, sleep=waits.append, clock=fake_clock()
    )
    assert evidence["verified"]
    assert session.calls == evidence["requests_attempted"] == 42
    assert waits == [30, 30, 5]
    assert all(row["status"] == 200 for row in evidence["attempts"][:40])
    assert evidence["attempts"][-1]["status"] == 429
    assert evidence["recovery"]["status"] == 200
    assert "clave-de-prueba" not in json.dumps(evidence)


def test_early_rate_limit_is_not_claimed_as_40_per_minute():
    evidence = run_minute_limit_probe(
        "clave", LimitSession(successes=5), sleep=lambda s: None, clock=fake_clock()
    )
    assert not evidence["verified"]
    assert len(evidence["attempts"]) == 6


def test_no_recovery_is_not_claimed_as_verified():
    evidence = run_minute_limit_probe(
        "clave", LimitSession(recover=False), sleep=lambda s: None, clock=fake_clock()
    )
    assert not evidence["verified"]
    assert evidence["recovery"]["status"] == 429


def test_no_rejection_stops_at_41_without_waiting():
    session = LimitSession(successes=100)
    waits = []
    evidence = run_minute_limit_probe("clave", session, sleep=waits.append, clock=fake_clock())
    assert not evidence["verified"]
    assert session.calls == 41
    assert waits == []
    assert evidence["stop_reason"] == "no_429_within_41_attempts"


def test_daily_quota_is_checked_before_burst():
    session = LimitSession(remaining=10)
    evidence = run_minute_limit_probe("clave", session, clock=fake_clock())
    assert session.calls == 1
    assert not evidence["verified"]
    assert evidence["stop_reason"] == "insufficient_daily_quota_or_missing_headers"


def test_slow_requests_cannot_span_multiple_windows():
    session = LimitSession()
    ticks = iter(range(0, 1000, 30))
    evidence = run_minute_limit_probe("clave", session, clock=lambda: next(ticks))
    assert not evidence["verified"]
    assert session.calls == 1
    assert evidence["stop_reason"] == "burst_exceeded_55_seconds"


def test_network_error_during_recovery_preserves_the_burst_evidence():
    class Disconnecting(LimitSession):
        def post(self, *args, **kwargs):
            if self.calls == 41:
                raise requests.ConnectionError("conexión interrumpida")
            return super().post(*args, **kwargs)

    evidence = run_minute_limit_probe(
        "clave", Disconnecting(), sleep=lambda s: None, clock=fake_clock()
    )
    assert not evidence["verified"]
    assert len(evidence["attempts"]) == 41
    assert evidence["attempts"][-1]["status"] == 429
    assert evidence["recovery"]["error"] == "ProviderUnavailable"


def test_provider_error_during_burst_is_recorded_without_retry():
    class Unavailable:
        def post(self, *args, **kwargs):
            raise requests.ConnectionError("conexión interrumpida")

    evidence = run_minute_limit_probe("clave", Unavailable(), clock=fake_clock())
    assert not evidence["verified"]
    assert len(evidence["attempts"]) == 1
    assert evidence["stop_reason"] == "provider_error_during_burst"
