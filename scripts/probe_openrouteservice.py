"""Prueba autenticada de OpenRouteService para POC-03.

Mide con estaciones reales de CABA el contrato, los errores, los límites y la
latencia de una matriz como la que usará el recomendador, y guarda la evidencia
en JSON. Usa como máximo runs + 3 solicitudes de la cuota diaria.

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
from nafta2go.adapters.routing import Point, RoutingError, trip_matrix  # noqa: E402

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
        "endpoint": "POST /v2/matrix/driving-car",
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--stations", type=int, default=20)
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "evidencia")
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
        evidence = run_probe(api_key, load_stations(args.stations), args.runs, requests.Session())
    except RoutingError as exc:
        print(f"La prueba falló: {type(exc).__name__}: {exc}")
        return 1

    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / f"poc-03-ors-{datetime.now(UTC):%Y-%m-%d}.json"
    path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    print(f"Evidencia guardada en {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
