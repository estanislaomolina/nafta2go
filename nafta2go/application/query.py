"""Consulta explicada, ranking y registro sin ubicaciones del usuario."""

from dataclasses import asdict
from datetime import UTC, datetime

from sqlalchemy import Connection, Engine

from nafta2go.adapters.routing import Point, RoutingProvider
from nafta2go.application.coverage_rules import configured_max_price_age_days
from nafta2go.application.recommendation import DEFAULT_CANDIDATE_LIMIT
from nafta2go.application.scenario import load_scenario
from nafta2go.application.stale_price_estimate import (
    ESTIMATE_VERSION,
    EVIDENCE,
    MAX_AGE_DAYS,
    METHOD,
    MIN_AGE_DAYS,
    estimate_stale_prices,
)
from nafta2go.application.stored_query import CoverageStatus, evaluate_with_coverage
from nafta2go.domain.engine import FuelRequest
from nafta2go.domain.ranking import rank_alternatives
from nafta2go.normalization.rules import CABA_BBOX
from nafta2go.persistence import repository as repo

ENGINE_VERSION = "mvp-02-v2"
SOURCE = {
    "name": "Secretaría de Energía — Precios en surtidor",
    "url": "https://datos.energia.gob.ar/dataset/precios-en-surtidor",
    "license": "CC-BY-4.0",
}
ESTIMATE_NOTICE = (
    "Estimación a partir de precios recientes de la misma bandera: no es un precio oficial, "
    "no renueva su vigencia ni participa del ranking. Un presupuesto calculado con ella no "
    "garantiza el importe en el surtidor."
)


def recommend_from_database(
    engine: Engine,
    request: FuelRequest,
    origin: Point,
    destination: Point | None,
    provider: RoutingProvider,
    **options,
) -> dict:
    """Límite transaccional para entradas que no administran una conexión."""
    with engine.begin() as conn:
        return recommend(conn, request, origin, destination, provider, **options)


