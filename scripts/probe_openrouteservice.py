"""Prueba autenticada de OpenRouteService para POC-03.

Mide con estaciones reales de CABA el contrato, los errores, los límites y la
latencia de una matriz como la que usará el recomendador, y guarda la evidencia
en JSON. El modo habitual usa como máximo runs + 3 solicitudes de la cuota diaria.
--verify-minute-limit usa hasta 42 matrices 1×1 y comprueba la recuperación.

Uso, desde la raíz del repositorio y con ORS_API_KEY en el entorno o en .env:

    python scripts/probe_openrouteservice.py --runs 5 --stations 20
"""

import argparse
import json
import math
import os
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nafta2go.adapters.openrouteservice import OpenRouteServiceClient  # noqa: E402
from nafta2go.adapters.routing import Point, QuotaExceeded, RoutingError, trip_matrix  # noqa: E402

STATIONS_FILE = ROOT / "scripts" / "data" / "stations_sample.json"
ORIGIN = Point(lat=-34.6037, lon=-58.3816)  # Obelisco
DESTINATION = Point(lat=-34.5627, lon=-58.4565)  # Av. Cabildo y Juramento
POINT_IN_RIVER = Point(lat=-34.55, lon=-58.20)  # Río de la Plata, sin red vial
PAUSE_BETWEEN_CALLS_S = 2  # mantiene la prueba lejos del límite de 40 por minuto


