"""Consulta con precios reales y rutas en vivo o una matriz real guardada."""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError

from nafta2go.adapters.recorded_routes import CapturedRoutes, RecordedRoutes, matrix_bytes
from nafta2go.adapters.routing import (
    InvalidCredentials,
    Point,
    ProviderTimeout,
    QuotaExceeded,
    RoutingError,
)
from nafta2go.application.coverage_rules import (
    MIN_RECENT_CANDIDATES,
    CoverageConfigurationError,
    configured_max_price_age_days,
)
from nafta2go.application.query import recommend
from nafta2go.application.recommendation import DEFAULT_CANDIDATE_LIMIT, MAX_CANDIDATES
from nafta2go.domain.engine import FuelRequest
from nafta2go.persistence.database import create_db_engine, database_url, upgrade_to_head
from nafta2go.presentation.cli_telemetry import CliObservation
from nafta2go.presentation.navigation import present_recommendation


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, _message):
        self.print_usage(sys.stderr)
        self.exit(2, "Argumentos inválidos; consultá --help.\n")


def error_code(exc):
    for error, code in (
        (CoverageConfigurationError, "coverage_not_configured"),
        (InvalidCredentials, "routes_not_configured"),
        (ProviderTimeout, "routes_timeout"),
        (QuotaExceeded, "routes_quota_exceeded"),
        (RoutingError, "routes_unavailable"),
        (SQLAlchemyError, "data_unavailable"),
        (OSError, "file_unavailable"),
    ):
        if isinstance(exc, error):
            return code
    return "invalid_request"


def point(value: str) -> Point:
    try:
        lat, lon = value.split(",")
        return Point(float(lat), float(lon))
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError("usar LAT,LON dentro de sus rangos") from exc


