"""Consulta final contra SQLite migrado: sin rutas reales ni red en los tests."""

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from nafta2go.adapters.recorded_routes import CapturedRoutes
from nafta2go.adapters.route_cache import RouteCache
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


@pytest.mark.parametrize("use_current", [False, True])
def test_requested_limit_is_applied_and_recorded_for_both_data_sources(engine, use_current):
    if use_current:
        from nafta2go.persistence.schema import station_prices

        with engine.begin() as conn:
            run_id = repo.start_run(conn, "vigente", REFERENCE.replace(tzinfo=None))
            conn.execute(
                station_prices.insert(),
                [{**row, "id": None, "run_id": run_id} for row in load_scenario().rows],
            )
            repo.finish_run(conn, run_id, "succeeded", REFERENCE.replace(tzinfo=None))
    provider = Routes()
    result = query(engine, provider, max_candidates=20)
    assert (
        len(result["evaluations"]) == 16
    )  # Todas las elegibles de la fixture, sin inventar cuatro.
    assert result["query"]["max_candidates"] == 20
    assert result["engine_version"] == "mvp-02-v2"
    assert provider.calls == 1
    with engine.connect() as conn:
        record = repo.get_recommendation(conn, result["recommendation_id"])
    assert record["request"]["max_candidates"] == 20


@pytest.mark.parametrize("limit", [0, 2, 21, True, 3.5])
def test_invalid_candidate_limit_does_not_call_routes(engine, limit):
    provider = Routes()
    with pytest.raises(ValueError):
        query(engine, provider, max_candidates=limit)
    assert provider.calls == 0


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


def test_cache_reduces_calls_without_caching_prices_or_recommendations(engine, monkeypatch):
    class Client(Routes):
        matrix_url = "https://proveedor.invalid/matrix/driving-car"
        credential_scope = b"credencial-de-prueba"

        def close(self):
            pass

    client = Client()
    monkeypatch.setattr("nafta2go.adapters.recorded_routes.client_from_env", lambda: client)
    cache = RouteCache()
    baseline = query(engine, Routes())
    first = query(engine, CapturedRoutes(cache))
    second = query(engine, CapturedRoutes(cache))
    assert baseline["evaluations"] == first["evaluations"] == second["evaluations"]
    assert baseline["alternatives"] == first["alternatives"] == second["alternatives"]
    assert second["routes"]["cache_hit"] and client.calls == 1

    from nafta2go.persistence.schema import station_prices

    with engine.begin() as conn:
        run_id = repo.start_run(conn, "vigente", REFERENCE.replace(tzinfo=None))
        conn.execute(
            station_prices.insert(),
            [
                {**row, "id": None, "run_id": run_id, "price": row["price"] * 2}
                for row in load_scenario().rows
            ],
        )
        repo.finish_run(conn, run_id, "succeeded", REFERENCE.replace(tzinfo=None))
    changed = query(engine, CapturedRoutes(cache))
    assert client.calls == 1 and changed["routes"]["cache_hit"]
    assert changed["data_run_id"] == run_id
    assert (
        changed["evaluations"][0]["price_ars_per_l"] != first["evaluations"][0]["price_ars_per_l"]
    )


