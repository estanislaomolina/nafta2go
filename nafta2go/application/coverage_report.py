"""Reporte de cobertura de precios para una consulta, sin consultar rutas (POC-02)."""

from collections.abc import Callable
from datetime import datetime

from sqlalchemy import Connection

from nafta2go.adapters.routing import Point
from nafta2go.application import coverage_rules
from nafta2go.application.scenario import ScenarioPrices, load_scenario
from nafta2go.application.stored_query import (
    CandidateSelection,
    select_stored_candidates,
    select_with_coverage,
)

# Antigüedades que se reportan para ver qué tan lejos está el umbral.
REPORT_WINDOWS_DAYS = (7, 30, 90, 365)


def coverage_report(
    conn: Connection,
    origin: Point,
    destination: Point | None,
    *,
    fuel_type: str,
    schedule_id: int,
    reference_at: datetime,
    scenario_loader: Callable[[], ScenarioPrices] = load_scenario,
) -> dict:
    """Cobertura actual por antigüedad (CABA y corredor) y la decisión que tomaría la consulta."""
    query = {"fuel_type": fuel_type, "schedule_id": schedule_id, "reference_at": reference_at}
    windows = {}
    current = None
    for days in REPORT_WINDOWS_DAYS:
        window = {"max_age_days": days, "minimum_candidates": 1, **query}
        city = select_stored_candidates(conn, **window)
        corridor = select_stored_candidates(conn, origin=origin, destination=destination, **window)
        windows[str(days)] = {
            "caba": city.eligible_station_count,
            "corridor": corridor.eligible_station_count,
        }
        current = current or city

    decision = select_with_coverage(
        conn, origin, destination, scenario_loader=scenario_loader, **query
    )
    return {
        "reference_at": reference_at.isoformat(),
        "query": {
            "origin": _point(origin),
            "destination": _point(destination),
            "fuel_type": fuel_type,
            "schedule_id": schedule_id,
        },
        "parameters": {
            "max_price_age_days": coverage_rules.MAX_PRICE_AGE_DAYS,
            "min_recent_candidates": coverage_rules.MIN_RECENT_CANDIDATES,
            "max_detour_km": coverage_rules.MAX_DETOUR_KM,
        },
        "current": {
            "data_run_id": current.data_run_id,
            "status": decision.current.status.value,
            "eligible_in_corridor": decision.current.eligible_station_count,
            "stations_by_age_days": windows,
            "exclusions": decision.current.exclusions,
        },
        "historical": _historical(decision.historical),
        "decision": {
            "status": decision.status.value,
            "scenario": _scenario(decision.selection),
            "candidates": [
                {
                    "station_id": item.candidate.station_id,
                    "price_ars_per_l": str(item.candidate.price_ars_per_l),
                    "published_at_local": item.published_at_local.isoformat(),
                    "alerts": list(item.alerts),
                }
                for item in decision.selection.items
            ]
            if decision.status.value != "insufficient_coverage"
            else [],
        },
    }


def _point(point: Point | None) -> dict | None:
    return None if point is None else {"lat": point.lat, "lon": point.lon}


def _scenario(selection: CandidateSelection) -> dict | None:
    if selection.scenario is None:
        return None
    return {
        "scenario_id": selection.scenario.scenario_id,
        "reference_at": selection.scenario.reference_at.isoformat(),
        "extract_sha256": selection.scenario.extract_sha256,
        "source_sha256": selection.scenario.source_sha256,
    }


def _historical(selection: CandidateSelection | None) -> dict | None:
    if selection is None:
        return None
    return {
        "scenario_id": selection.scenario.scenario_id,
        "status": selection.status.value,
        "eligible_in_corridor": selection.eligible_station_count,
        "exclusions": selection.exclusions,
    }