def render(payload: dict) -> str:
    lines = [f"Cobertura: {payload['status']}; resultado: {payload['outcome']}"]
    if payload["scenario"]:
        lines.append(
            "ESCENARIO HISTÓRICO: precios referidos a "
            + payload["scenario"]["reference_at"]
            + "; no son precios actuales."
        )
    lines.append(f"Referencia de precios: {payload['price_reference_at']}")
    lines.append(f"Vigencia máxima aplicada: {payload['query']['max_price_age_days']} días")
    if (payload.get("routes") or {}).get("replayed"):
        lines.append("Rutas REPRODUCIDAS de " + payload["routes"]["captured_at_utc"])
    elif (payload.get("routes") or {}).get("cache_hit"):
        lines.append("Rutas REUTILIZADAS de " + payload["routes"]["captured_at_utc"])
    lines.append("Consulta: " + json.dumps(payload["query"], ensure_ascii=False))
    navigation = {link["station_id"]: link for link in payload.get("navigation", [])}
    evaluations = {row["station_id"]: row for row in payload["evaluations"]}
    for choice in payload["alternatives"]:
        row = evaluations[choice["station_id"]]
        metrics = row["metrics"]
        lines.extend(
            [
                f"Estación {row['station_id']} — {row['brand']} — {row['address']}",
                "  Prioridades: " + ", ".join(choice["priorities"]),
                f"  Precio: ARS {row['price_ars_per_l']}/L; publicado: {row['published_at_local']}",
                f"  Compra: {float(metrics['purchased_l']):.3f} L; "
                f"costo: ARS {float(metrics['cost_ars']):.2f}",
                f"  Consumo: {float(metrics['total_consumption_l']):.3f} L; "
                f"ganancia neta: {float(metrics['net_gain_l']):.3f} L",
                f"  Final: {float(metrics['final_l']):.3f} L; "
                f"reserva exigida: {payload['query']['reserve_l']} L",
                f"  Desvío: {float(metrics['extra_km']):.3f} km / "
                f"{float(metrics['extra_min']):.2f} min",
                "  Alertas: " + (", ".join(row["alerts"]) or "ninguna"),
            ]
        )
        if link := navigation.get(choice["station_id"]):
            lines.append(f"  {link['label']}: {link['url']}")
    if payload.get("navigation_notice"):
        lines.append(payload["navigation_notice"])
    for row in payload["evaluations"]:
        if not row["feasible"]:
            lines.append(f"Descartada {row['station_id']}: " + ", ".join(row["reasons"]))
    lines.append("Fuente: " + payload["source"]["url"] + " (CC BY 4.0)")
    lines.append("La publicación no confirma stock ni precio efectivo al cargar.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    observation = CliObservation()
    emit = True
    try:
        observation.exit_code = run(argv, observation)
        return observation.exit_code
    except SystemExit as exc:
        emit = exc.code != 0
        observation.error_code = observation.outcome = "invalid_arguments"
        raise SystemExit(2 if emit else 0) from None
    except KeyboardInterrupt:
        observation.exit_code, observation.outcome = 130, "interrupted"
        observation.error_code = "interrupted"
        print("Consulta interrumpida.", file=sys.stderr)
        return 130
    except Exception:
        observation.exit_code, observation.outcome = 2, "error"
        observation.error_code = "internal_error"
        print("Consulta fallida (internal_error); revisá el estado operativo.", file=sys.stderr)
        return 2
    finally:
        if emit:
            observation.emit()


def run(argv, observation) -> int:
    parser = SafeArgumentParser(prog="nafta2go.query", description=__doc__)
    parser.add_argument("--origin", type=point, required=True)
    parser.add_argument("--destination", type=point, help="si falta, vuelve al origen")
    parser.add_argument("--fuel-type", choices=("super", "premium"), default="super")
    parser.add_argument("--schedule-id", type=int, choices=(2, 3), default=2)
    parser.add_argument(
        "--max-candidates",
        type=int,
        choices=range(MIN_RECENT_CANDIDATES, MAX_CANDIDATES + 1),
        default=DEFAULT_CANDIDATE_LIMIT,
        help="Máximo de candidatas entre 3 y 20; por defecto 10 para reproducir la POC",
    )
    parser.add_argument("--presupuesto", default="12000")
    parser.add_argument("--consumo", default="10")
    parser.add_argument("--capacidad", default="50")
    parser.add_argument("--litros-iniciales", default="10")
    parser.add_argument("--reserva", default="2")
    parser.add_argument("--reference-at", help="ISO 8601 con zona; por defecto ahora")
    routes = parser.add_mutually_exclusive_group()
    routes.add_argument("--matrix-file", type=Path, help="reproduce rutas guardadas; no usa red")
    routes.add_argument("--save-matrix", type=Path, help="guarda la matriz recibida en vivo")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    engine = None
    try:
        request = FuelRequest(
            args.consumo, args.capacidad, args.litros_iniciales, args.presupuesto, args.reserva
        )
        reference = (
            datetime.fromisoformat(args.reference_at) if args.reference_at else datetime.now(UTC)
        )
        if reference.utcoffset() is None:
            raise ValueError("reference_at: se requiere zona horaria")
        configured_max_price_age_days()
        provider = RecordedRoutes(args.matrix_file) if args.matrix_file else CapturedRoutes()
        url = database_url()
        upgrade_to_head(url)
        engine = create_db_engine(url)
        with engine.begin() as conn:
            payload = recommend(
                conn,
                request,
                args.origin,
                args.destination,
                provider,
                fuel_type=args.fuel_type,
                schedule_id=args.schedule_id,
                reference_at=reference,
                max_candidates=args.max_candidates,
                routing_provider="openrouteservice-recorded"
                if args.matrix_file
                else "openrouteservice",
            )
            evidence = provider.evidence
            if args.save_matrix and evidence is not None:
                args.save_matrix.parent.mkdir(parents=True, exist_ok=True)
                args.save_matrix.write_bytes(matrix_bytes(evidence))
        payload = present_recommendation(payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json else render(payload))
        observation.outcome = payload["outcome"]
        observation.error_code = None
        return 0
    except (ValueError, OSError, RoutingError, SQLAlchemyError, CoverageConfigurationError) as exc:
        observation.error_code = error_code(exc)
        print(
            f"Consulta fallida ({observation.error_code}); "
            "verificá entradas, configuración y dependencias.",
            file=sys.stderr,
        )
        return 2
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
