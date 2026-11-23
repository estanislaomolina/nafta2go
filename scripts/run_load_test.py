"""Ejecuta una prueba de carga con Locust y escribe un reporte reproducible (#158).

Por defecto levanta `scripts/load_server.py` (base temporal, escenario histórico y
rutas grabadas, sin red ni cuota de ORS), mide CPU y memoria del proceso servidor y,
al terminar, verifica que cada respuesta 200 dejó su recomendación guardada y audita
lo persistido. Con `--target` apunta a un despliegue existente: ahí las rutas son
reales, por eso exige `--max-requests` como tope explícito de solicitudes. El perfil
`historico` exige `--source-database` y `--reference-at` y falla si alguna respuesta
no trae los veinte diagnósticos disponibles.

Requiere `pip install -r requirements-load.txt`. Uso, desde la raíz del repositorio:

    python scripts/run_load_test.py --profile estres --output estres.json
"""

import argparse
import json
import math
import os
import platform
import socket
import subprocess
import sys
import tempfile
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nafta2go.application.price_dataset import code_provenance  # noqa: E402
from nafta2go.application.recommendation_audit import audit_recommendations  # noqa: E402
from nafta2go.persistence import repository as repo  # noqa: E402
from nafta2go.persistence.database import create_db_engine  # noqa: E402
from scripts.load_profile import (  # noqa: E402
    PROFILES,
    REQUIRED_DIAGNOSTICS,
    saturation,
    summarize,
)
from scripts.load_server import TOKEN  # noqa: E402

TICKS = os.sysconf("SC_CLK_TCK") if hasattr(os, "sysconf") else 100


def cpu_model() -> str | None:
    try:
        lines = Path("/proc/cpuinfo").read_text().splitlines()
    except OSError:
        return platform.processor() or None
    return next(
        (line.split(":", 1)[1].strip() for line in lines if line.startswith("model name")), None
    )


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def wait_healthy(url: str, timeout: float = 60) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if requests.get(url + "/health", timeout=2).status_code == 200:
                return
        except requests.RequestException:
            pass
        time.sleep(0.5)
    raise RuntimeError("El servidor de carga no respondió /health")


class ResourceSampler(threading.Thread):
    """CPU y memoria residente de un proceso Linux, leídas de /proc una vez por segundo."""

    def __init__(self, pid: int):
        super().__init__(daemon=True)
        self.pid, self.samples, self.started = pid, [], time.monotonic()
        self._halt = threading.Event()

    def _read(self):
        stat = Path(f"/proc/{self.pid}/stat").read_text().rsplit(")", 1)[1].split()
        cpu = (int(stat[11]) + int(stat[12])) / TICKS
        rss_kb = next(
            int(line.split()[1])
            for line in Path(f"/proc/{self.pid}/status").read_text().splitlines()
            if line.startswith("VmRSS:")
        )
        return cpu, rss_kb / 1024

    def run(self):
        try:
            previous_cpu, previous_at = self._read()[0], time.monotonic()
            while not self._halt.wait(1):
                cpu, rss_mb = self._read()
                now = time.monotonic()
                self.samples.append(
                    {
                        "elapsed_s": round(now - self.started, 3),
                        "cpu_percent": round(100 * (cpu - previous_cpu) / (now - previous_at), 1),
                        "rss_mb": round(rss_mb, 1),
                    }
                )
                previous_cpu, previous_at = cpu, now
        except (OSError, StopIteration, ValueError):
            return

    def stop(self):
        self._halt.set()
        self.join(timeout=5)


def resources_by_step(samples: list[dict], profile) -> list[dict]:
    result = []
    for index, users in enumerate(profile.users):
        start, end = index * profile.step_seconds, (index + 1) * profile.step_seconds
        rows = [s for s in samples if start <= s["elapsed_s"] < end]
        result.append(
            {
                "users": users,
                "cpu_percent_mean": round(sum(r["cpu_percent"] for r in rows) / len(rows), 1)
                if rows
                else None,
                "cpu_percent_max": max((r["cpu_percent"] for r in rows), default=None),
                "rss_mb_max": max((r["rss_mb"] for r in rows), default=None),
            }
        )
    return result


def persistence_check(database: Path, samples: list[dict]) -> dict:
    """Ningún 200 puede quedar sin su recomendación; lo guardado se audita como en VALIDACION."""
    engine = create_db_engine(f"sqlite:///{database}")
    try:
        with engine.connect() as conn:
            stored = list(repo.recommendations_with_run_status(conn))
    finally:
        engine.dispose()
    successes = sum(1 for sample in samples if sample["status"] == 200)
    return {
        "successful_responses": successes,
        "stored_recommendations": len(stored),
        "all_successes_stored": len(stored) >= successes,
        # Consultas que el servidor completó mientras Locust se detenía, sin respuesta registrada.
        "stored_without_recorded_response": max(0, len(stored) - successes),
        "audit": audit_recommendations(stored),
    }


def quota_check(samples: list[dict], profile) -> dict:
    """Sin caché, cada éxito consumió una matriz: no puede superar el cupo por minuto."""
    duration = profile.step_seconds * len(profile.users)
    allowed = profile.quota_per_minute * math.ceil(duration / 60)
    successes = sum(1 for sample in samples if sample["status"] == 200)
    blocked = sum(1 for sample in samples if sample.get("code") == "routes_quota_exceeded")
    return {
        "quota_per_minute": profile.quota_per_minute,
        "duration_s": duration,
        "provider_calls": successes,
        "max_allowed_calls": allowed,
        "blocked_by_quota": blocked,
        "respected": successes <= allowed and blocked > 0,
    }