@pytest.mark.parametrize("current", [False, True])
def test_configured_age_boundary_is_applied_and_saved_for_both_sources(
    engine, monkeypatch, current
):
    from datetime import timedelta
    from zoneinfo import ZoneInfo

    from nafta2go.persistence.schema import station_prices

    monkeypatch.setenv("NAFTA2GO_MAX_PRICE_AGE_DAYS", "14")
    base = next(
        row for row in load_scenario().rows if row["product_id"] == 2 and row["schedule_id"] == 2
    )
    local = REFERENCE.astimezone(ZoneInfo("America/Argentina/Buenos_Aires")).replace(tzinfo=None)
    ages = (
        timedelta(days=14),
        timedelta(days=14, microseconds=1),
        timedelta(days=13),
        timedelta(days=12),
    )
    rows = tuple(
        {
            **base,
            "id": None,
            "station_id": 100 + index,
            "source_row": 100 + index,
            "valid_from": local - age,
            "lat": -34.60,
            "lon": -58.40,
        }
        for index, age in enumerate(ages)
    )
    scenario = ScenarioPrices("synthetic-vigencia", REFERENCE, "a" * 64, "b" * 64, rows)
    if current:
        with engine.begin() as conn:
            run_id = repo.start_run(conn, "vigente", REFERENCE.replace(tzinfo=None))
            conn.execute(station_prices.insert(), [{**row, "run_id": run_id} for row in rows])
            repo.finish_run(conn, run_id, "succeeded", REFERENCE.replace(tzinfo=None))
    result = query(engine, scenario_loader=lambda: scenario)
    assert result["status"] == ("ready" if current else "historical_scenario")
    assert {row["station_id"] for row in result["evaluations"]} == {"100", "102", "103"}
    assert result["exclusions"]["stale_price"] == 1
    assert result["query"]["max_price_age_days"] == 14
    with engine.connect() as conn:
        saved = repo.get_recommendation(conn, result["recommendation_id"])
    assert (
        saved["request"]["max_price_age_days"]
        == saved["result"]["query"]["max_price_age_days"]
        == 14
    )
    monkeypatch.setenv("NAFTA2GO_MAX_PRICE_AGE_DAYS", "1")
    provider = Routes()
    tighter = query(engine, provider, scenario_loader=lambda: scenario)
    assert tighter["outcome"] == "insufficient_coverage" and provider.calls == 0


def test_stricter_policy_can_abstain_on_the_real_frozen_scenario(engine, monkeypatch):
    monkeypatch.setenv("NAFTA2GO_MAX_PRICE_AGE_DAYS", "14")
    provider = Routes()
    result = query(engine, provider)
    assert result["outcome"] == "insufficient_coverage"
    assert result["selected_eligible_count"] == 1
    assert result["recommendation_id"] is None and provider.calls == 0


def stale_fixture_rows():
    local = REFERENCE.astimezone(load_scenario().reference_at.tzinfo).replace(tzinfo=None)
    base = {
        "company": "EMPRESA",
        "brand": "YPF",
        "address": "CALLE",
        "product_id": 2,
        "fuel_type": "super",
        "schedule_id": 2,
        "lat": -34.6040,
        "lon": -58.3850,
        "valid_from_raw": "x",
        "price_raw": "x",
        "alerts": "",
    }
    stale = {**base, "source_row": 1, "station_id": 501, "price": Decimal("1500")}
    stale["valid_from"] = local - timedelta(days=45)
    recent = {**base, "source_row": 2, "station_id": 502, "price": Decimal("1700")}
    recent["valid_from"] = local - timedelta(days=1)
    return [stale, recent]


def put_current(engine, rows):
    from nafta2go.persistence.schema import station_prices

    with engine.begin() as conn:
        run_id = repo.start_run(conn, "vigente", REFERENCE.replace(tzinfo=None))
        conn.execute(station_prices.insert(), [{**r, "id": None, "run_id": run_id} for r in rows])
        repo.finish_run(conn, run_id, "succeeded", REFERENCE.replace(tzinfo=None))
    return run_id


def test_stale_estimates_are_reported_apart_from_the_ranking_and_recorded(engine):
    run_id = put_current(engine, stale_fixture_rows())
    result = query(engine)
    estimates = result["stale_price_estimates"]
    assert estimates["status"] == "available"
    assert estimates["data_run_id"] == run_id
    assert (estimates["min_age_days"], estimates["max_age_days"]) == (30, 120)
    assert estimates["method"] == "bandera_reciente"
    assert "no es un precio oficial" in estimates["notice"]
    (item,) = estimates["items"]
    assert item["station_id"] == "501"
    assert item["official_price_ars_per_l"] == "1500.000"
    assert item["estimate_ars_per_l"] == "1700.000"
    assert item["official_age_days"] == 45
    assert item["reference_count"] == 1
    ranked = {row["station_id"] for row in result["alternatives"] + result["evaluations"]}
    assert "501" not in ranked
    with engine.connect() as conn:
        record = repo.get_recommendation(conn, result["recommendation_id"])
    assert record["result"]["stale_price_estimates"]["items"][0]["station_id"] == "501"
    assert "location" not in item and "navigation" not in item
    assert "lat" not in json.dumps(record["result"]["stale_price_estimates"])
    assert set(result["stale_navigation_destinations"]) == {"501"}


