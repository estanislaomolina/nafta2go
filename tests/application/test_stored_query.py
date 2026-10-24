"""Consulta desde SQLite migrado, con precios normalizados y rutas simulados."""

from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from nafta2go.adapters.routing import DistanceMatrix, Point, ProviderTimeout
from nafta2go.application.stored_query import (
    CoverageStatus,
    evaluate_from_database,
    select_stored_candidates,
)
from nafta2go.domain.engine import FuelRequest
from nafta2go.persistence import repository as repo
from nafta2go.persistence.models import NormalizationResult, RawCapture
from nafta2go.services.ingestion import ingest

REFERENCE = datetime(2026, 10, 24, 21, tzinfo=UTC)
LOCAL_REFERENCE = datetime(2026, 10, 24, 18)
ORIGIN = Point(-34.60, -58.38)
DESTINATION = Point(-34.56, -58.45)
REQUEST = FuelRequest(10, 50, 10, 12000, 2)


def price_row(station_id=1, **overrides):
    return {
        "fila_origen": station_id,
        "idempresa": station_id,
        "empresa": "ESTACION DE PRUEBA SA",
        "empresabandera": "PRUEBA",
        "direccion": "DIRECCION DE PRUEBA",
        "idproducto": 2,
        "tipo_nafta": "super",
        "idtipohorario": 2,
        "precio": Decimal(1200),
        "fecha_vigencia": datetime(2026, 10, 23, 6),
        "latitud": -34.61,
        "longitud": -58.40,
        "fecha_vigencia_original": "2026-10-23 06:00:00",
        "precio_original": "1200",
        "alertas": "",
        **overrides,
    }


def put_run(engine, rows=(), *, status="succeeded", source="vigente", finished_at=None):
    finished_at = finished_at or REFERENCE.replace(tzinfo=None)
    with engine.begin() as conn:
        run_id = repo.start_run(conn, source, finished_at)
        repo.add_prices(conn, run_id, rows)
        if status != "running":
            repo.finish_run(conn, run_id, status, finished_at)
    return run_id


def select(engine, **overrides):
    options = {"fuel_type": "super", "schedule_id": 2, "reference_at": REFERENCE, **overrides}
    with engine.connect() as conn:
        return select_stored_candidates(conn, **options)


class FakeProvider:
    def __init__(self):
        self.calls = []

    def matrix(self, sources, destinations):
        self.calls.append((list(sources), list(destinations)))
        return DistanceMatrix(
            durations_s=[[0 if start == end else 60 for end in destinations] for start in sources],
            distances_m=[
                [0 if start == end else 1000 for end in destinations] for start in sources
            ],
            sources=list(sources),
            destinations=list(destinations),
        )


def evaluate(engine, provider, **overrides):
    options = {"fuel_type": "super", "schedule_id": 2, "reference_at": REFERENCE, **overrides}
    with engine.connect() as conn:
        return evaluate_from_database(conn, REQUEST, ORIGIN, DESTINATION, provider, **options)


def test_no_ingestion_does_not_call_routes(engine):
    provider = FakeProvider()
    result = evaluate(engine, provider)
    assert result.selection.status == CoverageStatus.NO_SUCCESSFUL_INGESTION
    assert result.selection.data_run_id is None
    assert result.evaluations == () and provider.calls == []


def test_failed_running_and_historical_runs_are_not_current_data(engine):
    put_run(engine, [price_row()], status="failed")
    put_run(engine, [price_row()], status="running")
    put_run(engine, [price_row()], source="historico")
    assert select(engine).status == CoverageStatus.NO_SUCCESSFUL_INGESTION


def test_latest_successful_snapshot_is_not_mixed_with_other_runs(engine):
    put_run(engine, [price_row(1)], finished_at=datetime(2026, 10, 24, 18))
    latest = put_run(engine, [price_row(2)])
    put_run(engine, [price_row(3)], status="failed", finished_at=datetime(2026, 10, 25))
    put_run(engine, [price_row(4)], source="historico", finished_at=datetime(2026, 10, 25))
    selected = select(engine)
    assert selected.data_run_id == latest
    assert [item.station_id for item in selected.candidates] == ["2"]


def test_empty_latest_snapshot_does_not_fall_back_to_old_prices(engine):
    put_run(engine, [price_row()])
    latest = put_run(engine)
    provider = FakeProvider()
    result = evaluate(engine, provider)
    assert result.selection.data_run_id == latest
    assert result.selection.status == CoverageStatus.INSUFFICIENT_COVERAGE
    assert result.evaluations == () and provider.calls == []


def test_product_and_schedule_must_both_match(engine):
    put_run(
        engine,
        [
            price_row(1),
            price_row(2, idproducto=3, tipo_nafta="premium"),
            price_row(3, tipo_nafta="premium"),
            price_row(4, idtipohorario=3),
        ],
    )
    result = select(engine)
    assert [item.station_id for item in result.candidates] == ["1"]
    assert result.exclusions == {"incompatible_product": 2, "incompatible_schedule": 1}
    assert [item.station_id for item in select(engine, fuel_type="premium").candidates] == ["2"]
    assert [item.station_id for item in select(engine, schedule_id=3).candidates] == ["4"]


def test_freshness_is_exact_and_includes_the_boundary(engine):
    boundary = LOCAL_REFERENCE - timedelta(days=30)
    put_run(
        engine,
        [
            price_row(1, fecha_vigencia=boundary),
            price_row(2, fecha_vigencia=boundary - timedelta(seconds=1)),
            price_row(3, fecha_vigencia=LOCAL_REFERENCE + timedelta(seconds=1)),
        ],
    )
    result = select(engine)
    assert [item.station_id for item in result.candidates] == ["1"]
    assert result.exclusions == {"future_price": 1, "stale_price": 1}


