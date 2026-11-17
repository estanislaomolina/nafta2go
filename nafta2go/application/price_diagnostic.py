"""Referencia retrospectiva del precio publicado; no calibra alertas ni altera rankings."""

import hashlib
import json
import os
from datetime import UTC
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from nafta2go.ml.temporal import FEATURES_VERSION, build_temporal_dataset
from nafta2go.normalization.rules import LOCAL_TIMEZONE
from nafta2go.persistence import repository as repo

ASSUMPTION = "valid_from_proxy_retrospective_not_verified"
METHODS = {
    "mediana_previa": ("prior_median",),
    "ultimo_precio": ("previous_station_price", "prior_median"),
    "bandera_reciente": ("brand_recent_median", "previous_station_price", "prior_median"),
}


class DiagnosticUnavailable(Exception):
    """Falta configuración compatible o datos trazables; no exportar el error original."""


def reference_price(features, method):
    reference = next(features[key] for key in METHODS[method] if features[key] is not None)
    return Decimal(str(reference)).quantize(Decimal("0.001"))


def _selection():
    try:
        if any(
            not os.environ.get(key, "").strip()
            for key in ("NAFTA2GO_PRICE_DATASET_DIR", "NAFTA2GO_PRICE_MODEL_DIR")
        ):
            raise ValueError("Falta configuración")
        dataset_bytes = (
            Path(os.environ["NAFTA2GO_PRICE_DATASET_DIR"]) / "manifest.json"
        ).read_bytes()
        raw = (Path(os.environ["NAFTA2GO_PRICE_MODEL_DIR"]) / "manifest.json").read_bytes()
        dataset, model = json.loads(dataset_bytes), json.loads(raw)
        options = dataset["parameters"]
        window, minimum = options["window_days"], options["min_history"]
        valid = (
            dataset["format_version"] == model["format_version"] == 1
            and dataset["features_version"] == model["features_version"] == FEATURES_VERSION
            and dataset["source"] == "historico"
            and isinstance(dataset["normalization_rules_version"], str)
            and dataset["availability_assumption"] == model["availability_assumption"] == ASSUMPTION
            and model["dataset_manifest_sha256"] == hashlib.sha256(dataset_bytes).hexdigest()
            and model["dataset_sha256"] == dataset["dataset_sha256"]
            and model["source_sha256"] == dataset["source_sha256"]
            and model["chosen_method"] in METHODS
            and type(window) is int
            and 1 <= window <= 365
            and type(minimum) is int
            and 3 <= minimum <= 100
        )
        if not valid:
            raise ValueError("Selección incompatible")
        return model, dataset, hashlib.sha256(raw).hexdigest()
    except (KeyError, OSError, ValueError, TypeError) as exc:
        raise DiagnosticUnavailable from exc


def price_diagnostic(engine, station_id, product_id, schedule_id, now):
    if now.utcoffset() is None:
        raise ValueError("La referencia requiere zona horaria")
    model, dataset, version = _selection()
    local_now = now.astimezone(ZoneInfo(LOCAL_TIMEZONE)).replace(tzinfo=None)
    with engine.connect() as conn:
        current = repo.latest_successful_run(conn, "vigente")
        historical = repo.latest_successful_run(conn, "historico")
        if current is None or historical is None:
            raise DiagnosticUnavailable
        if any(
            repo.get_run(conn, run)["rules_version"] != dataset["normalization_rules_version"]
            for run in (current, historical)
        ):
            raise DiagnosticUnavailable
        capture = repo.raw_capture_for_run(conn, historical)
        if capture is None or capture["sha256"] != model["source_sha256"]:
            raise DiagnosticUnavailable
        target = repo.diagnostic_publication(
            conn, current, station_id, product_id, schedule_id, local_now
        )
        if target is None:
            return None
        history = repo.diagnostic_history(
            conn, historical, product_id, schedule_id, target["valid_from"]
        )
    # Misma preparación que el entrenamiento; todo el instante objetivo queda fuera del contexto.
    examples, _ = build_temporal_dataset(
        [*history, target],
        now,
        window_days=dataset["parameters"]["window_days"],
        min_history=dataset["parameters"]["min_history"],
    )
    published = target["valid_from"].replace(tzinfo=ZoneInfo(LOCAL_TIMEZONE)).astimezone(UTC)
    example = next(
        (
            r
            for r in examples
            if r["station_id"] == station_id and r["target_at_utc"] == published.isoformat()
        ),
        None,
    )
    value = reference_price(example["features"], model["chosen_method"]) if example else None
    return {
        "scope": "published_price_retrospective",
        "status": "reference_only" if value is not None else "unavailable",
        "station_id": station_id,
        "product_id": product_id,
        "schedule_id": schedule_id,
        "official_price_ars_per_l": str(target["price"]),
        "published_at": published.isoformat(),
        "reference_ars_per_l": str(value) if value is not None else None,
        "difference_ars_per_l": str(target["price"] - value) if value is not None else None,
        "alert_level": "not_calibrated",
        "reason": "alert_policy_not_validated" if value is not None else "context_unavailable",
        "method": model["chosen_method"],
        "version": version,
        "features_version": FEATURES_VERSION,
        "data_run_id": current,
        "history_run_id": historical,
        "history_sha256": capture["sha256"],
        "availability_assumption": ASSUMPTION,
    }
