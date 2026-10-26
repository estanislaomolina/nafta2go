"""Consulta final contra SQLite migrado: sin rutas reales ni red en los tests."""

import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from nafta2go.adapters.routing import DistanceMatrix, Point, ProviderTimeout
from nafta2go.application.query import recommend
from nafta2go.application.scenario import ScenarioPrices, load_scenario
from nafta2go.domain.engine import FuelRequest
from nafta2go.persistence import repository as repo
from nafta2go.persistence.schema import ingestion_runs, recommendations

ORIGIN = Point(-34.6037, -58.3816)
DESTINATION = Point(-34.5627, -58.4565)
REFERENCE = datetime(2026, 10, 26, 12, tzinfo=UTC)
REQUEST = FuelRequest(10, 50, 10, 12000, 2)


class Routes:
    def __init__(self, missing=False):
        self.calls = 0
        self.missing = missing

    def matrix(self, sources, destinations):
        self.calls += 1
        n = len(sources)
        value = None if self.missing else 1000.0
        return DistanceMatrix(
            [[value] * n for _ in sources],
            [[value] * n for _ in sources],
            list(sources),
            list(destinations),
        )


def query(engine, provider=None, **kwargs):
    with engine.begin() as conn:
        return recommend(
            conn,
            REQUEST,
            ORIGIN,
            DESTINATION,
            provider or Routes(),
            fuel_type="super",
            schedule_id=2,
            reference_at=REFERENCE,
            routing_provider="fake-for-tests",
            **kwargs,
        )


def test_real_normalizer_scenario_to_recorded_recommendation(engine):
    result = query(engine)
    assert result["status"] == "historical_scenario"
    assert result["outcome"] == "recommended"
    assert len(result["evaluations"]) == 10
    assert 1 <= len(result["alternatives"]) <= 3
    assert {p for row in result["alternatives"] for p in row["priorities"]} == {
        "combustible_neto",
        "menor_desvio",
        "equilibrio",
    }
    assert result["evaluations"][0]["address"]
    for row in result["evaluations"]:
        assert Decimal(row["metrics"]["cost_ars"]) <= REQUEST.budget_ars
        assert Decimal(row["metrics"]["final_l"]) >= REQUEST.reserve_l
    with engine.connect() as conn:
        record = repo.get_recommendation(conn, result["recommendation_id"])
        assert record["data_run_id"] is None
        assert record["scenario"]["source_sha256"] == load_scenario().source_sha256
        assert conn.execute(select(func.count()).select_from(ingestion_runs)).scalar() == 0
        assert not {"origin", "destination", "lat", "lon"} & set(record["request"])
        encoded = json.dumps(record, default=str)
        assert str(ORIGIN.lat) not in encoded and str(DESTINATION.lon) not in encoded


def test_successful_ingestion_is_used_and_recorded(engine):
    # Ingiere las filas ya normalizadas del escenario como fixture de una captura de prueba.
    rows = load_scenario().rows
    from nafta2go.persistence.schema import station_prices

    with engine.begin() as conn:
        run_id = repo.start_run(conn, "vigente", REFERENCE.replace(tzinfo=None))
        conn.execute(station_prices.insert(), [{**r, "id": None, "run_id": run_id} for r in rows])
        repo.finish_run(conn, run_id, "succeeded", REFERENCE.replace(tzinfo=None))
    result = query(engine)
    assert result["status"] == "ready"
    assert result["scenario"] is None
    with engine.connect() as conn:
        assert repo.get_recommendation(conn, result["recommendation_id"])["data_run_id"] == run_id


def test_without_coverage_no_api_and_no_recommendation(engine):
    provider = Routes()
    empty = ScenarioPrices("empty", REFERENCE, "a" * 64, "b" * 64, ())
    result = query(engine, provider, scenario_loader=lambda: empty)
    assert result["outcome"] == "insufficient_coverage"
    assert result["recommendation_id"] is None
    assert provider.calls == 0


def test_missing_routes_never_produce_a_winner(engine):
    result = query(engine, Routes(missing=True))
    assert result["outcome"] == "no_feasible_stations"
    assert result["alternatives"] == []
    assert all(r["reasons"] == ["route_unavailable"] for r in result["evaluations"])


def test_timeout_is_propagated_without_writing_a_recommendation(engine):
    class Failing:
        def matrix(self, sources, destinations):
            raise ProviderTimeout("timeout de prueba")

    with pytest.raises(ProviderTimeout):
        query(engine, Failing())
    with engine.connect() as conn:
        assert conn.execute(select(func.count()).select_from(recommendations)).scalar() == 0


@pytest.mark.parametrize("scenario", [None, {}, {"scenario_id": "sin hashes"}])
def test_untraceable_scenario_is_rejected(engine, scenario):
    with pytest.raises(ValueError, match="scenario"), engine.begin() as conn:
        repo.record_recommendation(conn, None, "test", "fake", {}, {}, REFERENCE, scenario=scenario)
