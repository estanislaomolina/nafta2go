"""Entradas inválidas y errores de rutas se explican sin red."""

import json
from pathlib import Path

import pytest

from nafta2go.query.__main__ import main

ORIGIN = "--origin=-34.6037,-58.3816"
DESTINATION = "--destination=-34.5627,-58.4565"


@pytest.mark.parametrize(
    "option",
    ["--presupuesto=-1", "--consumo=nan", "--reserva=60", "--reference-at=2026-10-26T12:00"],
)
def test_bad_vehicle_and_dates_are_rejected(option, capsys):
    assert main([ORIGIN, DESTINATION, option]) == 2
    assert "Consulta fallida" in capsys.readouterr().err


def test_missing_key_is_reported_without_faking_routes(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("ORS_API_KEY", raising=False)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'query.db'}")
    assert main([ORIGIN, DESTINATION]) == 2
    assert "routes_not_configured" in capsys.readouterr().err


def test_missing_matrix_is_reported(tmp_path, capsys):
    assert main([ORIGIN, "--matrix-file", str(tmp_path / "missing.json")]) == 2
    assert "file_unavailable" in capsys.readouterr().err


@pytest.mark.parametrize("limit", [10, 20])
def test_no_coverage_requires_no_key(tmp_path, monkeypatch, capsys, limit):
    monkeypatch.delenv("ORS_API_KEY", raising=False)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'query.db'}")
    assert main(["--origin=-34.71,-58.33", f"--max-candidates={limit}", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["outcome"] == "insufficient_coverage"
    assert payload["recommendation_id"] is None
    assert payload["query"]["max_candidates"] == limit


def test_origin_outside_caba_is_rejected_before_routing(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("ORS_API_KEY", raising=False)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'query.db'}")
    assert main(["--origin=0,0"]) == 2
    assert "invalid_request" in capsys.readouterr().err


def test_reproduces_the_real_case_without_credentials(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("ORS_API_KEY", raising=False)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'query.db'}")
    evidence = Path(__file__).resolve().parents[1] / "docs/evidencia/poc-05-flujo-2026-10-26"
    assert (
        main([ORIGIN, DESTINATION, "--matrix-file", str(evidence / "matrix.json"), "--json"]) == 0
    )
    payload = json.loads(capsys.readouterr().out)
    original = json.loads((evidence / "historical-result.json").read_text())
    assert payload["status"] == "historical_scenario"
    assert payload["alternatives"] == original["alternatives"]
    assert payload["evaluations"] == original["evaluations"]
    assert payload["routes"]["replayed"]
    assert {link["station_id"] for link in payload["navigation"]} == {
        row["station_id"] for row in payload["alternatives"]
    }
    assert "navigation_destinations" not in payload


@pytest.mark.parametrize("limit", [2, 21])
def test_cli_rejects_candidate_limit_outside_supported_range(limit):
    with pytest.raises(SystemExit) as exc:
        main([ORIGIN, f"--max-candidates={limit}"])
    assert exc.value.code == 2


def test_budget_variant_discards_instead_of_inventing_a_recommendation(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'query.db'}")
    matrix = (
        Path(__file__).resolve().parents[1] / "docs/evidencia/poc-05-flujo-2026-10-26/matrix.json"
    )
    assert (
        main([ORIGIN, DESTINATION, "--matrix-file", str(matrix), "--presupuesto=0", "--json"]) == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["outcome"] == "no_feasible_stations"
    assert payload["alternatives"] == []
    assert all("no_budget" in row["reasons"] for row in payload["evaluations"])


def test_text_result_shows_maps_and_keeps_historical_label(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'query.db'}")
    matrix = (
        Path(__file__).resolve().parents[1] / "docs/evidencia/poc-05-flujo-2026-10-26/matrix.json"
    )
    assert main([ORIGIN, DESTINATION, "--matrix-file", str(matrix)]) == 0
    text = capsys.readouterr().out
    assert "Cómo llegar a " in text and "https://www.google.com/maps/dir/" in text
    assert "Google Maps recalcula" in text and "ESCENARIO HISTÓRICO" in text
