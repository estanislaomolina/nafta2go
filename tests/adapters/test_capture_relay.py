"""La transferencia conserva linaje y falla cerrada ante corrupción o replay viejo."""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from nafta2go.adapters.capture_relay import capture_from_receipt, read_receipt, receipt_for
from nafta2go.persistence.models import RawCapture

NOW = datetime(2026, 11, 23, 12, tzinfo=UTC)
RUN = "https://github.com/estanislaomolina/nafta2go/actions/runs/123"


@pytest.fixture
def transfer(tmp_path):
    csv = tmp_path / "capture.csv"
    csv.write_bytes(Path("tests/fixtures/vigente_sample.csv").read_bytes())
    capture = RawCapture(
        "vigente",
        "http://datos.energia.gob.ar/dataset/vigente.csv",
        hashlib.sha256(csv.read_bytes()).hexdigest(),
        csv.stat().st_size,
        str(csv),
        datetime(2026, 11, 23, 9),
        "2026-11-22",
        2,
    )
    receipt = tmp_path / "receipt.json"
    receipt.write_text(json.dumps(receipt_for(capture, RUN, "a" * 40)))
    return csv, receipt, capture


def test_preserves_origin_and_acquisition_date_instead_of_copy_mtime(transfer):
    csv, receipt, original = transfer
    copied = capture_from_receipt(csv, receipt, NOW)
    assert copied.url == original.url
    assert copied.fetched_at == original.fetched_at
    assert copied.source_last_modified == original.source_last_modified
    assert copied.acquisition_attempts == 2
    assert copied.provenance == {
        "method": "github-actions-s3",
        "workflow_run": RUN,
        "commit": "a" * 40,
        "receipt_sha256": hashlib.sha256(receipt.read_bytes()).hexdigest(),
    }


@pytest.mark.parametrize(
    "change",
    [
        {"schema_version": 2},
        {"source": "historico"},
        {"sha256": "../escape"},
        {"size_bytes": 0},
        {"size_bytes": True},
        {"size_bytes": 101 * 1024 * 1024},
        {"acquisition_attempts": 0},
        {"acquisition_attempts": True},
        {"workflow_run": "https://evil.test/123"},
        {"commit": "main"},
        {"url": "file:///private/secret"},
        {"url": "http://evil.test/csv"},
        {"url": "http://datos.energia.gob.ar/csv?token=secret"},
        {"url": "http://user:secret@datos.energia.gob.ar/csv"},
        {"source_last_modified": []},
        {"fetched_at": "2026-11-23T12:00:00"},
        {"fetched_at": "bad"},
        {"fetched_at": None},
    ],
)
def test_rejects_invalid_receipts_before_reading_csv(transfer, change):
    csv, receipt, _ = transfer
    data = json.loads(receipt.read_text())
    data.update(change)
    receipt.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        capture_from_receipt(csv, receipt, NOW)


@pytest.mark.parametrize("offset", [timedelta(hours=37), -timedelta(minutes=6)])
def test_rejects_expired_or_future_capture(transfer, offset):
    csv, receipt, _ = transfer
    with pytest.raises(ValueError, match="ventana"):
        capture_from_receipt(csv, receipt, NOW + offset)


@pytest.mark.parametrize("same_size", [False, True])
def test_rejects_truncated_and_tampered_bytes(transfer, same_size):
    csv, receipt, _ = transfer
    content = csv.read_bytes()
    csv.write_bytes(b"X" + content[1:] if same_size else content[:-1])
    with pytest.raises(ValueError, match="SHA-256|tamaño"):
        capture_from_receipt(csv, receipt, NOW)


@pytest.mark.parametrize("content", ["[]", "x" * 16385])
def test_rejects_wrong_type_and_oversized_receipt(tmp_path, content):
    receipt = tmp_path / "receipt.json"
    receipt.write_text(content)
    with pytest.raises(ValueError):
        read_receipt(receipt, NOW)


def test_import_records_provenance_and_does_not_commit_corrupted_prices(
    transfer, engine, monkeypatch, capsys
):
    from nafta2go.normalization import __main__ as cli
    from nafta2go.persistence import repository as repo

    csv, receipt, _ = transfer
    monkeypatch.setattr(cli, "database_url", lambda: str(engine.url))
    monkeypatch.setattr(cli, "capture_from_receipt", lambda c, r: capture_from_receipt(c, r, NOW))
    args = ["--source", "vigente", "--file", str(csv), "--receipt", str(receipt), "--json"]
    assert cli.main(args) == 0
    success = json.loads(capsys.readouterr().out)
    assert success["report"]["acquisition_provenance"]["workflow_run"] == RUN
    with engine.connect() as conn:
        count = conn.exec_driver_sql("select count(*) from station_prices").scalar()
    csv.write_text("truncado")
    assert cli.main(args) == 1
    failure = json.loads(capsys.readouterr().out)
    assert failure["status"] == "failed"
    with engine.connect() as conn:
        assert conn.exec_driver_sql("select count(*) from station_prices").scalar() == count
        assert repo.get_run(conn, success["run_id"])["status"] == "succeeded"


@pytest.mark.parametrize(
    "args",
    [
        ["--source", "vigente", "--receipt", "receipt.json"],
        ["--source", "historico", "--file", "c.csv", "--receipt", "receipt.json"],
    ],
)
def test_cli_rejects_incomplete_receipt_options_before_database(args):
    from nafta2go.normalization.__main__ import main

    with pytest.raises(SystemExit) as exc:
        main(args)
    assert exc.value.code == 2
