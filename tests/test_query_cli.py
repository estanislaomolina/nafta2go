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
    assert "InvalidCredentials" in capsys.readouterr().err


def test_missing_matrix_is_reported(tmp_path, capsys):
    assert main([ORIGIN, "--matrix-file", str(tmp_path / "missing.json")]) == 2
    assert "FileNotFoundError" in capsys.readouterr().err


def test_no_coverage_requires_no_key(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("ORS_API_KEY", raising=False)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'query.db'}")
    assert main(["--origin=-34.71,-58.33", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["outcome"] == "insufficient_coverage"
    assert payload["recommendation_id"] is None


def test_origin_outside_caba_is_rejected_before_routing(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("ORS_API_KEY", raising=False)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'query.db'}")
    assert main(["--origin=0,0"]) == 2
    assert "origin: fuera del área" in capsys.readouterr().err


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
