"""Parámetros de cobertura de precios (POC-02). Se cambian acá y todo el código los toma.

Las decisiones y su justificación están en docs/COBERTURA.md.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from nafta2go.normalization.rules import LOCAL_TIMEZONE
from nafta2go.persistence.database import ROOT

# Un precio es reciente si se publicó como máximo hace esta cantidad de días.
MAX_PRICE_AGE_DAYS = 30
# Candidatas recientes dentro del corredor necesarias para recomendar con datos actuales.
MIN_RECENT_CANDIDATES = 3
# Desvío máximo en línea recta (origen → estación → destino menos el trayecto directo).
MAX_DETOUR_KM = 5.0

# Escenario histórico que se usa cuando la cobertura actual no alcanza.
HISTORICAL_SCENARIO_ID = "vigente-2026-10-24"
HISTORICAL_SCENARIO_REFERENCE_AT = datetime(2026, 10, 24, 18, 0, tzinfo=ZoneInfo(LOCAL_TIMEZONE))
HISTORICAL_SCENARIO_DIR = ROOT / "docs" / "evidencia" / f"escenario-{HISTORICAL_SCENARIO_ID}"
