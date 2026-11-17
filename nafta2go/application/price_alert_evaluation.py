"""Evalúa umbrales candidatos retrospectivos; no habilita alertas ni cambia rankings."""

import json
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from math import ceil, isfinite
from pathlib import Path
from tempfile import TemporaryDirectory

from nafta2go.application.price_dataset import code_provenance, encoded, sha256
from nafta2go.application.price_diagnostic import ASSUMPTION, METHODS, reference_price
from nafta2go.ml.temporal import FEATURES_VERSION


def _time(value):
    result = datetime.fromisoformat(value)
    if result.utcoffset() is None:
        raise ValueError("Se requiere zona horaria")
    return result


def evaluate_price_alerts(
    dataset: Path,
    model: Path,
    output: Path,
    audit_start: datetime,
    quantile: float,
    min_examples: int = 30,
):
    if (
        output.exists()
        or audit_start.utcoffset() is None
        or not isfinite(quantile)
        or not 0 < quantile < 1
        or type(min_examples) is not int
        or min_examples < 2
    ):
        raise ValueError("Parámetros inválidos")
    dataset_raw = (dataset / "manifest.json").read_bytes()
    model_raw = (model / "manifest.json").read_bytes()
    data, selection = json.loads(dataset_raw), json.loads(model_raw)
    if not (
        data["format_version"] == selection["format_version"] == 1
        and data["features_version"] == selection["features_version"] == FEATURES_VERSION
        and data["availability_assumption"] == selection["availability_assumption"] == ASSUMPTION
        and data["source"] == "historico"
        and data["dataset_file"] == "examples.jsonl"
        and selection["chosen_method"] in METHODS
        and selection["dataset_manifest_sha256"] == sha256(dataset_raw)
        and selection["dataset_sha256"] == data["dataset_sha256"]
        and selection["source_sha256"] == data["source_sha256"]
    ):
        raise ValueError("Manifiestos incompatibles")
    cutoff = _time(data["parameters"]["cutoff_utc"])
    if not _time(selection["parameters"]["selection_start_utc"]) < cutoff < audit_start:
        raise ValueError("Cortes temporales incompatibles")
    raw = (dataset / "examples.jsonl").read_bytes()
    if sha256(raw) != data["dataset_sha256"]:
        raise ValueError("Dataset incompatible")
    groups, seen = defaultdict(lambda: {"calibration": [], "audit": []}), set()
    for line in raw.splitlines():
        row = json.loads(line)
        when = _time(row["target_at_utc"])
        if row["source_row"] in seen:
            raise ValueError("Observación duplicada")
        seen.add(row["source_row"])
        if row["partition"] == "train" and when < cutoff:
            continue
        if row["partition"] != "validation" or when < cutoff:
            raise ValueError("Partición temporal incompatible")
        features = row["features"]
        value = reference_price(features, selection["chosen_method"])
        actual = Decimal(str(row["target_price_ars_per_l"]))
        if not (actual.is_finite() and value.is_finite() and actual > 0 and value > 0):
            raise ValueError("Precio inválido")
        # El denominador también está disponible al servir, sin usar el precio objetivo.
        score = float(abs(actual - value) / value)
        if not isfinite(score):
            raise ValueError("Desviación inválida")
        key = f"{features['product_id']}:{features['schedule_id']}"
        part = "calibration" if when < audit_start else "audit"
        groups[key][part].append(score)
    if (
        not groups
        or not any(g["calibration"] for g in groups.values())
        or not any(g["audit"] for g in groups.values())
    ):
        raise ValueError("El corte deja un período vacío")
    segments = {}
    for key, group in sorted(groups.items()):
        calibration, audit = sorted(group["calibration"]), group["audit"]
        enough = len(calibration) >= min_examples and len(audit) >= min_examples
        threshold = calibration[ceil(quantile * len(calibration)) - 1] if enough else None
        segments[key] = {
            "status": "candidate" if enough else "insufficient_support",
            "calibration_examples": len(calibration),
            "audit_examples": len(audit),
            "relative_deviation_threshold": threshold,
            "audit_exceedances": sum(s > threshold for s in audit) if enough else None,
            "audit_exceedance_rate": sum(s > threshold for s in audit) / len(audit)
            if enough
            else None,
        }
    report = {
        "format_version": 1,
        "scope": "published_price_retrospective",
        "runtime_enabled": False,
        "chosen_method": selection["chosen_method"],
        "features_version": FEATURES_VERSION,
        "availability_assumption": ASSUMPTION,
        "dataset_manifest_sha256": sha256(dataset_raw),
        "model_manifest_sha256": sha256(model_raw),
        "dataset_sha256": sha256(raw),
        "source_sha256": data["source_sha256"],
        "parameters": {
            "cutoff": cutoff.isoformat(),
            "audit_start": audit_start.isoformat(),
            "quantile": quantile,
            "min_examples": min_examples,
            "score": "abs(published-reference)/reference",
            "comparison": "strict_gt",
            "quantile_method": "nearest_rank",
        },
        "segments": segments,
        "code": code_provenance(),
        "limitations": "Sin etiquetas de errores: no mide precisión, recall ni confianza futura.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".price-alert-evaluation-", dir=output.parent) as directory:
        staging = Path(directory)
        (staging / "alert-evaluation.json").write_bytes(encoded(report) + b"\n")
        staging.replace(output)
    return report