def diagnostics_check(samples: list[dict]) -> dict:
    """El perfil de histórico real sólo vale si cada 200 trajo los veinte diagnósticos."""
    incomplete = sum(1 for sample in samples if sample.get("code") == "diagnostico_incompleto")
    complete = sum(1 for sample in samples if sample["status"] == 200) - incomplete
    return {
        "required_per_response": REQUIRED_DIAGNOSTICS,
        "complete_responses": complete,
        "incomplete_responses": incomplete,
        "passed": complete > 0 and incomplete == 0,
    }


def run_locust(profile_name: str, host: str, token: str, samples: Path, max_requests: int | None):
    env = {
        **os.environ,
        "NAFTA2GO_LOAD_PROFILE": profile_name,
        "NAFTA2GO_LOAD_TOKEN": token,
        "NAFTA2GO_LOAD_SAMPLES": str(samples),
        "NAFTA2GO_LOAD_MAX_REQUESTS": str(max_requests or 0),
    }
    command = [sys.executable, "-m", "locust", "-f", str(ROOT / "scripts/locustfile.py")]
    command += ["--headless", "--host", host, "--only-summary", "--loglevel", "WARNING"]
    # Locust termina con código 1 si hubo fallas; eso se informa en el reporte, no aborta.
    subprocess.run(command, env=env, check=False, cwd=ROOT)


def read_samples(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def measure(
    profile_name: str, target: str | None, token: str | None, max_requests=None, history=None
) -> dict:
    """`history` son los argumentos del servidor para el perfil de histórico real."""
    profile = PROFILES[profile_name]
    with tempfile.TemporaryDirectory() as directory:
        samples_path = Path(directory) / "samples.jsonl"
        server, sampler, database = None, None, Path(directory) / "carga.db"
        try:
            if target is None:
                port = free_port()
                command = [sys.executable, str(ROOT / "scripts/load_server.py")]
                command += ["--port", str(port), "--database", str(database)]
                if profile.quota_per_minute is not None:
                    command += ["--quota-per-minute", str(profile.quota_per_minute)]
                if profile.real_history:
                    command += history
                server = subprocess.Popen(command, cwd=ROOT)
                host = f"http://127.0.0.1:{port}"
                wait_healthy(host)
                sampler = ResourceSampler(server.pid)
                sampler.start()
            else:
                host = target.rstrip("/")
            run_locust(profile_name, host, token or TOKEN, samples_path, max_requests)
        finally:
            if sampler is not None:
                sampler.stop()
            if server is not None:
                server.terminate()
                try:
                    server.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    # Consultas encoladas al saturar retrasan el apagado ordenado de uvicorn.
                    server.kill()
                    server.wait(timeout=30)
        samples = read_samples(samples_path)
        steps = summarize(samples, profile)
        report = {
            "format_version": 1,
            "measured_at_utc": datetime.now(UTC).isoformat(),
            "profile": profile_name,
            "configuration": {
                "users": list(profile.users),
                "step_seconds": profile.step_seconds,
                "think_seconds": profile.think_seconds,
                "quota_per_minute": profile.quota_per_minute,
            },
            "scope": (
                "remote_target"
                if target is not None
                else "local_real_history_synthetic_routes"
                if profile.real_history
                else "local_recorded_routes"
            ),
            "excludes": (
                ["CPU y memoria del servidor remoto"]
                if target is not None
                else ["rutas reales (distancias sintéticas)", "red entre cliente y servidor"]
                if profile.real_history
                else ["llamada real a OpenRouteService", "red entre cliente y servidor"]
            ),
            "requests": len(samples),
            "steps": steps,
            "saturation": saturation(steps),
            "server_resources": resources_by_step(sampler.samples, profile) if sampler else None,
            "persistence": persistence_check(database, samples) if target is None else None,
            "quota": quota_check(samples, profile) if profile.quota_per_minute else None,
            "diagnostics": diagnostics_check(samples) if profile.real_history else None,
            "code": code_provenance(),
            "environment": {
                "python": platform.python_version(),
                "platform": f"{platform.system()} {platform.machine()}",
                "cpu_count": os.cpu_count(),
                "cpu_model": cpu_model(),
                "server": "uvicorn, un proceso" if target is None else target,
            },
        }
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=sorted(PROFILES), default="estres")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--target", help="URL de un despliegue existente; usa rutas reales")
    parser.add_argument("--max-requests", type=int, help="Tope obligatorio con --target")
    parser.add_argument("--source-database", type=Path, help="Base con histórico real")
    parser.add_argument("--reference-at", help="Instante ISO con zona horaria del histórico")
    parser.add_argument("--model-run", help="Corrida auditada a servir en lugar del campeón")
    args = parser.parse_args(argv)
    if args.target and not (args.max_requests and args.max_requests > 0):
        parser.error("--target requiere --max-requests positivo: consume cuota real de ORS")
    history = None
    if PROFILES[args.profile].real_history:
        if args.target or not (args.source_database and args.reference_at):
            parser.error("historico es local y requiere --source-database y --reference-at")
        history = ["--source-database", str(args.source_database.resolve())]
        history += ["--reference-at", args.reference_at]
        history += ["--model-run", args.model_run] if args.model_run else []
    token = os.environ.get("NAFTA2GO_LOAD_TOKEN") if args.target else None
    if args.target and not token:
        parser.error("--target requiere el código de conductor en NAFTA2GO_LOAD_TOKEN")
    report = measure(args.profile, args.target, token, args.max_requests, history)
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 1 if report["diagnostics"] and not report["diagnostics"]["passed"] else 0


if __name__ == "__main__":
    sys.exit(main())
