"""El benchmark no modifica la base fuente ni acredita diagnósticos ausentes."""

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.measure_real_history_diagnostics import measure


def test_measurement_uses_copy_and_missing_history_is_not_success(engine):
    source = Path(engine.url.database)
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    result = measure(source, datetime(2026, 10, 26, 12, tzinfo=UTC), count=1)
    assert not result["passed"]
    assert result["source_database_unchanged"]
    assert not result["runs"][0]["available"]
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before


def test_measurement_rejects_naive_clock_before_touching_source(tmp_path):
    source = tmp_path / "no.db"
    with pytest.raises(ValueError):
        measure(source, datetime(2026, 10, 26))
    assert not source.exists()
