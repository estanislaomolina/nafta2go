"""Demostración sintética de rutas y motor, ejecutable sin red ni credenciales."""

import argparse
from collections.abc import Sequence
from decimal import Decimal, InvalidOperation

from nafta2go.adapters.routing import DistanceMatrix, Point
from nafta2go.application.recommendation import Candidate, evaluate_stations
from nafta2go.domain.engine import DiscardReason, FuelRequest

ORIGIN = Point(lat=-34.60, lon=-58.38)
DESTINATION = Point(lat=-34.56, lon=-58.45)
STATIONS = (
    Point(lat=-34.61, lon=-58.39),
    Point(lat=-34.62, lon=-58.40),
    Point(lat=-34.63, lon=-58.41),
)

REASON_LABELS = {
    DiscardReason.ROUTE_UNAVAILABLE: "No se obtuvo una ruta completa.",
    DiscardReason.STATION_UNREACHABLE: "El combustible no alcanza para llegar.",
    DiscardReason.RESERVE_AT_STATION: "Llegar consumiría parte de la reserva.",
    DiscardReason.NO_BUDGET: "No hay presupuesto para cargar.",
    DiscardReason.NO_TANK_SPACE: "No hay espacio en el tanque para cargar.",
    DiscardReason.INSUFFICIENT_FUEL_FOR_TRIP: "La carga no alcanza para terminar con reserva.",
}


class DemoRoutingProvider:
    """Escenario fijo ficticio: dos recorridos completos y uno sin ruta de salida."""

    def matrix(self, sources: Sequence[Point], destinations: Sequence[Point]) -> DistanceMatrix:
        if list(sources) != [ORIGIN, *STATIONS] or list(destinations[:-1]) != list(STATIONS):
            raise ValueError("El proveedor de demostración sólo admite el escenario fijo")
        if destinations[-1] not in (ORIGIN, DESTINATION):
            raise ValueError("El proveedor de demostración no admite ese destino")
        round_trip = destinations[-1] == ORIGIN
        return DistanceMatrix(
            durations_s=[
                [900, 1200, 600, 0 if round_trip else 1800],
                [0, None, None, 1500],
                [None, 0, None, 900],
                [None, None, 0, None],
            ],
            distances_m=[
                [10000, 20000, 5000, 0 if round_trip else 25000],
                [0, None, None, 20000],
                [None, 0, None, 10000],
                [None, None, 0, None],
            ],
            sources=list(sources),
            destinations=list(destinations),
        )


def _decimal(text: str) -> Decimal:
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise argparse.ArgumentTypeError(
            "Se requiere un número decimal, por ejemplo 12000.50"
        ) from exc


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--presupuesto", type=_decimal, default=Decimal(12000), help="Pesos disponibles"
    )
    parser.add_argument("--litros-iniciales", type=_decimal, default=Decimal(10))
    parser.add_argument("--consumo", type=_decimal, default=Decimal(10), help="Litros cada 100 km")
    parser.add_argument("--capacidad", type=_decimal, default=Decimal(50), help="Litros del tanque")
    parser.add_argument("--reserva", type=_decimal, default=Decimal(2), help="Litros mínimos")
    parser.add_argument("--sin-destino", action="store_true", help="Evaluar ida y vuelta al origen")
    args = parser.parse_args(argv)
    try:
        request = FuelRequest(
            consumption_l_per_100km=args.consumo,
            tank_capacity_l=args.capacidad,
            remaining_l=args.litros_iniciales,
            budget_ars=args.presupuesto,
            reserve_l=args.reserva,
        )
    except ValueError as exc:
        message = str(exc)
        for field, flag in (
            ("consumption_l_per_100km", "--consumo"),
            ("tank_capacity_l", "--capacidad"),
            ("remaining_l", "--litros-iniciales"),
            ("budget_ars", "--presupuesto"),
            ("reserve_l", "--reserva"),
        ):
            message = message.replace(field, flag)
        parser.error(f"Consulta inválida: {message}")

    candidates = [
        Candidate("demo-a", STATIONS[0], Decimal(1200)),
        Candidate("demo-b", STATIONS[1], Decimal(1500)),
        Candidate("demo-sin-ruta", STATIONS[2], Decimal(1100)),
    ]
    results = evaluate_stations(
        request,
        candidates,
        ORIGIN,
        None if args.sin_destino else DESTINATION,
        DemoRoutingProvider(),
    )
    print("DEMOSTRACIÓN SINTÉTICA: estaciones, precios y rutas ficticios.")
    print("Sin conexión a servicios externos. Estos resultados no orientan una carga real.")
    print("Recorrido:", "ida y vuelta al origen" if args.sin_destino else "con destino")
    print(f"Presupuesto: ${request.budget_ars:.2f}; reserva: {request.reserve_l:.2f} L")
    print("Evaluación de candidatas, en orden de entrada (sin ranking):")
    for item in results:
        print(f"\n{item.candidate.station_id} — ${item.candidate.price_ars_per_l:.2f}/L")
        if not item.evaluation.feasible:
            for reason in item.evaluation.reasons:
                print(f"  Descartada: {REASON_LABELS[reason]}")
            continue
        metrics = item.evaluation.metrics
        print(f"  Llegada a la estación: {metrics.arrival_l:.2f} L")
        print(f"  Compra estimada: {metrics.purchased_l:.2f} L por ${metrics.cost_ars:.2f}")
        print(f"  Consumo total: {metrics.total_consumption_l:.2f} L")
        print(f"  Combustible al finalizar: {metrics.final_l:.2f} L")
        print(f"  Ganancia neta: {metrics.net_gain_l:.2f} L")
        print(f"  Desvío: {metrics.extra_km:.2f} km; tiempo adicional: {metrics.extra_min:.2f} min")
    if not any(item.evaluation.feasible for item in results):
        print("\nNinguna alternativa viable para esta consulta sintética.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
