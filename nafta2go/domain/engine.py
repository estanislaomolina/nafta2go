"""Evaluación determinística de una candidata con precio y ruta ya validados."""

from dataclasses import dataclass, fields
from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_HALF_EVEN, localcontext
from enum import StrEnum


def _number(raw: object, name: str, *, positive: bool = False) -> Decimal:
    if isinstance(raw, bool) or not isinstance(raw, (int, float, str, Decimal)):
        raise ValueError(f"{name}: se requiere un número finito")
    try:
        value = Decimal(str(raw))
    except InvalidOperation as exc:
        raise ValueError(f"{name}: se requiere un número finito") from exc
    if not value.is_finite() or value < 0:
        raise ValueError(f"{name}: se requiere un número finito no negativo")
    if positive and value == 0:
        raise ValueError(f"{name}: debe ser mayor que cero")
    return value


def _validate_numbers(instance: object, *, positive: tuple[str, ...] = ()) -> None:
    for field in fields(instance):
        value = _number(getattr(instance, field.name), field.name, positive=field.name in positive)
        object.__setattr__(instance, field.name, value)


@dataclass(frozen=True)
class FuelRequest:
    consumption_l_per_100km: Decimal
    tank_capacity_l: Decimal
    remaining_l: Decimal
    budget_ars: Decimal
    reserve_l: Decimal

    def __post_init__(self) -> None:
        _validate_numbers(self, positive=("consumption_l_per_100km", "tank_capacity_l"))
        if self.remaining_l > self.tank_capacity_l:
            raise ValueError("remaining_l: supera la capacidad del tanque")
        if self.reserve_l > self.tank_capacity_l:
            raise ValueError("reserve_l: supera la capacidad del tanque")


@dataclass(frozen=True)
class Route:
    to_station_km: Decimal
    after_station_km: Decimal
    to_station_min: Decimal
    after_station_min: Decimal
    direct_km: Decimal
    direct_min: Decimal

    def __post_init__(self) -> None:
        _validate_numbers(self)


class DiscardReason(StrEnum):
    ROUTE_UNAVAILABLE = "route_unavailable"
    STATION_UNREACHABLE = "station_unreachable"
    RESERVE_AT_STATION = "reserve_at_station"
    NO_BUDGET = "no_budget"
    NO_TANK_SPACE = "no_tank_space"
    INSUFFICIENT_FUEL_FOR_TRIP = "insufficient_fuel_for_trip"


@dataclass(frozen=True)
class FuelMetrics:
    consumption_to_station_l: Decimal
    consumption_after_station_l: Decimal
    total_consumption_l: Decimal
    arrival_l: Decimal
    free_capacity_l: Decimal
    purchased_l: Decimal
    cost_ars: Decimal
    final_l: Decimal
    net_gain_l: Decimal
    final_range_km: Decimal
    extra_km: Decimal
    extra_min: Decimal


@dataclass(frozen=True)
class Evaluation:
    reasons: tuple[DiscardReason, ...]
    metrics: FuelMetrics | None

    @property
    def feasible(self) -> bool:
        return not self.reasons


def evaluate_candidate(
    request: FuelRequest, price_ars_per_l: Decimal, route: Route | None
) -> Evaluation:
    """Evalúa una candidata; una ruta ausente se descarta sin inventar distancias.

    Los adaptadores deben filtrar producto, ubicación y vigencia antes de llamar.
    No redondea litros ni importes a unidades de presentación.
    """
    # Un precio inválido es un error de contrato, no una alternativa evaluable.
    price = _number(price_ars_per_l, "price_ars_per_l", positive=True)
    if route is None:
        return Evaluation((DiscardReason.ROUTE_UNAVAILABLE,), None)

    with localcontext() as context:
        context.prec = 28
        context.rounding = ROUND_HALF_EVEN
        per_km = request.consumption_l_per_100km / 100
        to_station = route.to_station_km * per_km
        after_station = route.after_station_km * per_km
        arrival = request.remaining_l - to_station
        if arrival < 0:
            return Evaluation((DiscardReason.STATION_UNREACHABLE,), None)
        if arrival < request.reserve_l:
            return Evaluation((DiscardReason.RESERVE_AT_STATION,), None)

        free_capacity = request.tank_capacity_l - arrival
        with localcontext() as purchase_context:
            purchase_context.rounding = ROUND_DOWN
            purchased = min(request.budget_ars / price, free_capacity)
        final = arrival + purchased - after_station
        reasons = []
        if request.budget_ars == 0:
            reasons.append(DiscardReason.NO_BUDGET)
        if free_capacity == 0:
            reasons.append(DiscardReason.NO_TANK_SPACE)
        if final < request.reserve_l:
            reasons.append(DiscardReason.INSUFFICIENT_FUEL_FOR_TRIP)
        metrics = FuelMetrics(
            consumption_to_station_l=to_station,
            consumption_after_station_l=after_station,
            total_consumption_l=to_station + after_station,
            arrival_l=arrival,
            free_capacity_l=free_capacity,
            purchased_l=purchased,
            cost_ars=purchased * price,
            final_l=final,
            net_gain_l=final - request.remaining_l,
            final_range_km=max(Decimal(0), final) / per_km,
            extra_km=max(Decimal(0), route.to_station_km + route.after_station_km - route.direct_km),
            extra_min=max(Decimal(0), route.to_station_min + route.after_station_min - route.direct_min),
        )
        return Evaluation(tuple(reasons), metrics)
