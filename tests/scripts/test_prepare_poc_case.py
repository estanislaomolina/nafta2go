"""Trazabilidad del recorte real y reglas acotadas del caso controlado."""

import csv
import hashlib
import io
import json
from datetime import date
from pathlib import Path

import pytest

from scripts.prepare_poc_case import prepare_case

EVIDENCE = Path(__file__).resolve().parents[2] / "docs/evidencia/poc-05-obelisco-cabildo-2026-10-24"


@pytest.fixture
def snapshot():
    report = json.loads((EVIDENCE / "case.json").read_text(encoding="utf-8"))
    raw = (EVIDENCE / "prices.csv").read_bytes()
    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8"))))
    return report, raw, rows


def build_input(rows, metadata):
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    raw = out.getvalue().encode("utf-8")
    metadata = {**metadata, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
    return raw, metadata


def test_real_subset_matches_hash_dates_and_original_values(snapshot):
    report, raw, rows = snapshot
    assert hashlib.sha256(raw).hexdigest() == report["selected_prices"]["sha256"]
    assert len(rows) == len(report["candidates"]) == 10
    assert len({row["idempresa"] for row in rows}) == 10
    reference = date.fromisoformat(report["query"]["reference_date"])
    for row, candidate in zip(rows, report["candidates"], strict=True):
        assert row["provincia"] == "CAPITAL FEDERAL"
        assert row["idproducto"] == row["idtipohorario"] == "2"
        assert row["idempresa"] == candidate["station_id"]
        assert row["precio"] == candidate["price_ars_per_l"]
        assert row["latitud"] == candidate["lat"]
        assert row["longitud"] == candidate["lon"]
        assert row["fecha_vigencia"] == candidate["price_effective_at_raw"]
        age = (reference - date.fromisoformat(row["fecha_vigencia"][:10])).days
        assert 0 <= age <= 30
        assert age == candidate["price_age_calendar_days"]
    assert report["status"] == "prices_prepared_routes_pending"
    assert "routes" not in report and "recommendation" not in report


def test_reprocessing_subset_preserves_order_and_strings(snapshot):
    original, raw, _ = snapshot
    metadata = {**original["source"], "sha256": hashlib.sha256(raw).hexdigest()}
    result, subset = prepare_case(raw, metadata)
    assert subset == raw
    assert [item["station_id"] for item in result["candidates"]] == [
        item["station_id"] for item in original["candidates"]
    ]


def test_thirty_day_boundary_and_future_dates(snapshot):
    original, _, rows = snapshot
    rows = [
        {**rows[0], "idempresa": "1", "fecha_vigencia": "2026-09-24 00:00:00"},
        {**rows[0], "idempresa": "2", "fecha_vigencia": "2026-09-23 00:00:00"},
        {**rows[0], "idempresa": "3", "fecha_vigencia": "2026-10-25 00:00:00"},
    ]
    result, _ = prepare_case(*build_input(rows, original["source"]))
    assert [item["station_id"] for item in result["candidates"]] == ["1"]
    assert result["candidates"][0]["price_age_calendar_days"] == 30
    assert result["coverage"]["excluded_rows"] == {"future_date": 1, "older_than_30_days": 1}


def test_duplicate_keys_are_excluded_without_picking_a_price(snapshot):
    original, _, rows = snapshot
    rows = [rows[0], {**rows[0], "precio": "1"}, rows[1]]
    result, _ = prepare_case(*build_input(rows, original["source"]))
    assert [item["station_id"] for item in result["candidates"]] == [rows[2]["idempresa"]]
    assert result["coverage"]["excluded_rows"]["duplicate_key"] == 2


def test_tied_dates_use_numeric_station_id(snapshot):
    original, _, rows = snapshot
    rows = [{**rows[0], "idempresa": str(i)} for i in (10, 2, 1, 11, 3, 4, 5, 6, 7, 8, 9)]
    result, _ = prepare_case(*build_input(rows, original["source"]))
    assert [item["station_id"] for item in result["candidates"]] == [str(i) for i in range(1, 11)]
    assert result["coverage"]["recent_stations"] == 11


@pytest.mark.parametrize(
    "changes",
    [
        {"fecha_vigencia": "23/10/2026"},
        {"precio": "NaN"},
        {"precio": "-1"},
        {"latitud": "Infinity"},
        {"latitud": "0"},
        {"longitud": "0"},
        {"idempresa": ""},
    ],
)
def test_invalid_rows_do_not_become_candidates(snapshot, changes):
    original, _, rows = snapshot
    result, _ = prepare_case(*build_input([{**rows[0], **changes}], original["source"]))
    assert result["candidates"] == []
    assert result["status"] == "insufficient_price_coverage"
    assert result["coverage"]["excluded_rows"]["invalid_record"] == 1


def test_corrupted_capture_is_rejected(snapshot):
    report, raw, _ = snapshot
    with pytest.raises(ValueError, match="SHA-256"):
        prepare_case(raw + b"\n", report["source"])


@pytest.mark.parametrize("key,value", [("resource_id", "otro"), ("license_id", "desconocida")])
def test_unexpected_provenance_is_rejected(snapshot, key, value):
    report, raw, _ = snapshot
    metadata = {**report["source"], "sha256": hashlib.sha256(raw).hexdigest(), key: value}
    with pytest.raises(ValueError, match="recurso o su licencia"):
        prepare_case(raw, metadata)
