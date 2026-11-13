"""Preparación offline trazable desde una ingesta histórica ya normalizada."""

import hashlib
import json
import platform
import subprocess
from datetime import UTC
from importlib.metadata import version
from pathlib import Path
from tempfile import TemporaryDirectory
from zoneinfo import ZoneInfo

from nafta2go.ml.temporal import FEATURES_VERSION, build_temporal_dataset
from nafta2go.normalization.rules import LOCAL_TIMEZONE
from nafta2go.persistence import repository as repo
from nafta2go.persistence.database import ROOT

INPUT_COLUMNS = (
    "source_row",
    "station_id",
    "product_id",
    "schedule_id",
    "valid_from",
    "price",
    "lat",
    "lon",
    "brand",
)


def encoded(value):
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, allow_nan=False, default=str
    ).encode()


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def code_provenance():
    files = sorted((ROOT / "nafta2go").rglob("*.py")) + [ROOT / "requirements.txt"]
    hashes = {str(path.relative_to(ROOT)): sha256(path.read_bytes()) for path in files}
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True, check=True
        ).stdout.strip()
        dirty = (
            subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=True,
            ).stdout
            != ""
        )
    except (OSError, subprocess.SubprocessError):
        # La imagen de ejecución no incluye git; el hash de archivos sigue siendo obligatorio.
        commit, dirty = None, None
    return {"git_commit": commit, "git_dirty": dirty, "files_sha256": sha256(encoded(hashes))}


def prepare_price_dataset(engine, output: Path, cutoff, *, window_days=30, min_history=5):
    if output.exists():
        raise ValueError("El directorio de salida debe ser nuevo")
    with engine.connect() as conn:
        run_id = repo.latest_successful_run(conn, "historico")
        if run_id is None:
            raise ValueError("Se requiere una ingesta histórica exitosa")
        run = repo.get_run(conn, run_id)
        capture = repo.raw_capture_for_run(conn, run_id)
        if capture is None:
            raise ValueError("La ingesta debe conservar metadatos de captura")
        rows = repo.prices_for_run(conn, run_id)
    examples, report = build_temporal_dataset(
        rows, cutoff, window_days=window_days, min_history=min_history
    )
    if any(report["partitions"][part]["examples"] == 0 for part in ("train", "validation")):
        raise ValueError("El corte requiere ejemplos utilizables en ambas particiones")
    dataset = b"".join(encoded(row) + b"\n" for row in examples)
    normalized = [
        {key: row[key] for key in INPUT_COLUMNS}
        for row in sorted(rows, key=lambda r: r["source_row"])
    ]
    manifest = {
        "format_version": 1,
        "features_version": FEATURES_VERSION,
        "source": "historico",
        "ingestion_run_id": run_id,
        "source_sha256": capture["sha256"],
        "source_size_bytes": capture["size_bytes"],
        "capture_fetched_at_utc": capture["fetched_at"]
        .replace(tzinfo=ZoneInfo(LOCAL_TIMEZONE))
        .astimezone(UTC)
        .isoformat(),
        "normalization_rules_version": run["rules_version"],
        "normalized_rows": len(rows),
        "normalized_input_sha256": sha256(encoded(normalized)),
        "dataset_sha256": sha256(dataset),
        "dataset_file": "examples.jsonl",
        "parameters": {
            "cutoff_utc": cutoff.astimezone(UTC).isoformat(),
            "window_days": window_days,
            "min_history": min_history,
        },
        "code": code_provenance(),
        "environment": {
            "python": platform.python_version(),
            "sqlalchemy": version("sqlalchemy"),
            "tzdata": version("tzdata"),
        },
        "availability_assumption": "valid_from_proxy_retrospective_not_verified",
        "model_trained": False,
        "random_seed": None,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".price-dataset-", dir=output.parent) as temporary:
        staging = Path(temporary)
        (staging / "examples.jsonl").write_bytes(dataset)
        (staging / "manifest.json").write_bytes(encoded(manifest) + b"\n")
        (staging / "baseline-report.json").write_bytes(encoded(report) + b"\n")
        staging.replace(output)
    return {"manifest": manifest, "baseline": report}
