"""Mide la latencia de la API de recomendaciones sin red, con rutas reales guardadas (RNF01).

Levanta la aplicación HTTP en el mismo proceso sobre una base SQLite nueva, que usa el
escenario histórico del 24/10/2026, y reemplaza ORS por la matriz capturada en POC-05.
Cada consulta pasa por autenticación, validación, lectura de precios, motor, guardado y
telemetría; no incluye la llamada real al proveedor ni la red entre cliente y servidor.
Al final audita las recomendaciones guardadas con `recommendation_audit`.

Uso, desde la raíz del repositorio:

    python scripts/measure_query_latency.py --requests 120 --output resultado.json
"""

import argparse
import json
import math
import os
import platform
import statistics
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from nafta2go.adapters.recorded_routes import RecordedRoutes  # noqa: E402
from nafta2go.application.price_dataset import code_provenance  # noqa: E402
from nafta2go.application.recommendation_audit import audit_recommendations  # noqa: E402
from nafta2go.persistence import repository as repo  # noqa: E402
from nafta2go.persistence.database import create_db_engine, upgrade_to_head  # noqa: E402
from nafta2go.presentation.http import create_app  # noqa: E402

MATRIX = ROOT / "docs/evidencia/poc-05-flujo-2026-10-26/matrix.json"
ORIGIN = {"lat": -34.6037, "lon": -58.3816}
DESTINATION = {"lat": -34.5627, "lon": -58.4565}
TOKEN = "token-de-medicion-local"


def bodies(count: int) -> list[dict]:
    """Consultas UC01 válidas que varían vehículo y presupuesto de forma determinística."""
    return [
        {
            "origin": ORIGIN,
            "destination": DESTINATION,
            "fuel_type": "super",
            "consumption_l_per_100km": str(7 + index % 6),
            "tank_capacity_l": str(40 + 5 * (index % 4)),
            "remaining_l": str(4 + index % 9),
            "budget_ars": str(6000 + 1500 * (index % 7)),
            "reserve_l": "2",
        }
        for index in range(count)
    ]


def percentile(values: list[float], share: float) -> float:
    """Percentil por rango más cercano: el valor observado que cubre esa proporción."""
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * share) - 1)]


def measure(count: int, warmup: int = 3) -> dict:
    previous = os.environ.get("NAFTA2GO_API_TOKEN")
    os.environ["NAFTA2GO_API_TOKEN"] = TOKEN
    try:
        return _measure(count, warmup)
    finally:
        if previous is None:
            os.environ.pop("NAFTA2GO_API_TOKEN")
        else:
            os.environ["NAFTA2GO_API_TOKEN"] = previous


def _measure(count: int, warmup: int) -> dict:
    with tempfile.TemporaryDirectory() as directory:
        url = f"sqlite:///{Path(directory) / 'medicion.db'}"
        upgrade_to_head(url)
        engine = create_db_engine(url)
        app = create_app(engine, provider_factory=lambda: RecordedRoutes(MATRIX))
        headers = {"Authorization": f"Bearer {TOKEN}"}
        latencies, statuses, outcomes = [], {}, {}
        try:
            with TestClient(app) as client:
                for body in bodies(warmup):
                    client.post("/api/v1/recommendations", json=body, headers=headers)
                for body in bodies(count):
                    started = time.perf_counter()
                    response = client.post("/api/v1/recommendations", json=body, headers=headers)
                    latencies.append(time.perf_counter() - started)
                    statuses[response.status_code] = statuses.get(response.status_code, 0) + 1
                    outcome = response.json().get("outcome", "error")
                    outcomes[outcome] = outcomes.get(outcome, 0) + 1
            with engine.connect() as conn:
                audit = audit_recommendations(repo.recommendations_with_run_status(conn))
        finally:
            engine.dispose()
    return {
        "format_version": 1,
        "measured_at_utc": datetime.now(UTC).isoformat(),
        "scope": "api_in_process_recorded_routes",
        "use_case": "UC01",
        "requests": count,
        "warmup_requests": warmup,
        "statuses": {str(key): value for key, value in sorted(statuses.items())},
        "outcomes": dict(sorted(outcomes.items())),
        "latency_s": {
            "p50": round(statistics.median(latencies), 4),
            "p95": round(percentile(latencies, 0.95), 4),
            "max": round(max(latencies), 4),
        },
        "excludes": ["llamada real a OpenRouteService", "red entre cliente y servidor"],
        "matrix_file": str(MATRIX.relative_to(ROOT)),
        # Auditoría de lo guardado durante la medición, calentamiento incluido.
        "audit": audit,
        "code": code_provenance(),
        "environment": {
            "python": platform.python_version(),
            "platform": f"{platform.system()} {platform.machine()}",
            "processor": platform.processor() or None,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requests", type=int, default=120)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.requests < 1:
        parser.error("--requests debe ser positivo")
    report = measure(args.requests)
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
