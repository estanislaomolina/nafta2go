"""Escenario histórico congelado (POC-02): precios de una captura vigente pasada.

Se lee desde el recorte versionado en docs/evidencia/ y se normaliza con las
reglas de POC-01, pero no se ingiere en la base: si se guardara como vigente,
la consulta actual lo tomaría como la última captura y presentaría precios
viejos como actuales.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

from nafta2go.application.coverage_rules import HISTORICAL_SCENARIO_DIR
from nafta2go.normalization.pipeline import normalize
from nafta2go.normalization.reading import read_raw
from nafta2go.persistence.repository import price_record

SCENARIO_FILE = "escenario.json"


class ScenarioIntegrityError(ValueError):
    """El recorte no coincide con el que registra la ficha del escenario."""


@dataclass(frozen=True)
class ScenarioPrices:
    scenario_id: str
    reference_at: datetime
    extract_sha256: str
    source_sha256: str
    rows: tuple[dict, ...]


def load_scenario(directory: Path = HISTORICAL_SCENARIO_DIR) -> ScenarioPrices:
    meta = json.loads((directory / SCENARIO_FILE).read_text(encoding="utf-8"))
    extract = directory / meta["extract"]["file"]
    actual = hashlib.sha256(extract.read_bytes()).hexdigest()
    if actual != meta["extract"]["sha256"]:
        raise ScenarioIntegrityError(
            f"{extract.name}: SHA-256 {actual}, la ficha registra {meta['extract']['sha256']}"
        )

    reference_at = datetime.fromisoformat(meta["reference_at"])
    # Las fechas de la fuente son hora local sin zona, igual que en la ingesta.
    ingested_at = pd.Timestamp(reference_at.replace(tzinfo=None))
    result = normalize(read_raw(extract, "vigente"), "vigente", ingested_at)
    rows = tuple({"id": None, **price_record(row)} for row in result.rows)
    return ScenarioPrices(
        scenario_id=meta["scenario_id"],
        reference_at=reference_at,
        extract_sha256=actual,
        source_sha256=meta["source"]["sha256"],
        rows=rows,
    )
