"""Tres prioridades determinísticas, agrupando las que eligen la misma estación."""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Context, Decimal, localcontext

from nafta2go.domain.engine import Evaluation


@dataclass(frozen=True)
class Choice:
    station_id: str
    priorities: tuple[str, ...]


def rank_alternatives(evaluations: Mapping[str, Evaluation]) -> tuple[Choice, ...]:
    with localcontext(Context(prec=28)):
        return _rank(evaluations)


def _rank(evaluations: Mapping[str, Evaluation]) -> tuple[Choice, ...]:
    feasible = {key: value.metrics for key, value in evaluations.items() if value.feasible}
    if not feasible:
        return ()
    if any(metrics is None for metrics in feasible.values()):
        raise ValueError("evaluations: una alternativa factible requiere métricas")
    net = [m.net_gain_l for m in feasible.values()]
    detour = [m.extra_km for m in feasible.values()]

    def normalized(value: Decimal, values: list[Decimal]) -> Decimal:
        span = max(values) - min(values)
        return Decimal(0) if span == 0 else (value - min(values)) / span

    def tie(station_id: str) -> tuple:
        m = feasible[station_id]
        return (-m.net_gain_l, m.extra_km, m.extra_min, station_id)

    def balance(station_id: str) -> tuple:
        m = feasible[station_id]
        # Igual peso a maximizar ganancia neta y minimizar kilómetros extra.
        score = normalized(m.net_gain_l, net) - normalized(m.extra_km, detour)
        return (-score, *tie(station_id))

    winners = (
        ("combustible_neto", min(feasible, key=tie)),
        (
            "menor_desvio",
            min(
                feasible,
                key=lambda key: (feasible[key].extra_km, feasible[key].extra_min, *tie(key)),
            ),
        ),
        ("equilibrio", min(feasible, key=balance)),
    )
    grouped: dict[str, list[str]] = {}
    for priority, station_id in winners:
        grouped.setdefault(station_id, []).append(priority)
    return tuple(Choice(key, tuple(priorities)) for key, priorities in grouped.items())
