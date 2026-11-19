"""Auditoría de las recomendaciones guardadas: trazabilidad, frescura y privacidad (MVP-09).

Revisa lo que quedó persistido, no lo que el código intentó guardar: así detecta
regresiones, filas viejas o escrituras por fuera del repositorio. Cada criterio se
informa como cantidad y proporción, sin ocultar las filas que fallan.
"""

import re
from collections.abc import Iterable, Mapping
from datetime import datetime, timedelta

from nafta2go.application.coverage_rules import MAX_PRICE_AGE_DAYS
from nafta2go.application.stored_query import LOCAL_ZONE
from nafta2go.normalization.rules import CABA_BBOX

AUDIT_VERSION = "recommendation-audit-v2"
SHA256 = re.compile(r"[0-9a-f]{64}")
SCENARIO_KEYS = ("scenario_id", "reference_at", "extract_sha256", "source_sha256")
# Claves que indicarían ubicaciones (RNF03). Se comparan exactas para que nombres como
# `has_destination` no cuenten; lo guardado no incluye coordenadas, ni de estaciones.
LOCATION_KEYS = frozenset(
    {"origin", "destination", "origen", "destino", "lat", "lon", "lng", "latitude"}
    | {"longitude", "latitud", "longitud", "coordinates", "coordenadas"}
)
NUMBER_PAIR = re.compile(r"(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)")
MISSING = object()
MAPS_LINK = re.compile(r"google\.[a-z.]+/maps|maps\.app\.goo\.gl|maps\.google\.", re.IGNORECASE)


def traceability_failures(record: Mapping) -> list[str]:
    """Motivos por los que una recomendación no es trazable a datos, reglas y rutas (RNF05)."""
    failures = []
    result = record["result"]
    run_id, scenario = record["data_run_id"], record["scenario"]
    if (run_id is None) == (scenario is None):
        failures.append("origen_no_unico")
    elif run_id is not None and record.get("data_run_status") != "succeeded":
        failures.append("ingesta_no_exitosa")
    elif scenario is not None and not _valid_scenario(scenario):
        failures.append("escenario_incompleto")
    if result.get("data_run_id", MISSING) != run_id or result.get("scenario", MISSING) != scenario:
        failures.append("origen_inconsistente")
    if not _valid_max_age(result["query"]["max_price_age_days"]):
        failures.append("vigencia_fuera_de_rango")
    for key in ("engine_version", "routing_provider"):
        if not record[key] or result.get(key) != record[key]:
            failures.append(f"{key}_inconsistente")
    if any(row.get("source_row") is None for row in result.get("evaluations", [])):
        failures.append("precio_sin_fila_de_origen")
    routes = result.get("routes") or {}
    if routes.get("replayed") and not SHA256.fullmatch(str(routes.get("sha256"))):
        failures.append("matriz_reproducida_sin_hash")
    return failures


def stale_evaluations(record: Mapping) -> tuple[int, int]:
    """(evaluadas, fuera de vigencia): precios usados contra el umbral de la consulta (RF09).

    Un umbral guardado fuera de 1 a `MAX_PRICE_AGE_DAYS` no amplía la vigencia: se mide
    contra el máximo y la fila falla además en trazabilidad.
    """
    result = record["result"]
    evaluations = result.get("evaluations", [])
    stored = result["query"]["max_price_age_days"]
    max_age = timedelta(days=stored if _valid_max_age(stored) else MAX_PRICE_AGE_DAYS)
    reference = datetime.fromisoformat(result["price_reference_at"])
    stale = 0
    for row in evaluations:
        published = datetime.fromisoformat(row["published_at_local"]).replace(tzinfo=LOCAL_ZONE)
        if published > reference or reference - published > max_age:
            stale += 1
    return len(evaluations), stale


def privacy_failures(record: Mapping) -> list[str]:
    """Ubicaciones o enlaces de navegación persistidos en la consulta o el resultado (RNF03)."""
    failures = set()
    for part in ("request", "result", "scenario"):
        for key, value in _walk(record.get(part)):
            if (key is not None and key.lower() in LOCATION_KEYS) or _coordinates(value):
                failures.add(f"{part}_con_ubicacion")
            if isinstance(value, str) and MAPS_LINK.search(value):
                failures.add(f"{part}_con_enlace_de_mapas")
    return sorted(failures)


def audit_recommendations(records: Iterable[Mapping]) -> dict:
    """Recorre el historial una vez. Una fila sin los campos esperados (por ejemplo, de una
    versión anterior) falla en trazabilidad con su id y no corta la auditoría del resto."""
    failing = {"trazabilidad": {}, "frescura": {}, "privacidad": {}}
    total = evaluated = stale = current = historical = 0
    for record in records:
        total += 1
        current += record.get("data_run_id") is not None
        historical += record.get("scenario") is not None
        try:
            reasons = traceability_failures(record)
            count, outdated = stale_evaluations(record)
        except (KeyError, TypeError, ValueError, AttributeError):
            reasons, count, outdated = ["fila_incompleta"], 0, 0
        if reasons:
            failing["trazabilidad"][record["id"]] = reasons
        evaluated, stale = evaluated + count, stale + outdated
        if outdated:
            failing["frescura"][record["id"]] = outdated
        if reasons := privacy_failures(record):
            failing["privacidad"][record["id"]] = reasons
    return {
        "audit_version": AUDIT_VERSION,
        "recommendations": total,
        "origins": {"ingesta_vigente": current, "escenario_historico": historical},
        "trazabilidad": _share(total - len(failing["trazabilidad"]), total),
        "frescura": {**_share(evaluated - stale, evaluated), "unidad": "precios evaluados"},
        "privacidad": _share(total - len(failing["privacidad"]), total),
        "fallas": {name: {str(k): v for k, v in rows.items()} for name, rows in failing.items()},
    }


def _share(passing: int, total: int) -> dict:
    return {"cumplen": passing, "total": total, "proporcion": passing / total if total else None}


def _valid_max_age(days) -> bool:
    return type(days) is int and 1 <= days <= MAX_PRICE_AGE_DAYS


def _coordinates(value) -> bool:
    """Un par de números dentro del rectángulo de CABA, en lista o en texto."""
    if isinstance(value, list | tuple) and len(value) == 2:
        pairs = [value]
    elif isinstance(value, str):
        pairs = NUMBER_PAIR.findall(value)
    else:
        return False
    return any(_inside_caba(*pair) or _inside_caba(*reversed(pair)) for pair in pairs)


def _inside_caba(lat, lon) -> bool:
    try:
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        return False
    return (
        CABA_BBOX["lat_min"] <= lat <= CABA_BBOX["lat_max"]
        and CABA_BBOX["lon_min"] <= lon <= CABA_BBOX["lon_max"]
    )


def _valid_scenario(scenario: Mapping) -> bool:
    if set(scenario) != set(SCENARIO_KEYS) or not str(scenario["scenario_id"]).strip():
        return False
    try:
        if datetime.fromisoformat(str(scenario["reference_at"])).utcoffset() is None:
            return False
    except ValueError:
        return False
    return all(SHA256.fullmatch(str(scenario[key])) for key in SCENARIO_KEYS[2:])


def _walk(value, key=None):
    yield key, value
    if isinstance(value, Mapping):
        for child_key, child in value.items():
            yield from _walk(child, str(child_key))
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)
