"""Evalúa estimaciones para precios de más de 30 días con reingresos (#57); no se sirve.

El precio actual de una estación que no vuelve a publicar no es observable. El proxy son
los reingresos: publicaciones cuyo precio previo propio supera la antigüedad mínima. Se
elige el método con el período de selección dentro de train y la validación sólo se
reporta, igual que ADR-014.
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pandas as pd

from nafta2go.application.price_dataset import code_provenance, encoded, sha256
from nafta2go.ml.models import (
    CANDIDATES,
    build_model,
    examples_frame,
    fit,
    metrics,
    predict,
    reference_predictions,
)
from nafta2go.ml.temporal import FEATURES_VERSION

BUCKET_EDGES = (30, 60, 120, np.inf)
BUCKETS = ("31_a_60", "61_a_120", "mas_de_120")
LAST_PRICE = "ultimo_precio"


def stale_examples(frame: pd.DataFrame, min_gap_days: int) -> pd.DataFrame:
    """Reingresos: el precio previo propio tiene estrictamente más de `min_gap_days`."""
    return frame[frame.previous_age_days > min_gap_days]


def adjusted_last_price(frame: pd.DataFrame) -> tuple[pd.Series, int]:
    """Último precio propio movido según la mediana del mercado desde entonces.

    Sin ejemplo previo del grupo no hay `market_change`: se usa el último precio sin
    ajustar y se cuenta como fallback.
    """
    missing = frame.market_change.isna() & frame.previous_relative.notna()
    return frame.reference + frame.market_change.fillna(0.0), int(missing.sum())


def _predictions(fitting, evaluating, seed):
    predictions = reference_predictions(evaluating)
    predictions["ultimo_ajustado"], fallbacks = adjusted_last_price(evaluating)
    for name in CANDIDATES:
        predictions[name] = predict(fit(build_model(name, seed), fitting), evaluating)
    return predictions, fallbacks


def _score(frame, predicted):
    result = metrics(frame, predicted)
    estimate = frame.prior_median * np.exp(predicted)
    relative = (frame.target_price_ars_per_l - estimate).abs() / frame.target_price_ars_per_l
    result["p90_relative"] = float(relative.quantile(0.9))
    return result


def _group(frame, predictions, min_examples):
    if len(frame) < min_examples:
        return {"status": "insufficient_support", "examples": len(frame), "methods": None}
    return {
        "status": "candidate",
        "examples": len(frame),
        "methods": {name: _score(frame, p.loc[frame.index]) for name, p in predictions.items()},
    }


def _adoption(chosen, validation, max_mape, max_p90_relative):
    overall = validation["overall"]["methods"]
    supported = [s["methods"] for s in validation["segments"].values() if s["methods"]]
    checks = {
        "max_mape": bool(overall) and overall[chosen]["mape"] <= max_mape,
        "max_p90_relative": bool(overall) and overall[chosen]["p90_relative"] <= max_p90_relative,
        "beats_last_price_in_supported_segments": bool(supported)
        and all(s[chosen]["mape"] < s[LAST_PRICE]["mape"] for s in supported),
    }
    checks["adopt"] = all(checks.values())
    return checks


def evaluate_stale_estimates(
    dataset: Path,
    output: Path,
    selection_start: datetime,
    *,
    min_gap_days: int = 30,
    min_examples: int = 30,
    seed: int = 0,
    max_mape: float = 0.03,
    max_p90_relative: float = 0.08,
) -> dict:
    if output.exists():
        raise ValueError("El directorio de salida debe ser nuevo")
    if selection_start.utcoffset() is None:
        raise ValueError("El inicio de la selección requiere zona horaria")
    manifest_bytes = (dataset / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    if manifest["features_version"] != FEATURES_VERSION:
        raise ValueError(f"El dataset no usa {FEATURES_VERSION}")
    raw = (dataset / manifest["dataset_file"]).read_bytes()
    if sha256(raw) != manifest["dataset_sha256"]:
        raise ValueError("El dataset no coincide con el hash de su manifiesto")

    frame = examples_frame([json.loads(line) for line in raw.splitlines()])
    selection_from = selection_start.astimezone(UTC)
    train = frame[frame.partition == "train"]
    fitting = train[train.target_at < selection_from]
    selecting = stale_examples(train[train.target_at >= selection_from], min_gap_days)
    validating = stale_examples(frame[frame.partition == "validation"], min_gap_days)
    if fitting.empty:
        raise ValueError("El inicio de la selección deja vacío el ajuste")
    if len(selecting) < min_examples:
        raise ValueError("Sin reingresos suficientes en el período de selección")
    if validating.empty:
        raise ValueError("Sin reingresos en la validación")

    selection_predictions, selection_fallbacks = _predictions(fitting, selecting, seed)
    selection = {name: _score(selecting, p) for name, p in selection_predictions.items()}
    chosen = min(selection, key=lambda name: (selection[name]["mape"], name))

    validation_predictions, validation_fallbacks = _predictions(train, validating, seed)
    buckets = pd.cut(validating.previous_age_days, BUCKET_EDGES, labels=BUCKETS, right=True)
    validation = {
        "overall": _group(validating, validation_predictions, min_examples),
        "segments": {
            label: _group(validating[buckets == label], validation_predictions, min_examples)
            for label in BUCKETS
        },
    }
    report = {
        "format_version": 1,
        "scope": "stale_price_estimate_retrospective",
        "runtime_enabled": False,
        "features_version": FEATURES_VERSION,
        "dataset_manifest_sha256": sha256(manifest_bytes),
        "dataset_sha256": manifest["dataset_sha256"],
        "source_sha256": manifest["source_sha256"],
        "parameters": {
            "selection_start_utc": selection_from.isoformat(),
            "min_gap_days": min_gap_days,
            "comparison": "strict_gt",
            "min_examples": min_examples,
            "seed": seed,
            "max_mape": max_mape,
            "max_p90_relative": max_p90_relative,
            "candidates": CANDIDATES,
        },
        "fallbacks": {"selection": selection_fallbacks, "validation": validation_fallbacks},
        "chosen_method": chosen,
        "selection": selection,
        "validation": validation,
        "adoption_check": _adoption(chosen, validation, max_mape, max_p90_relative),
        "code": code_provenance(),
        "limitations": (
            "Los reingresos pueden diferir de las estaciones que no vuelven a publicar; "
            "no mide el precio actual de estaciones sin publicación nueva."
        ),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".stale-evaluation-", dir=output.parent) as directory:
        staging = Path(directory)
        (staging / "stale-evaluation.json").write_bytes(encoded(report) + b"\n")
        staging.replace(output)
    return report