def load_env_file(path: Path) -> None:
    """Carga pares CLAVE=valor sin pisar variables ya definidas."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip().strip("\"'"))


def load_stations(limit: int, path: Path = STATIONS_FILE) -> list[Point]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [Point(lat=s["lat"], lon=s["lon"]) for s in data["stations"][:limit]]


def summarize_latencies(latencies_s: list[float]) -> dict:
    ordered = sorted(latencies_s)

    def nearest_rank(p: float) -> float:
        return round(ordered[math.ceil(p * len(ordered)) - 1], 3)

    return {
        "n": len(ordered),
        "p50_s": nearest_rank(0.50),
        "p95_s": nearest_rank(0.95),
        "max_s": round(ordered[-1], 3),
    }


def run_probe(
    api_key: str,
    stations: list[Point],
    runs: int,
    session: requests.Session,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.perf_counter,
) -> dict:
    if runs < 1:
        raise ValueError("runs: se necesita al menos una corrida para medir latencia")
    client = OpenRouteServiceClient(api_key=api_key, session=session)

    latencies = []
    result = None
    for run in range(runs):
        if run:
            sleep(PAUSE_BETWEEN_CALLS_S)
        start = clock()
        result = trip_matrix(client, ORIGIN, stations, DESTINATION)
        latencies.append(clock() - start)
    rate_limit = dict(client.last_rate_limit)

    sleep(PAUSE_BETWEEN_CALLS_S)
    round_trip = trip_matrix(client, ORIGIN, stations, None)

    sleep(PAUSE_BETWEEN_CALLS_S)
    invalid_key = _error_case(
        lambda: OpenRouteServiceClient("clave-invalida", session=session).matrix(
            [ORIGIN], [DESTINATION]
        )
    )
    sleep(PAUSE_BETWEEN_CALLS_S)
    point_in_river = _error_case(lambda: client.matrix([ORIGIN], [POINT_IN_RIVER]))

    rows = len(result.durations_s)
    cols = len(result.durations_s[0])
    return {
        "executed_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "provider": "openrouteservice",
        "endpoint": f"POST {client.matrix_url}",
        "matrix": {
            "stations": len(stations),
            "locations": len(stations) + 2,
            "elements": rows * cols,
            "null_pairs": sum(value is None for row in result.durations_s for value in row),
        },
        "latency": summarize_latencies(latencies),
        "latencies_s": [round(value, 3) for value in latencies],
        "reference_trip": {
            "duration_s": result.durations_s[0][-1],
            "distance_m": result.distances_m[0][-1],
        },
        "round_trip": {"ok": len(round_trip.durations_s) == len(stations) + 1},
        "rate_limit": rate_limit,
        "errors": {"invalid_key": invalid_key, "point_in_river": point_in_river},
        "requests_used": runs + 3,
    }


def _error_case(call: Callable[[], object]) -> dict:
    try:
        call()
    except RoutingError as exc:
        return {
            "error": type(exc).__name__,
            "status": exc.status,
            "provider_code": exc.provider_code,
        }
    return {"error": None, "status": 200, "provider_code": None}


def run_minute_limit_probe(
    api_key: str,
    session: requests.Session,
    *,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
    progress: Callable[[str], None] = lambda message: None,
) -> dict:
    """Verifica 40 éxitos, un 429 y recuperación; usa como máximo 42 solicitudes 1×1.

    Debe ejecutarse sin otras consultas con esa clave. Si la ventana no está
    limpia, faltan créditos o el servidor no limita, lo registra sin afirmar
    que el límite quedó verificado. No reintenta errores ni excede 41 llamadas
    en la primera ventana.
    """
    client = OpenRouteServiceClient(api_key, session=session)
    evidence = {
        "executed_at_utc": datetime.now(UTC).isoformat(),
        "provider": "openrouteservice",
        "endpoint": f"POST {client.matrix_url}",
        "matrix_elements_per_request": 1,
        "expected_requests_per_minute": 40,
        "attempts": [],
        "verified": False,
    }
    start = clock()
    rejected = False
    for attempt in range(1, 42):
        if clock() - start >= 55:
            evidence["stop_reason"] = "burst_exceeded_55_seconds"
            return evidence
        status = 200
        error = None
        try:
            client.matrix([ORIGIN], [DESTINATION])
        except RoutingError as exc:
            status = exc.status
            error = type(exc).__name__
            rejected = isinstance(exc, QuotaExceeded)
        evidence["attempts"].append(
            {
                "number": attempt,
                "elapsed_s": round(clock() - start, 3),
                "status": status,
                "error": error,
                "rate_limit": dict(client.last_rate_limit),
            }
        )
        if error is not None and not rejected:
            evidence["stop_reason"] = "provider_error_during_burst"
            return evidence
        remaining = client.last_rate_limit.get("x-ratelimit-remaining")
        if rejected:
            break
        if attempt == 1 and (remaining is None or int(remaining) < 45):
            evidence["stop_reason"] = "insufficient_daily_quota_or_missing_headers"
            return evidence
    if not rejected:
        evidence["stop_reason"] = "no_429_within_41_attempts"
        return evidence

    progress(f"Primer 429 en intento {len(evidence['attempts'])}; esperando recuperación")
    # Sesenta y cinco segundos después del rechazo, en pausas cortas para informar progreso.
    for seconds in (30, 30, 5):
        sleep(seconds)
        progress(f"Pausa de {seconds} s completada")
    recovery_status = 200
    recovery_error = None
    try:
        client.matrix([ORIGIN], [DESTINATION])
    except RoutingError as exc:
        recovery_status = exc.status
        recovery_error = type(exc).__name__
    evidence["recovery"] = {
        "wait_s": 65,
        "status": recovery_status,
        "error": recovery_error,
        "rate_limit": dict(client.last_rate_limit),
    }
    burst = evidence["attempts"]
    evidence["verified"] = (
        len(burst) == 41
        and all(item["status"] == 200 for item in burst[:40])
        and burst[-1]["status"] == 429
        and burst[-1]["elapsed_s"] < 60
        and recovery_status == 200
    )
    evidence["requests_attempted"] = len(burst) + 1
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--stations", type=int, default=20)
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "evidencia")
    parser.add_argument(
        "--verify-minute-limit",
        action="store_true",
        help="verifica el límite por minuto: hasta 42 solicitudes pequeñas y pausa de 65 s",
    )
    args = parser.parse_args()

    load_env_file(ROOT / ".env")
    api_key = os.environ.get("ORS_API_KEY", "").strip()
    if not api_key:
        print("Falta ORS_API_KEY: definila en el entorno o en .env (ver .env.example).")
        return 2
    if not 1 <= args.stations <= 20:
        print("--stations debe estar entre 1 y 20.")
        return 2
    if args.runs < 1:
        print("--runs debe ser al menos 1.")
        return 2

    try:
        if args.verify_minute_limit:
            evidence = run_minute_limit_probe(
                api_key, requests.Session(), progress=lambda message: print(message, flush=True)
            )
        else:
            evidence = run_probe(
                api_key, load_stations(args.stations), args.runs, requests.Session()
            )
    except RoutingError as exc:
        print(f"La prueba falló: {type(exc).__name__}: {exc}")
        return 1

    args.out.mkdir(parents=True, exist_ok=True)
    prefix = "poc-03-limite-minuto" if args.verify_minute_limit else "poc-03-ors"
    path = args.out / f"{prefix}-{datetime.now(UTC):%Y-%m-%d}.json"
    path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    print(f"Evidencia guardada en {path.relative_to(ROOT)}")
    return 0 if not args.verify_minute_limit or evidence["verified"] else 1


if __name__ == "__main__":
    sys.exit(main())