def test_reference_timezone_is_converted_to_argentine_publication_time(engine):
    put_run(engine, [price_row(fecha_vigencia=LOCAL_REFERENCE)])
    utc_result = select(engine)
    local_result = select(engine, reference_at=REFERENCE.astimezone(timezone(timedelta(hours=-3))))
    assert utc_result == local_result
    assert utc_result.status == CoverageStatus.READY


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"latitud": None}, "missing_coordinates"),
        ({"longitud": float("nan")}, "missing_coordinates"),
        ({"latitud": float("inf")}, "invalid_coordinates"),
        ({"longitud": -58.58}, "outside_caba"),
        ({"alertas": "fuera_de_caba"}, "outside_caba"),
        ({"alertas": "sin_coordenadas"}, "missing_coordinates"),
        ({"precio": 0}, "invalid_price"),
        ({"precio": -1}, "invalid_price"),
    ],
)
def test_unusable_prices_or_coordinates_are_explained(engine, changes, reason):
    put_run(engine, [price_row(**changes)])
    result = select(engine)
    assert result.status == CoverageStatus.INSUFFICIENT_COVERAGE
    assert result.candidates == () and result.exclusions == {reason: 1}


def test_price_alert_is_preserved_without_changing_official_price(engine):
    put_run(engine, [price_row(alertas="precio_atipico; otra_alerta")])
    result = select(engine)
    assert result.status == CoverageStatus.READY
    assert result.items[0].alerts == ("precio_atipico", "otra_alerta")
    assert result.candidates[0].price_ars_per_l == Decimal(1200)


def test_only_latest_usable_publication_per_station_is_selected(engine):
    put_run(
        engine,
        [
            price_row(precio=1000, fecha_vigencia=datetime(2026, 10, 1)),
            price_row(fila_origen=42, precio=1200),
        ],
    )
    result = select(engine)
    assert len(result.items) == 1
    assert result.items[0].candidate.price_ars_per_l == Decimal(1200)
    assert result.items[0].source_row == 42
    assert result.exclusions == {"superseded_price": 1}


def test_limit_applies_after_deduplication_and_uses_numeric_ids(engine):
    put_run(engine, [price_row(i) for i in (12, 2, 1, 11, 3, 4, 5, 6, 7, 8, 9, 10)])
    result = select(engine)
    assert result.eligible_station_count == 12
    assert [item.station_id for item in result.candidates] == [str(i) for i in range(1, 11)]
    assert [item.station_id for item in select(engine, limit=3).candidates] == ["1", "2", "3"]


def test_minimum_coverage_prevents_partial_route_queries(engine):
    put_run(engine, [price_row(1), price_row(2)])
    provider = FakeProvider()
    result = evaluate(engine, provider, minimum_candidates=3)
    assert result.selection.status == CoverageStatus.INSUFFICIENT_COVERAGE
    assert result.selection.eligible_station_count == 2
    assert result.selection.minimum_candidates == 3
    assert result.evaluations == () and provider.calls == []


def test_ingestion_database_routes_and_engine_are_connected(engine):
    rows = [price_row(1), price_row(2, precio=1500)]
    capture = RawCapture(
        "vigente", "test://capture", "a" * 64, 1, "unused.csv", REFERENCE.replace(tzinfo=None)
    )
    run_id = ingest(
        engine,
        capture,
        lambda _: NormalizationResult(rows, [], {"filas_validas": 2}, "test-1"),
        clock=lambda: REFERENCE.replace(tzinfo=None),
    )
    provider = FakeProvider()
    result = evaluate(engine, provider)
    assert result.selection.data_run_id == run_id
    assert len(provider.calls) == 1
    assert [item.candidate.station_id for item in result.evaluations] == ["1", "2"]
    assert result.evaluations[0].evaluation.metrics.final_l == Decimal("19.8")
    assert result.evaluations[1].evaluation.metrics.final_l == Decimal("17.8")
    with engine.connect() as conn:
        stored = repo.prices_for_run(conn, run_id)
    assert [item.price_id for item in result.selection.items] == [row["id"] for row in stored]


def test_route_failures_are_not_reported_as_empty_coverage(engine):
    put_run(engine, [price_row()])

    class UnavailableProvider:
        def matrix(self, sources, destinations):
            raise ProviderTimeout("sin respuesta")

    with pytest.raises(ProviderTimeout):
        evaluate(engine, UnavailableProvider())


@pytest.mark.parametrize(
    "changes,field",
    [
        ({"fuel_type": "diesel"}, "fuel_type"),
        ({"fuel_type": []}, "fuel_type"),
        ({"schedule_id": 2.0}, "schedule_id"),
        ({"schedule_id": True}, "schedule_id"),
        ({"reference_at": LOCAL_REFERENCE}, "reference_at"),
        ({"limit": 11}, "limit"),
        ({"limit": True}, "limit"),
        ({"minimum_candidates": 0}, "minimum_candidates"),
        ({"minimum_candidates": 11}, "minimum_candidates"),
        ({"max_age_days": -1}, "max_age_days"),
        ({"max_age_days": True}, "max_age_days"),
        ({"max_age_days": 10**20}, "max_age_days"),
    ],
)
def test_invalid_query_options_fail_before_loading_data(engine, changes, field):
    with pytest.raises(ValueError, match=field):
        select(engine, **changes)
