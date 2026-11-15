"""Comparación reproducible de modelos sobre un dataset preparado por `nafta2go.ml`."""

import json
import platform
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from tempfile import TemporaryDirectory

import joblib

from nafta2go.application.price_dataset import code_provenance, encoded, sha256
from nafta2go.ml.models import (
    CANDIDATES,
    REFERENCES,
    THREADS,
    build_model,
    error_analysis,
    examples_frame,
    fit,
    metrics,
    predict,
    reference_predictions,
)


def train_price_models(dataset: Path, output: Path, selection_start: datetime, seed: int = 0):
    """Elige método con un período interno de train y lo compara en la validación reservada.

    La validación del dataset no participa de la elección: todos los métodos se miden
    ahí solo después de elegir, para reportarlos sin ajustar nada con esos datos.
    """
    if output.exists():
        raise ValueError("El directorio de salida debe ser nuevo")
    if selection_start.utcoffset() is None:
        raise ValueError("El inicio de la selección requiere zona horaria")
    manifest_bytes = (dataset / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    raw = (dataset / manifest["dataset_file"]).read_bytes()
    if sha256(raw) != manifest["dataset_sha256"]:
        raise ValueError("El dataset no coincide con el hash de su manifiesto")
    frame = examples_frame([json.loads(line) for line in raw.splitlines()])
    train = frame[frame.partition == "train"]
    validation = frame[frame.partition == "validation"]
    selection_from = selection_start.astimezone(UTC)
    fitting = train[train.target_at < selection_from]
    selecting = train[train.target_at >= selection_from]
    if fitting.empty or selecting.empty or validation.empty:
        raise ValueError("El corte de selección deja una partición vacía")

    selection = _score_all(fitting, selecting, seed)[0]
    chosen = min(selection, key=lambda name: selection[name]["mae_ars_per_l"])
    best_model = min(CANDIDATES, key=lambda name: selection[name]["mae_ars_per_l"])
    validation_scores, models, predictions = _score_all(train, validation, seed)

    analysed = dict.fromkeys([chosen, best_model, "ultimo_precio"])
    report = {
        "selection_period_start_utc": selection_from.isoformat(),
        "chosen_method": chosen,
        "chosen_is_model": chosen in CANDIDATES,
        "best_model": best_model,
        "selection": selection,
        "validation": validation_scores,
        "validation_error_analysis": {
            name: error_analysis(validation, predictions[name]) for name in analysed
        },
    }
    predicted = predictions[best_model]
    prediction_lines = b"".join(
        encoded({"source_row": int(row), "predicted_target": float(value)}) + b"\n"
        for row, value in zip(validation.source_row, predicted, strict=True)
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".price-model-", dir=output.parent) as temporary:
        staging = Path(temporary)
        joblib.dump(models[best_model], staging / "model.joblib")
        (staging / "validation-predictions.jsonl").write_bytes(prediction_lines)
        model_manifest = {
            "format_version": 1,
            "dataset_manifest_sha256": sha256(manifest_bytes),
            "dataset_sha256": manifest["dataset_sha256"],
            "features_version": manifest["features_version"],
            "source_sha256": manifest["source_sha256"],
            "availability_assumption": manifest["availability_assumption"],
            "parameters": {
                "selection_start_utc": selection_from.isoformat(),
                "random_seed": seed,
                "candidates": CANDIDATES,
                "references": list(REFERENCES),
                "threads": THREADS,
            },
            "chosen_method": chosen,
            "artifact_model": best_model,
            "artifact_file": "model.joblib",
            "artifact_sha256": sha256((staging / "model.joblib").read_bytes()),
            "validation_predictions_file": "validation-predictions.jsonl",
            "validation_predictions_sha256": sha256(prediction_lines),
            "code": code_provenance(),
            "environment": {
                "python": platform.python_version(),
                "scikit-learn": version("scikit-learn"),
                "numpy": version("numpy"),
                "pandas": version("pandas"),
            },
        }
        (staging / "manifest.json").write_bytes(encoded(model_manifest) + b"\n")
        (staging / "model-report.json").write_bytes(encoded(report) + b"\n")
        staging.replace(output)
    return {"manifest": model_manifest, "report": report}


def _score_all(fitting, evaluating, seed):
    scores, models, predictions = {}, {}, {}
    for name, predicted in reference_predictions(evaluating).items():
        predictions[name], scores[name] = predicted, metrics(evaluating, predicted)
    for name in CANDIDATES:
        models[name] = fit(build_model(name, seed), fitting)
        predictions[name] = predict(models[name], evaluating)
        scores[name] = metrics(evaluating, predictions[name])
    return scores, models, predictions
