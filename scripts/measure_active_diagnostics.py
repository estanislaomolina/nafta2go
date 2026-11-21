"""Carga sintética identificada: veinte candidatas con diagnóstico activo, sin red.

No mide el histórico real ni precisión de alertas. La compatibilidad de la política
se sustituye sólo dentro del ensayo para el manifiesto sintético generado.
"""

import argparse
import hashlib
import json
import os
import sys
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from nafta2go.application.price_dataset import code_provenance  # noqa: E402
from nafta2go.application.price_diagnostic import ASSUMPTION  # noqa: E402
from nafta2go.application.scenario import load_scenario  # noqa: E402
from nafta2go.ml.temporal import FEATURES_VERSION  # noqa: E402
from nafta2go.persistence import repository as repo  # noqa: E402
from nafta2go.persistence.database import create_db_engine, upgrade_to_head  # noqa: E402
from nafta2go.persistence.models import RawCapture  # noqa: E402
from nafta2go.persistence.schema import station_prices  # noqa: E402
from nafta2go.presentation.http import create_app  # noqa: E402
from scripts.measure_query_latency import percentile  # noqa: E402
from scripts.validate_simulated_scenarios import SyntheticRoutes  # noqa: E402

NOW = datetime(2026, 1, 4, tzinfo=UTC)
TARGET = datetime(2026, 1, 3, 12)


def prepare(engine, directory, history_days):
    base = load_scenario().rows[0] | {
        "id": None,
        "lat": -34.60,
        "lon": -58.40,
        "product_id": 2,
        "fuel_type": "super",
        "schedule_id": 2,
        "brand": "CARGA SINTETICA",
        "alerts": "",
    }
    with engine.begin() as conn:
        for source in ["historico", "vigente"]:
            run = repo.start_run(conn, source, TARGET)
            repo.add_raw_capture(
                conn,
                run,
                RawCapture(
                    source,
                    "https://example.invalid/fixture",
                    "f" * 64,
                    0,
                    "synthetic-not-a-real-capture",
                    TARGET,
                ),
            )
            rows = [
                base
                | {
                    "station_id": 100 + station,
                    "source_row": 1 + day * 20 + station,
                    "valid_from": TARGET - timedelta(days=day),
                    "price": 1000 + station,
                    "run_id": run,
                }
                for day in (range(1, history_days + 1) if source == "historico" else [0])
                for station in range(20)
            ]
            conn.execute(station_prices.insert(), rows)
            repo.finish_run(conn, run, "succeeded", TARGET, rules_version="1")
    shared = {
        "format_version": 1,
        "features_version": FEATURES_VERSION,
        "source_sha256": "f" * 64,
        "dataset_sha256": "d" * 64,
        "availability_assumption": ASSUMPTION,
    }
    dataset = shared | {
        "source": "historico",
        "normalization_rules_version": "1",
        "parameters": {"window_days": 30, "min_history": 5},
    }
    raw = json.dumps(dataset, sort_keys=True).encode()
    (directory / "dataset").mkdir()
    (directory / "model").mkdir()
    (directory / "dataset/manifest.json").write_bytes(raw)
    model = shared | {
        "chosen_method": "bandera_reciente",
        "dataset_manifest_sha256": hashlib.sha256(raw).hexdigest(),
    }
    raw = json.dumps(model, sort_keys=True).encode()
    (directory / "model/manifest.json").write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def measure(runs=5, history_days=60):
    results = []
    with tempfile.TemporaryDirectory() as folder:
        directory = Path(folder)
        url = f"sqlite:///{directory / 'carga.db'}"
        upgrade_to_head(url)
        engine = create_db_engine(url)
        version = prepare(engine, directory, history_days)
        environment = {
            "NAFTA2GO_API_TOKEN": "codigo-carga-sintetica",
            "NAFTA2GO_PRICE_DATASET_DIR": str(directory / "dataset"),
            "NAFTA2GO_PRICE_MODEL_DIR": str(directory / "model"),
            "NAFTA2GO_MAX_PRICE_AGE_DAYS": "30",
        }
        try:
            with (
                patch.dict(os.environ, environment),
                patch("nafta2go.domain.price_alert.AUDITED_MODEL_VERSION", version),
            ):
                app = create_app(
                    engine,
                    provider_factory=SyntheticRoutes,
                    clock=lambda: NOW,
                    routing_provider="synthetic-active-diagnostic-validation",
                )
                with TestClient(app) as client:
                    for _ in range(runs):
                        start = time.perf_counter()
                        response = client.post(
                            "/api/v1/recommendations",
                            headers={"Authorization": "Bearer codigo-carga-sintetica"},
                            json={
                                "origin": {"lat": -34.60, "lon": -58.40},
                                "fuel_type": "super",
                                "max_candidates": 20,
                                "consumption_l_per_100km": "10",
                                "tank_capacity_l": "50",
                                "remaining_l": "10",
                                "budget_ars": "12000",
                                "reserve_l": "2",
                            },
                        )
                        elapsed = time.perf_counter() - start
                        body = response.json()
                        block = body.get("conservative_ranking", {})
                        results.append(
                            {
                                "http_status": response.status_code,
                                "elapsed_s": elapsed,
                                "evaluated": len(body.get("evaluations", [])),
                                "diagnostics": len(block.get("diagnostics", [])),
                                "active": block.get("status") == "available"
                                and all(
                                    d["alert_policy_version"] == "conservative-v1"
                                    for d in block.get("diagnostics", [])
                                ),
                            }
                        )
        finally:
            engine.dispose()
    return {
        "scope": "synthetic_active_diagnostics_not_real_history",
        "observed_at_utc": datetime.now(UTC).isoformat(),
        "policy_compatibility": "synthetic_manifest_override_only_in_harness",
        "history_rows": history_days * 20,
        "candidates": 20,
        "runs": results,
        "p95_s": percentile([r["elapsed_s"] for r in results], 0.95),
        "passed": all(
            r["http_status"] == 200 and r["evaluated"] == r["diagnostics"] == 20 and r["active"]
            for r in results
        ),
        "code": code_provenance(),
        "limitations": [
            "Rutas, precios y manifiestos sintéticos, sin tráfico externo.",
            "No acredita latencia con el histórico real, red del cliente ni disponibilidad.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = measure()
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