def recommend(
    conn: Connection,
    request: FuelRequest,
    origin: Point,
    destination: Point | None,
    provider: RoutingProvider,
    *,
    fuel_type: str,
    schedule_id: int,
    reference_at: datetime,
    routing_provider: str,
    max_candidates: int = DEFAULT_CANDIDATE_LIMIT,
    scenario_loader=load_scenario,
) -> dict:
    max_age_days = configured_max_price_age_days()
    for name, point in (("origin", origin), ("destination", destination)):
        if point is not None and not (
            CABA_BBOX["lat_min"] <= point.lat <= CABA_BBOX["lat_max"]
            and CABA_BBOX["lon_min"] <= point.lon <= CABA_BBOX["lon_max"]
        ):
            raise ValueError(f"{name}: fuera del área de servicio de CABA")
    result = evaluate_with_coverage(
        conn,
        request,
        origin,
        destination,
        provider,
        fuel_type=fuel_type,
        schedule_id=schedule_id,
        reference_at=reference_at,
        limit=max_candidates,
        max_age_days=max_age_days,
        scenario_loader=scenario_loader,
    )
    selection = result.selection
    scenario = asdict(selection.scenario) if selection.scenario is not None else None
    if scenario is not None:
        scenario["reference_at"] = scenario["reference_at"].isoformat()
    rows = {item.candidate.station_id: item for item in selection.items}
    evaluations = {item.candidate.station_id: item.evaluation for item in result.evaluations}
    choices = rank_alternatives(evaluations)
    parameters = {
        **{key: str(value) for key, value in asdict(request).items()},
        "fuel_type": fuel_type,
        "schedule_id": schedule_id,
        "max_candidates": max_candidates,
        "max_price_age_days": max_age_days,
    }
    capture = (
        repo.raw_capture_for_run(conn, selection.data_run_id)
        if selection.data_run_id is not None
        else None
    )
    stale_block, stale_locations = _stale_estimates(
        conn,
        result.current.data_run_id,
        fuel_type=fuel_type,
        schedule_id=schedule_id,
        reference_at=reference_at,
        origin=origin,
        destination=destination,
        max_age_days=max_age_days,
        limit=max_candidates,
    )
    payload = {
        "stale_price_estimates": stale_block,
        "status": result.status.value,
        "outcome": (
            "insufficient_coverage"
            if result.status == CoverageStatus.INSUFFICIENT_COVERAGE
            else "recommended"
            if choices
            else "no_feasible_stations"
        ),
        "query": {**parameters, "reference_at": reference_at.isoformat()},
        "price_reference_at": selection.reference_at.isoformat(),
        "source": {**SOURCE, "sha256": capture["sha256"] if capture else None},
        "data_run_id": selection.data_run_id,
        "scenario": scenario,
        "current_eligible_count": result.current.eligible_station_count,
        "selected_eligible_count": selection.eligible_station_count,
        "exclusions": selection.exclusions,
        "routing_provider": routing_provider,
        "engine_version": ENGINE_VERSION,
        "routes": (
            {
                "replayed": routing_provider == "openrouteservice-recorded",
                "cache_hit": getattr(provider, "cache_hit", False),
                "captured_at_utc": provider.evidence["captured_at_utc"],
                "sha256": provider.sha256,
            }
            if getattr(provider, "evidence", None) is not None and evaluations
            else None
        ),
        "alternatives": [asdict(choice) for choice in choices],
        "evaluations": [
            {
                "station_id": station_id,
                "company": rows[station_id].company,
                "brand": rows[station_id].brand,
                "address": rows[station_id].address,
                "price_ars_per_l": str(rows[station_id].candidate.price_ars_per_l),
                "published_at_local": rows[station_id].published_at_local.isoformat(),
                "source_row": rows[station_id].source_row,
                "price_id": rows[station_id].price_id,
                "alerts": list(rows[station_id].alerts),
                "feasible": evaluation.feasible,
                "reasons": [reason.value for reason in evaluation.reasons],
                "metrics": (
                    {key: str(value) for key, value in asdict(evaluation.metrics).items()}
                    if evaluation.metrics is not None
                    else None
                ),
            }
            for station_id, evaluation in evaluations.items()
        ],
    }
    # Sin cobertura no hay recomendación que persistir. Nunca se guardan ubicaciones.
    payload["recommendation_id"] = None
    if result.status != CoverageStatus.INSUFFICIENT_COVERAGE:
        payload["recommendation_id"] = repo.record_recommendation(
            conn,
            selection.data_run_id,
            ENGINE_VERSION,
            routing_provider,
            parameters,
            payload,
            datetime.now(UTC).replace(tzinfo=None),
            scenario=scenario,
        )
    # Coordenadas públicas de las estaciones elegidas, solo para la presentación.
    # Se agregan después de persistir: nunca incluyen el origen ni el destino del viaje.
    payload["navigation_destinations"] = {
        choice.station_id: asdict(rows[choice.station_id].candidate.location) for choice in choices
    }
    payload["stale_navigation_destinations"] = stale_locations
    return payload


def _stale_estimates(
    conn: Connection, run_id: int | None, *, max_age_days: int, **options
) -> tuple[dict, dict]:
    """Estimaciones de ADR-020 sobre la ingesta vigente, aparte de la recomendación.

    Devuelve el bloque que se persiste y, por separado, las coordenadas públicas de esas
    estaciones para la navegación, que se agregan recién después de persistir."""
    items = (
        estimate_stale_prices(
            repo.prices_for_run(conn, run_id), max_age_days=max_age_days, **options
        )
        if run_id is not None
        else ()
    )
    block = {
        "status": "available" if run_id is not None else "no_current_data",
        "data_run_id": run_id,
        "method": METHOD,
        "version": ESTIMATE_VERSION,
        "evidence": EVIDENCE,
        "min_age_days": max(MIN_AGE_DAYS, max_age_days),
        "max_age_days": MAX_AGE_DAYS,
        "notice": ESTIMATE_NOTICE,
        "items": [
            {
                **{key: str(value) for key, value in asdict(item).items() if key != "location"},
                "official_published_at_local": item.official_published_at_local.isoformat(),
                "official_age_days": item.official_age_days,
                "reference_from_local": item.reference_from_local.isoformat(),
                "reference_to_local": item.reference_to_local.isoformat(),
                "reference_count": item.reference_count,
            }
            for item in items
        ],
    }
    locations = {item.station_id: asdict(item.location) for item in items if item.location}
    return block, locations