def test_without_current_ingestion_estimates_are_not_available(engine):
    result = query(engine)
    assert result["stale_price_estimates"] == {
        **result["stale_price_estimates"],
        "status": "no_current_data",
        "data_run_id": None,
        "items": [],
    }


@pytest.mark.parametrize(
    "mode", ["some", "all", "unknown", "unavailable", "mismatch", "incompatible"]
)
def test_conservative_uses_existing_routes_and_persists_trace(engine, monkeypatch, mode):
    from nafta2go.application.price_diagnostic import DiagnosticUnavailable
    from nafta2go.domain.price_alert import AUDITED_MODEL_VERSIONS
    from nafta2go.persistence.schema import station_prices

    prices = load_scenario().rows
    with engine.begin() as conn:
        run_id = repo.start_run(conn, "vigente", REFERENCE.replace(tzinfo=None))
        conn.execute(station_prices.insert(), [{**r, "id": None, "run_id": run_id} for r in prices])
        repo.finish_run(conn, run_id, "succeeded", REFERENCE.replace(tzinfo=None))
    baseline = query(engine)
    feasible = [r for r in baseline["evaluations"] if r["feasible"]]
    assert feasible
    excluded = feasible[0]["station_id"]
    calls = []

    def diagnostic(conn, station, product, schedule, now):
        calls.append(station)
        if mode == "unavailable":
            raise DiagnosticUnavailable
        row = next(r for r in baseline["evaluations"] if int(r["station_id"]) == station)
        return {
            "station_id": station,
            "data_run_id": run_id + (mode == "mismatch"),
            "official_price_ars_per_l": row["price_ars_per_l"],
            "published_at": row["published_at_local"] + "-03:00",
            "method": "bandera_reciente",
            "version": "otra" if mode == "incompatible" else min(AUDITED_MODEL_VERSIONS),
            "reference_ars_per_l": None if mode == "unknown" else "1000",
            "alert_level": "provisional_deviation"
            if mode == "all" or row["station_id"] == excluded
            else "provisional_within_threshold",
        }

    monkeypatch.setattr(
        "nafta2go.application.conservative_ranking.price_diagnostics_on_connection",
        lambda conn, stations, product, schedule, now: {
            station: diagnostic(conn, station, product, schedule, now) for station in stations
        },
    )
    provider = Routes()
    result = query(engine, provider)
    assert provider.calls == 1
    assert result["alternatives"] == baseline["alternatives"]
    assert result["evaluations"] == baseline["evaluations"]
    block = result["conservative_ranking"]
    if mode in {"unavailable", "mismatch", "incompatible"}:
        assert block["status"] == "unavailable" and block["alternatives"] == []
    else:
        assert block["status"] == "available"
        assert len(calls) == len(feasible)
        if mode == "all":
            assert not block["alternatives"] and block["reason"] == "all_feasible_excluded"
        if mode == "some":
            assert excluded in block["excluded_station_ids"]
            assert excluded not in [c["station_id"] for c in block["alternatives"]]
        if mode == "unknown":
            assert block["alternatives"] == result["alternatives"]
            assert len(block["without_reference_station_ids"]) == len(feasible)
            assert not block["excluded_station_ids"]
    with engine.connect() as conn:
        record = repo.get_recommendation(conn, result["recommendation_id"])
    assert record["result"]["conservative_ranking"] == json.loads(json.dumps(block))


def test_historical_conservative_is_unavailable_without_reading_diagnostics(engine, monkeypatch):
    def forbidden(*args):
        raise AssertionError("No diagnosticar un escenario histórico como vigente")

    monkeypatch.setattr(
        "nafta2go.application.conservative_ranking.price_diagnostics_on_connection", forbidden
    )
    result = query(engine)
    assert result["conservative_ranking"]["status"] == "unavailable"
    assert not result["conservative_ranking"]["alternatives"]
