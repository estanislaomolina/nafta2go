"""Referencia retrospectiva y política provisional, sin modificar el precio oficial."""

import hashlib
import json
import os
from datetime import UTC
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from nafta2go.domain.price_alert import provisional_alert
from nafta2go.ml import registry
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


def _manifest(directory, version):
    """Un almacén guarda cada versión en <sha256>/; una carpeta simple, en su raíz."""
    stored = Path(directory) / version / "manifest.json"
    return (stored if stored.is_file() else Path(directory) / "manifest.json").read_bytes()


def _selection():
    try:
        if any(
            not os.environ.get(key, "").strip()
            for key in ("NAFTA2GO_PRICE_DATASET_DIR", "NAFTA2GO_PRICE_MODEL_DIR")
        ):
            raise ValueError("Falta configuración")
        champion = registry.champion()
        if champion is None:
            raise ValueError("Sin campeón registrado")
        raw = _manifest(os.environ["NAFTA2GO_PRICE_MODEL_DIR"], champion["run"])
        model = json.loads(raw)
        # Solo se sirve la corrida del alias champion; promover o revertir cambia esta versión.
        if (
            hashlib.sha256(raw).hexdigest() != champion["run"]
            or model["chosen_method"] != champion["method"]
        ):
            raise ValueError("La selección configurada no es el campeón del registro")
        dataset_bytes = _manifest(
            os.environ["NAFTA2GO_PRICE_DATASET_DIR"], model["dataset_manifest_sha256"]
        )
        dataset = json.loads(dataset_bytes)
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
    with engine.connect() as conn:
        return price_diagnostic_on_connection(conn, station_id, product_id, schedule_id, now)


def price_diagnostic_on_connection(conn, station_id, product_id, schedule_id, now):
    return price_diagnostics_on_connection(conn, [station_id], product_id, schedule_id, now)[
        station_id
    ]


def price_diagnostics_on_connection(conn, station_ids, product_id, schedule_id, now):
    station_ids = tuple(dict.fromkeys(station_ids))
    if len(station_ids) > 20:
        raise ValueError("Se admiten hasta veinte publicaciones por lote")
    if not station_ids:
        return {}
    if now.utcoffset() is None:
        raise ValueError("La referencia requiere zona horaria")
    model, dataset, version = _selection()
    local_now = now.astimezone(ZoneInfo(LOCAL_TIMEZONE)).replace(tzinfo=None)
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
    targets = {
        station: repo.diagnostic_publication(
            conn, current, station, product_id, schedule_id, local_now
        )
        for station in station_ids
    }
    publications = [row for row in targets.values() if row is not None]
    if not publications:
        return targets
    history = repo.diagnostic_history(
        conn, historical, product_id, schedule_id, max(row["valid_from"] for row in publications)
    )
    examples, _ = build_temporal_dataset(
        history,
        now,
        targets=publications,
        window_days=dataset["parameters"]["window_days"],
        min_history=dataset["parameters"]["min_history"],
    )
    indexed = {(row["station_id"], row["target_at_utc"]): row for row in examples}
    result = {}
    for station, target in targets.items():
        if target is None:
            result[station] = None
            continue
        published = target["valid_from"].replace(tzinfo=ZoneInfo(LOCAL_TIMEZONE)).astimezone(UTC)
        example = indexed.get((station, published.isoformat()))
        result[station] = _present_diagnostic(
            target,
            example,
            station,
            product_id,
            schedule_id,
            published,
            model,
            version,
            current,
            historical,
            capture,
        )
    return result


def _present_diagnostic(
    target,
    example,
    station_id,
    product_id,
    schedule_id,
    published,
    model,
    version,
    current,
    historical,
    capture,
):
    value = reference_price(example["features"], model["chosen_method"]) if example else None
    alert = provisional_alert(target["price"], value, product_id, model["chosen_method"], version)
    return {
        **alert,
        "scope": "published_price_retrospective",
        "status": "reference_only" if value is not None else "unavailable",
        "station_id": station_id,
        "product_id": product_id,
        "schedule_id": schedule_id,
        "official_price_ars_per_l": str(target["price"]),
        "published_at": published.isoformat(),
        "reference_ars_per_l": str(value) if value is not None else None,
        "difference_ars_per_l": str(target["price"] - value) if value is not None else None,
        "reason": (
            "context_unavailable"
            if value is None
            else "provisional_policy"
            if alert["alert_policy_version"]
            else "alert_policy_not_validated"
        ),
        "method": model["chosen_method"],
        "version": version,
        "features_version": FEATURES_VERSION,
        "data_run_id": current,
        "history_run_id": historical,
        "history_sha256": capture["sha256"],
        "availability_assumption": ASSUMPTION,
    }
