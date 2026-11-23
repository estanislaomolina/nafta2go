"""La prueba de carga se verifica sin Locust ni red: perfiles, análisis, cupo y persistencia."""

import json
import os

import pytest
from fastapi.testclient import TestClient

from scripts.load_profile import (
    BODIES,
    PROFILES,
    Profile,
    request_body,
    saturation,
    summarize,
    target_users,
)
from scripts.load_server import ADMIN_TOKEN, TOKEN, build_app
from scripts.run_load_test import main, persistence_check, quota_check, resources_by_step

PROFILE = Profile(users=(1, 5), step_seconds=10, think_seconds=0.0)


def sample(users, elapsed, latency, status=200, code=None):
    return {
        "users": users,
        "elapsed_s": elapsed,
        "latency_s": latency,
        "status": status,
        "code": code,
    }


def test_steps_follow_the_profile_and_then_stop():
    assert [target_users(PROFILE, t) for t in (0, 9.9, 10, 19.9)] == [1, 1, 5, 5]
    assert target_users(PROFILE, 20) is None
    assert target_users(PROFILES["estres"], 0) == 1


def test_bodies_cycle_through_every_vehicle_variation():
    assert request_body(0) == request_body(len(BODIES))
    assert len({json.dumps(body, sort_keys=True) for body in BODIES}) == len(BODIES)
    assert all(body["destination"] for body in BODIES)


def test_summary_is_per_step_and_ignores_samples_of_other_levels():
    samples = [sample(1, t, 0.1) for t in range(10)]
    samples += [sample(5, 10 + t / 5, 0.2) for t in range(40)]
    samples += [sample(5, 15, 6.0, 503, "routes_timeout"), sample(1, 15, 9.0)]
    first, second = summarize(samples, PROFILE)
    assert first["requests"] == 10 and first["latency_s"]["p95"] == 0.1
    assert second["requests"] == 41 and second["statuses"] == {"200": 40, "503": 1}
    assert second["error_codes"] == {"routes_timeout": 1}
    assert second["latency_s"]["max"] == 6.0 and second["error_rate"] == round(1 / 41, 4)


def test_saturation_names_the_first_failing_step():
    steps = summarize([sample(1, t, 0.1) for t in range(10)], PROFILE)
    steps[1] |= {"requests_per_second": 5.0, "error_rate": 0.0}
    steps[1]["latency_s"] = {"p50": 1, "p95": 2, "p99": 3, "max": 3}
    assert saturation(steps) == {"users": None, "reasons": []}
    steps[1]["latency_s"]["p95"] = 5.5
    assert saturation(steps) == {"users": 5, "reasons": ["p95_supera_objetivo"]}
    steps[1] |= {"requests_per_second": 1.0, "error_rate": 0.5}
    assert saturation(steps)["reasons"] == [
        "p95_supera_objetivo",
        "errores_superan_umbral",
        "rendimiento_no_crece",
    ]


def test_resources_are_grouped_by_step():
    samples = [{"elapsed_s": 1, "cpu_percent": 10.0, "rss_mb": 100.0}]
    samples += [{"elapsed_s": 12, "cpu_percent": 90.0, "rss_mb": 150.0}]
    assert resources_by_step(samples, PROFILE) == [
        {"users": 1, "cpu_percent_mean": 10.0, "cpu_percent_max": 10.0, "rss_mb_max": 100.0},
        {"users": 5, "cpu_percent_mean": 90.0, "cpu_percent_max": 90.0, "rss_mb_max": 150.0},
    ]


@pytest.fixture
def tokens(monkeypatch):
    monkeypatch.setenv("NAFTA2GO_API_TOKEN", TOKEN)
    monkeypatch.setenv("NAFTA2GO_ADMIN_TOKEN", ADMIN_TOKEN)


def test_load_server_answers_with_recorded_routes_and_stores_traceable_results(tmp_path, tokens):
    database = tmp_path / "carga.db"
    headers = {"Authorization": f"Bearer {TOKEN}"}
    with TestClient(build_app(f"sqlite:///{database}")) as client:
        responses = [
            client.post("/api/v1/recommendations", json=request_body(i), headers=headers)
            for i in range(3)
        ]
    assert [r.status_code for r in responses] == [200, 200, 200]
    assert responses[0].json()["routes"]["replayed"] is True
    check = persistence_check(database, [sample(1, 0, 0.1) for _ in responses])
    assert check["all_successes_stored"] and check["stored_recommendations"] == 3
    assert check["stored_without_recorded_response"] == 0
    # Una respuesta perdida por el cliente al detenerse no es una recomendación perdida.
    partial = persistence_check(database, [sample(1, 0, 0.1)] * 2)
    assert partial["all_successes_stored"] and partial["stored_without_recorded_response"] == 1
    lost = persistence_check(database, [sample(1, 0, 0.1)] * 4)
    assert not lost["all_successes_stored"]
    assert not any(check["audit"]["fallas"].values())


def test_quota_mode_blocks_instead_of_consuming_more_matrices(tmp_path, tokens):
    headers = {"Authorization": f"Bearer {TOKEN}"}
    app = build_app(f"sqlite:///{tmp_path / 'cupo.db'}", quota_per_minute=2)
    with TestClient(app) as client:
        statuses = [
            client.post("/api/v1/recommendations", json=request_body(i), headers=headers)
            for i in range(4)
        ]
    assert [r.status_code for r in statuses] == [200, 200, 503, 503]
    assert statuses[-1].json()["detail"]["code"] == "routes_quota_exceeded"
    samples = [sample(10, 0, 0.1)] * 2 + [sample(10, 0, 0.1, 503, "routes_quota_exceeded")] * 2
    check = quota_check(
        samples, Profile(users=(10,), step_seconds=30, think_seconds=0, quota_per_minute=2)
    )
    assert check == {
        "quota_per_minute": 2,
        "duration_s": 30,
        "provider_calls": 2,
        "max_allowed_calls": 2,
        "blocked_by_quota": 2,
        "respected": True,
    }


def test_remote_target_requires_an_explicit_cap_and_token(monkeypatch, capsys):
    monkeypatch.delenv("NAFTA2GO_LOAD_TOKEN", raising=False)
    for argv in (["--target", "https://demo"], ["--target", "https://demo", "--max-requests", "5"]):
        with pytest.raises(SystemExit):
            main(argv)
    assert "NAFTA2GO_LOAD_TOKEN" not in os.environ
    capsys.readouterr()
