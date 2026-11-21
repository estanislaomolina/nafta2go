"""Diez escenarios técnicos, sin participantes ni respuestas humanas simuladas.

Ejecuta la API y audita lo persistido en una base temporal. Por defecto usa rutas
sintéticas. --live-routes permite hasta diez matrices ORS reales; requiere clave.
Los precios son la captura histórica del repositorio, nunca precios actuales.
"""

import argparse
import json
import os
import sys
import tempfile
import time
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from nafta2go.adapters.openrouteservice import client_from_env  # noqa: E402
from nafta2go.adapters.routing import DistanceMatrix  # noqa: E402
from nafta2go.application.price_dataset import code_provenance  # noqa: E402
from nafta2go.application.recommendation_audit import audit_recommendations  # noqa: E402
from nafta2go.persistence import repository as repo  # noqa: E402
from nafta2go.persistence.database import create_db_engine, upgrade_to_head  # noqa: E402
from nafta2go.presentation.http import create_app  # noqa: E402
from scripts.measure_query_latency import percentile  # noqa: E402

REFERENCE = datetime(2026, 10, 26, 12, tzinfo=UTC)
TOKEN = "codigo-de-validacion-sintetica"


class SyntheticRoutes:
    """Distancias constantes de QA; no representan calles ni tráfico real."""

    def matrix(self, sources, destinations):
        return DistanceMatrix(
            [[1000] * len(destinations) for _ in sources],
            [[100] * len(destinations) for _ in sources],
            list(sources),
            list(destinations),
        )


def scenarios():
    for index in range(10):
        body = {
            "origin": {"lat": -34.6037, "lon": -58.3816},
            "destination": {"lat": -34.5627, "lon": -58.4565} if index < 5 else None,
            "fuel_type": "premium" if index % 2 else "super",
            "schedule_id": 3 if index in (3, 8) else 2,
            "max_candidates": 20 if index in (2, 7) else 10,
            "consumption_l_per_100km": str(5 + index % 5),
            "tank_capacity_l": "50",
            "remaining_l": "10",
            "budget_ars": "0" if index in (4, 9) else str(8000 + index * 1000),
            "reserve_l": "2",
        }
        yield f"caso-{index + 1:02}", body


def result_checks(response, body):
    if response.status_code != 200:
        return {"http_ok": False}
    result = response.json()
    evaluations = {r["station_id"]: r for r in result["evaluations"]}
    chosen = [evaluations[c["station_id"]] for c in result["alternatives"]]
    expected = "no_feasible_stations" if body["budget_ars"] == "0" else "recommended"
    return {
        "http_ok": True,
        "expected_outcome": result["outcome"] == expected,
        "historical_label": result["status"] == "historical_scenario"
        and result["scenario"] is not None,
        "choice_count": 1 <= len(chosen) <= 3 if expected == "recommended" else not chosen,
        "physical_constraints": all(
            row["feasible"]
            and row["metrics"] is not None
            and Decimal(row["metrics"]["cost_ars"]) <= Decimal(body["budget_ars"])
            and Decimal(row["metrics"]["final_l"]) >= Decimal(body["reserve_l"])
            and Decimal(row["metrics"]["final_l"]) <= Decimal(body["tank_capacity_l"])
            for row in chosen
        ),
        "discard_reasons": all(
            row["reasons"] for row in evaluations.values() if not row["feasible"]
        ),
        "conservative_abstention": result["conservative_ranking"]["status"] == "unavailable",
    }


def measure(provider_factory=SyntheticRoutes, *, live=False):
    previous = os.environ.get("NAFTA2GO_API_TOKEN")
    os.environ["NAFTA2GO_API_TOKEN"] = TOKEN
    cases = []
    try:
        with tempfile.TemporaryDirectory() as directory:
            url = f"sqlite:///{Path(directory) / 'validacion.db'}"
            upgrade_to_head(url)
            engine = create_db_engine(url)
            app = create_app(
                engine,
                provider_factory=provider_factory,
                clock=lambda: REFERENCE,
                routing_provider="openrouteservice-live-validation"
                if live
                else "synthetic-validation",
            )
            try:
                with TestClient(app) as client:
                    for case_id, body in scenarios():
                        started = time.perf_counter()
                        response = client.post(
                            "/api/v1/recommendations",
                            json=body,
                            headers={"Authorization": f"Bearer {TOKEN}"},
                        )
                        cases.append(
                            {
                                "case_id": case_id,
                                "use_case": "UC01" if body["destination"] else "UC02",
                                "fuel_type": body["fuel_type"],
                                "schedule_id": body["schedule_id"],
                                "budget_ars": body["budget_ars"],
                                "max_candidates": body["max_candidates"],
                                "elapsed_s": round(time.perf_counter() - started, 6),
                                "http_status": response.status_code,
                                "checks": result_checks(response, body),
                            }
                        )
                with engine.connect() as conn:
                    audit = audit_recommendations(repo.recommendations_with_run_status(conn))
            finally:
                engine.dispose()
    finally:
        if previous is None:
            os.environ.pop("NAFTA2GO_API_TOKEN", None)
        else:
            os.environ["NAFTA2GO_API_TOKEN"] = previous
    return {
        "format_version": 1,
        "measured_at_utc": datetime.now(UTC).isoformat(),
        "scope": "technical_scenarios_not_user_study",
        "real_participants": 0,
        "routes": "live_openrouteservice" if live else "synthetic_constant_matrix",
        "prices": "repository_historical_capture",
        "reference_at": REFERENCE.isoformat(),
        "cases": cases,
        "passed_cases": sum(all(c["checks"].values()) for c in cases),
        "latency_s": {
            uc: {
                "p95": percentile([c["elapsed_s"] for c in cases if c["use_case"] == uc], 0.95),
                "requests": sum(c["use_case"] == uc for c in cases),
            }
            for uc in ("UC01", "UC02")
        },
        "audit": audit,
        "audit_passed": all(not errors for errors in audit["fallas"].values())
        and audit["recommendations"] == 10,
        "code": code_provenance(),
        "limitations": [
            "No mide utilidad ni comprensión humana; no hay participantes reales.",
            "API en proceso: excluye red cliente-servidor, tráfico y teléfono físico.",
            "Cinco consultas por caso de uso no acreditan capacidad ni un SLA.",
            "Precios históricos rotulados; ranking conservador no disponible. "
            "Su integración se prueba por separado.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live-routes", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.live_routes and not os.environ.get("ORS_API_KEY", "").strip():
        parser.error("--live-routes requiere ORS_API_KEY")
    report = measure(
        client_from_env if args.live_routes else SyntheticRoutes, live=args.live_routes
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return 0 if report["passed_cases"] == 10 and report["audit_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
