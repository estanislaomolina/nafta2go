"""Mide veinte diagnósticos reales en una copia SQLite, con rutas sintéticas."""

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from nafta2go.application.price_dataset import code_provenance  # noqa: E402
from nafta2go.persistence.database import create_db_engine  # noqa: E402
from nafta2go.presentation.http import create_app  # noqa: E402
from scripts.measure_query_latency import bodies, percentile  # noqa: E402
from scripts.validate_simulated_scenarios import SyntheticRoutes  # noqa: E402


def measure(database, reference_at, count=5, oracle=None):
    if reference_at.utcoffset() is None or not 1 <= count <= 100:
        raise ValueError("Se requiere zona horaria y entre una y cien consultas")
    body = bodies(1)[0] | {
        "max_candidates": 20,
        "consumption_l_per_100km": "10",
        "tank_capacity_l": "50",
        "remaining_l": "10",
        "budget_ars": "12000",
    }
    runs = []
    with tempfile.TemporaryDirectory() as folder:
        snapshot = Path(folder) / "copia.db"
        with sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True) as source:
            with sqlite3.connect(snapshot) as destination:
                source.backup(destination)
        engine = create_db_engine("sqlite:///" + str(snapshot))
        try:
            with patch.dict(
                os.environ,
                {
                    "NAFTA2GO_API_TOKEN": "codigo-medicion-local",
                    "NAFTA2GO_MAX_PRICE_AGE_DAYS": "30",
                },
            ):
                app = create_app(
                    engine,
                    provider_factory=SyntheticRoutes,
                    clock=lambda: reference_at,
                    routing_provider="synthetic-routes-real-history",
                )
                with TestClient(app) as client:
                    for _ in range(count):
                        start = time.perf_counter()
                        response = client.post(
                            "/api/v1/recommendations",
                            json=body,
                            headers={"Authorization": "Bearer codigo-medicion-local"},
                        )
                        elapsed = time.perf_counter() - start
                        block = response.json().get("conservative_ranking", {})
                        diagnostics = block.get("diagnostics", [])
                        runs.append(
                            {
                                "seconds": elapsed,
                                "http_status": response.status_code,
                                "diagnostics": len(diagnostics),
                                "available": block.get("status") == "available",
                                "diagnostics_equal": diagnostics == oracle
                                if oracle is not None
                                else None,
                            }
                        )
        finally:
            engine.dispose()
    return {
        "scope": "real_history_api_in_process_synthetic_routes",
        "reference_at": reference_at.isoformat(),
        "source_database_unchanged": True,
        "runs": runs,
        "p95_nearest_rank_seconds": percentile([r["seconds"] for r in runs], 0.95),
        "diagnostics_sha256": hashlib.sha256(
            json.dumps(diagnostics, sort_keys=True).encode()
        ).hexdigest(),
        "passed": all(
            r["http_status"] == 200
            and r["diagnostics"] == 20
            and r["available"]
            and (r["diagnostics_equal"] is not False)
            for r in runs
        ),
        "code": code_provenance(),
        "limitations": [
            "Copia local e HTTP en proceso; no incluye red, ORS ni AWS.",
            "La muestra no acredita SLA ni p95 poblacional.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--reference-at", type=datetime.fromisoformat, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = measure(args.database, args.reference_at)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
