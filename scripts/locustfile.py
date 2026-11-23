"""Usuarios y escalones de Locust para #158; lo ejecuta scripts/run_load_test.py.

Variables: NAFTA2GO_LOAD_PROFILE (perfil de load_profile), NAFTA2GO_LOAD_TOKEN y
NAFTA2GO_LOAD_SAMPLES (archivo JSONL donde se registra cada solicitud) y
NAFTA2GO_LOAD_MAX_REQUESTS (tope de solicitudes; 0 sin tope). En el perfil de
histórico real, la primera respuesta sin los veinte diagnósticos detiene la prueba.
"""

import itertools
import json
import os
import time

import gevent
from load_profile import PROFILES, diagnostics_complete, request_body, target_users
from locust import HttpUser, LoadTestShape, constant, events, task
from locust.exception import StopUser

PROFILE = PROFILES[os.environ.get("NAFTA2GO_LOAD_PROFILE", "estres")]
COUNTER = itertools.count()
# Tope explícito con rutas reales (--target); 0 significa sin tope.
MAX_REQUESTS = int(os.environ.get("NAFTA2GO_LOAD_MAX_REQUESTS", "0"))
STATE = {"started": None, "environment": None, "samples": None}


@events.test_start.add_listener
def start(environment, **_):
    STATE["started"], STATE["environment"] = time.monotonic(), environment
    STATE["samples"] = open(os.environ["NAFTA2GO_LOAD_SAMPLES"], "a", encoding="utf-8")  # noqa: SIM115


@events.test_stop.add_listener
def stop(**_):
    if STATE["samples"] is not None:
        STATE["samples"].close()


@events.request.add_listener
def record(response_time, response, exception, **_):
    # Locust informa status 0 cuando no hubo respuesta (conexión rechazada o timeout).
    status = getattr(response, "status_code", 0) or 0
    code = None
    if status != 200:
        try:
            code = response.json()["detail"]["code"]
        except (AttributeError, KeyError, TypeError, ValueError):
            code = type(exception).__name__ if exception else None
    elif PROFILE.real_history and not diagnostics_complete(response.json()):
        code = "diagnostico_incompleto"
        # Sin diagnóstico activo la prueba no mide #158: se aborta en vez de promediarla.
        gevent.spawn(STATE["environment"].runner.quit)
    sample = {
        "elapsed_s": round(time.monotonic() - STATE["started"], 3),
        "users": STATE["environment"].runner.user_count,
        "latency_s": response_time / 1000,
        "status": status,
        "code": code,
    }
    STATE["samples"].write(json.dumps(sample) + "\n")


class Driver(HttpUser):
    wait_time = constant(PROFILE.think_seconds)

    @task
    def recommend(self):
        index = next(COUNTER)
        if MAX_REQUESTS and index >= MAX_REQUESTS:
            raise StopUser()
        self.client.post(
            "/api/v1/recommendations",
            json=request_body(index, PROFILE.real_history),
            headers={"Authorization": "Bearer " + os.environ["NAFTA2GO_LOAD_TOKEN"]},
            name="POST /api/v1/recommendations",
        )


class Steps(LoadTestShape):
    def tick(self):
        users = target_users(PROFILE, self.get_run_time())
        # Se alcanza cada escalón en un segundo para no mezclar niveles de carga.
        return None if users is None else (users, max(users, 1))
