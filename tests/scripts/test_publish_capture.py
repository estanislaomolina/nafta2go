"""No publicar un puntero nuevo si falla la adquisición, calidad o transferencia."""

import hashlib
import subprocess
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest

from nafta2go.normalization.rules import LOCAL_TIMEZONE
from nafta2go.persistence.models import RawCapture
from scripts import publish_capture as publisher


@pytest.fixture
def acquired(monkeypatch, tmp_path):
    path = tmp_path / "capture.csv"
    path.write_bytes(Path("tests/fixtures/vigente_sample.csv").read_bytes())
    capture = RawCapture(
        "vigente",
        "http://datos.energia.gob.ar/vigente.csv",
        hashlib.sha256(path.read_bytes()).hexdigest(),
        path.stat().st_size,
        str(path),
        datetime.now(ZoneInfo(LOCAL_TIMEZONE)).replace(tzinfo=None),
    )
    monkeypatch.setattr(publisher, "acquire_with_retries", lambda acquire, source: capture)
    return path


def publish(tmp_path, run):
    return publisher.publish(
        "nafta2go-test",
        tmp_path,
        "https://github.com/estanislaomolina/nafta2go/actions/runs/123",
        "a" * 40,
        run=run,
    )


def test_publishes_csv_before_latest_with_bounded_machine_identity(acquired, tmp_path):
    run = Mock()
    result = publish(tmp_path, run)
    assert result["valid_rows"] > 0
    keys = [call.args[0][call.args[0].index("--key") + 1] for call in run.call_args_list]
    assert keys == [f"vigente/{result['sha256']}.csv", "vigente/latest.json"]
    for call in run.call_args_list:
        assert "--profile" not in call.args[0]
        assert call.kwargs["env"]["AWS_MAX_ATTEMPTS"] == "3"
        assert call.kwargs["timeout"] == 300
        assert call.kwargs["check"] is True


def test_upload_failure_never_advances_latest(acquired, tmp_path):
    run = Mock(side_effect=subprocess.CalledProcessError(1, "aws"))
    with pytest.raises(subprocess.CalledProcessError):
        publish(tmp_path, run)
    assert run.call_count == 1


def test_corrupted_capture_is_never_published(acquired, tmp_path):
    acquired.write_text("corrupto")
    run = Mock()
    with pytest.raises(ValueError, match="tamaño"):
        publish(tmp_path, run)
    run.assert_not_called()


def test_empty_normalized_capture_is_never_published(acquired, tmp_path, monkeypatch):
    monkeypatch.setattr(publisher, "normalize_capture", lambda c: Mock(rows=[]))
    run = Mock()
    with pytest.raises(ValueError, match="utilizables"):
        publish(tmp_path, run)
    run.assert_not_called()


def test_acquisition_failure_is_never_published(tmp_path, monkeypatch):
    def fail(*args):
        raise RuntimeError("adquisición agotada")

    monkeypatch.setattr(publisher, "acquire_with_retries", fail)
    run = Mock()
    with pytest.raises(RuntimeError):
        publish(tmp_path, run)
    run.assert_not_called()


def test_invalid_bucket_does_not_acquire(tmp_path, monkeypatch):
    acquire = Mock()
    monkeypatch.setattr(publisher, "acquire_with_retries", acquire)
    with pytest.raises(ValueError, match="bucket"):
        publisher.publish("bad;command", tmp_path, "unused", "unused")
    acquire.assert_not_called()
