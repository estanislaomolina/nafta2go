"""Parámetros de cobertura de precios y vigencia configurable del MVP.

Las decisiones y su justificación están en docs/COBERTURA.md.
"""

import os
from datetime import datetime
from zoneinfo import ZoneInfo

from nafta2go.normalization.rules import LOCAL_TIMEZONE
from nafta2go.persistence.database import ROOT

# Un precio es reciente si se publicó como máximo hace esta cantidad de días.
MAX_PRICE_AGE_DAYS = 30


class CoverageConfigurationError(RuntimeError):
    """Política operativa inválida; no depende de la entrada del conductor."""


def configured_max_price_age_days() -> int:
    value = os.environ.get("NAFTA2GO_MAX_PRICE_AGE_DAYS", str(MAX_PRICE_AGE_DAYS))
    if not (value.isascii() and value.isdigit() and 1 <= len(value) <= 2):
        raise CoverageConfigurationError("La vigencia configurada debe ser un entero de 1 a 30")
    days = int(value)
    if not 1 <= days <= MAX_PRICE_AGE_DAYS:
        raise CoverageConfigurationError("La vigencia configurada debe ser un entero de 1 a 30")
    return days


# Candidatas recientes dentro del corredor necesarias para recomendar con datos actuales.
MIN_RECENT_CANDIDATES = 3
# Desvío máximo en línea recta (origen → estación → destino menos el trayecto directo).
MAX_DETOUR_KM = 5.0

# Escenario histórico que se usa cuando la cobertura actual no alcanza.
HISTORICAL_SCENARIO_ID = "vigente-2026-10-24"
HISTORICAL_SCENARIO_REFERENCE_AT = datetime(2026, 10, 24, 18, 0, tzinfo=ZoneInfo(LOCAL_TIMEZONE))
HISTORICAL_SCENARIO_DIR = ROOT / "docs" / "evidencia" / f"escenario-{HISTORICAL_SCENARIO_ID}"
