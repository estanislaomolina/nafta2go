"""Tests de la carga del escenario histórico congelado."""

import shutil
from datetime import UTC

import pytest
from sqlalchemy import func, select

from nafta2go.application.coverage_rules import (
    HISTORICAL_SCENARIO_DIR,
    HISTORICAL_SCENARIO_ID,
    HISTORICAL_SCENARIO_REFERENCE_AT,
)
from nafta2go.application.scenario import ScenarioIntegrityError, load_scenario
from nafta2go.persistence.schema import ingestion_runs


def test_loads_the_frozen_capture():
    scenario = load_scenario()
    assert scenario.scenario_id == HISTORICAL_SCENARIO_ID
    assert scenario.reference_at == HISTORICAL_SCENARIO_REFERENCE_AT
    assert len(scenario.rows) == 732
    assert len({row["station_id"] for row in scenario.rows}) == 184


def test_rows_have_the_station_prices_shape_without_database_id():
    row = load_scenario().rows[0]
    assert row["id"] is None
    assert {"station_id", "product_id", "fuel_type", "schedule_id", "price", "valid_from"} <= set(
        row
    )
    assert {"lat", "lon", "source_row", "alerts"} <= set(row)


def test_no_price_is_published_after_the_reference():
    scenario = load_scenario()
    local_reference = scenario.reference_at.replace(tzinfo=None)
    assert max(row["valid_from"] for row in scenario.rows) <= local_reference


def test_tampered_extract_is_rejected(tmp_path):
    copy = tmp_path / "escenario"
    shutil.copytree(HISTORICAL_SCENARIO_DIR, copy)
    extract = copy / "precios_caba_nafta.csv"
    # Un byte de más alcanza: el recorte ya no es el congelado.
    extract.write_bytes(extract.read_bytes() + b"\n")
    with pytest.raises(ScenarioIntegrityError, match="SHA-256"):
        load_scenario(copy)


def test_loading_does_not_create_ingestions(engine):
    load_scenario()
    with engine.connect() as conn:
        assert conn.execute(select(func.count()).select_from(ingestion_runs)).scalar() == 0


def test_reference_is_in_argentine_time():
    assert load_scenario().reference_at.astimezone(UTC).hour == 21
