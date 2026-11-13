"""Telemetría CLI separada del resultado, con fallos sensibles inyectados."""

import json
from datetime import datetime
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy.exc import SQLAlchemyError

import nafta2go.query.__main__ as cli
from nafta2go.adapters.routing import ProviderTimeout, ProviderUnavailable, QuotaExceeded

ORIGIN = "--origin=-34.6037,-58.3816"
DESTINATION = "--destination=-34.5627,-58.4565"
MATRIX = Path(__file__).resolve().parents[1] / "docs/evidencia/poc-05-flujo-2026-10-26/matrix.json"


def event(stderr):
    events = [json.loads(line) for line in stderr.splitlines() if line.startswith('{"event":')]
    assert len(events) == 1
    record = events[0]
    assert UUID(record["request_id"]).hex == record["request_id"]
    assert datetime.fromisoformat(record["started_at_utc"]).utcoffset().total_seconds() == 0
    assert record["duration_ms"] >= 0 and record["channel"] == "cli"
    assert set(record) == {
        "event",
        "channel",
        "request_id",
        "started_at_utc",
        "duration_ms",
        "exit_code",
        "outcome",
        "error_code",
    }
    for private in ("-34.6037", "-58.4565", "secreto", str(MATRIX)):
        assert private not in stderr
    return record


@pytest.mark.parametrize(
    "outcome", ["recommended", "no_feasible_stations", "insufficient_coverage"]
)
def test_success_preserves_json_stdout_and_reports_outcome(tmp_path, monkeypatch, capsys, outcome):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'secreto-base.db'}")
    arguments = [ORIGIN, DESTINATION, "--matrix-file", str(MATRIX), "--json"]
    if outcome == "no_feasible_stations":
        arguments += ["--presupuesto=0"]
    elif outcome == "insufficient_coverage":
        arguments = ["--origin=-34.71,-58.33", "--json"]
    assert cli.main(arguments) == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out)["outcome"] == outcome
    record = event(captured.err)
    assert record["outcome"] == outcome and record["exit_code"] == 0
    assert record["error_code"] is None


@pytest.mark.parametrize(
    "error,code",
    [
        (ValueError("secreto-valor"), "invalid_request"),
        (OSError("secreto-archivo"), "file_unavailable"),
        (SQLAlchemyError("secreto-clave-base"), "data_unavailable"),
        (ProviderTimeout("secreto-proveedor"), "routes_timeout"),
        (QuotaExceeded("secreto-cuota"), "routes_quota_exceeded"),
        (ProviderUnavailable("secreto-rutas"), "routes_unavailable"),
        (RuntimeError("secreto-inesperado"), "internal_error"),
    ],
)
def test_errors_hide_original_messages_and_keep_exit_code(monkeypatch, capsys, error, code):
    def fail():
        raise error

    monkeypatch.setattr(cli, "database_url", fail)
    assert cli.main([ORIGIN, "--json"]) == 2
    captured = capsys.readouterr()
    assert captured.out == "" and "Consulta fallida" in captured.err
    record = event(captured.err)
    assert record["error_code"] == code and record["outcome"] == "error"
    assert record["exit_code"] == 2 and "Traceback" not in captured.err


@pytest.mark.parametrize(
    "argument", ["--origin=secreto-invalido", "--fuel-type=secreto-tipo", "--secreto-desconocido"]
)
def test_parser_errors_do_not_echo_submitted_arguments(argument, capsys):
    with pytest.raises(SystemExit) as caught:
        cli.main([ORIGIN, argument])
    assert caught.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == "" and "Argumentos inválidos" in captured.err
    assert event(captured.err)["outcome"] == "invalid_arguments"


def test_help_does_not_count_as_a_query(capsys):
    with pytest.raises(SystemExit) as caught:
        cli.main(["--help"])
    assert caught.value.code == 0
    captured = capsys.readouterr()
    assert "--origin" in captured.out and captured.err == ""


def test_keyboard_interrupt_has_safe_message_and_exit_130(monkeypatch, capsys):
    def fail():
        raise KeyboardInterrupt("secreto-interrupcion")

    monkeypatch.setattr(cli, "database_url", fail)
    assert cli.main([ORIGIN]) == 130
    captured = capsys.readouterr()
    record = event(captured.err)
    assert record["exit_code"] == 130 and record["outcome"] == "interrupted"


def test_curated_vehicle_error_identifies_field_without_changing_telemetry(capsys):
    assert cli.main([ORIGIN, "--litros-iniciales=60"]) == 2
    captured = capsys.readouterr()
    assert "remaining_l: supera la capacidad del tanque" in captured.err
    record = event(captured.err)
    assert record["error_code"] == "invalid_request" and "remaining_l" not in str(record)


def test_parser_identifies_known_field_and_choices_without_echo(capsys):
    with pytest.raises(SystemExit) as caught:
        cli.main([ORIGIN, "--schedule-id=secreto"])
    assert caught.value.code == 2
    captured = capsys.readouterr()
    assert "Revisá --schedule-id" in captured.err and "Opciones permitidas: 2, 3" in captured.err
    assert event(captured.err)["outcome"] == "invalid_arguments"


def test_invalid_reference_has_safe_actionable_message(capsys):
    assert cli.main([ORIGIN, "--reference-at=secreto"]) == 2
    captured = capsys.readouterr()
    assert "reference_at: usar fecha ISO 8601 con zona horaria" in captured.err
    assert event(captured.err)["error_code"] == "invalid_request"
