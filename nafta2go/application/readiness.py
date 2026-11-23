"""Readiness separa esquema disponible y cobertura de datos, sin usar rutas."""

from nafta2go.application.coverage_rules import configured_max_price_age_days
from nafta2go.application.scenario import load_scenario
from nafta2go.application.stored_query import select_candidates, select_stored_candidates
from nafta2go.persistence.database import database_is_ready


def data_readiness(engine, now):
    if not database_is_ready(engine):
        return {"usable": False, "data_status": "unavailable"}
    with engine.connect() as conn:
        current = select_stored_candidates(
            conn,
            fuel_type="super",
            schedule_id=2,
            reference_at=now,
            max_age_days=configured_max_price_age_days(),
        )
    if current.status.value == "ready":
        return {"usable": True, "data_status": "current"}
    scenario = load_scenario()
    historical = select_candidates(
        scenario.rows,
        fuel_type="super",
        schedule_id=2,
        reference_at=scenario.reference_at,
        max_age_days=configured_max_price_age_days(),
    )
    usable = historical.status.value == "ready"
    return {"usable": usable, "data_status": "historical_scenario" if usable else "unavailable"}
