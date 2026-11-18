"""Regla provisional de desvío respecto de la referencia servida (ADR-021).

Un desvío mayor al umbral no prueba que el precio publicado esté mal: sólo indica que
se aleja de la referencia más que lo habitual en la calibración de ADR-017.
"""

from dataclasses import dataclass
from decimal import Decimal

RULE_VERSION = "conservative-v1"
THRESHOLDS: dict[int, Decimal] = {
    2: Decimal("0.05424409844299347"),
    3: Decimal("0.054570259208731244"),
}


@dataclass(frozen=True)
class Deviation:
    relative: Decimal
    threshold: Decimal
    above: bool


def deviation(official: Decimal, reference: Decimal, product_id: int) -> Deviation:
    if product_id not in THRESHOLDS:
        raise ValueError("Producto sin umbral en la regla conservadora")
    for price in (official, reference):
        if not price.is_finite() or price <= 0:
            raise ValueError("Los precios deben ser positivos y finitos")
    threshold = THRESHOLDS[product_id]
    relative = abs(official - reference) / reference
    return Deviation(relative=relative, threshold=threshold, above=relative > threshold)
