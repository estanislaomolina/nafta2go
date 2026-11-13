"""Pipeline offline sobre una ingesta sintética migrada; ninguna prueba usa red."""

import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from nafta2go.application.price_dataset import prepare_price_dataset, sha256
from nafta2go.application.scenario import load_scenario
from nafta2go.ml.__main__ import main
from nafta2go.persistence import repository as repo
from nafta2go.persistence.models import RawCapture
from nafta2go.persistence.schema import ingestion_runs, station_prices

CUTOFF = datetime(2026, 1, 3, tzinfo=UTC)


@pytest.fixture
def historical(engine):
    base = load_scenario().rows[0]
    when = datetime(2026, 1, 1, 12)
    with engine.begin() as conn:
        run_id = repo.start_run(conn, "historico", when)
        repo.add_raw_capture(
            conn,
            run_id,
            RawCapture(
                "historico",
                "https://example.invalid/secreto-url",
                "a" * 64,
                1234,
                "/secreto-ruta.csv",
                when,
            ),
        )
        rows = [
            {
                **base,
                "id": None,
                "station_id": i + 1,
                "source_row": i + 1,
                "valid_from": when + timedelta(days=day),
                "price": price,
                "lat": -34.60,
                "lon": -58.40,
                "product_id": 2,
                "schedule_id": 2,
            }
            for i, (day, price) in enumerate(
                ((0, 100), (0, 110), (0, 120), (1, 125), (1, 135), (2, 150))
            )
        ]
        conn.execute(station_prices.insert(), [{**row, "run_id": run_id} for row in rows])
        repo.finish_run(conn, run_id, "succeeded", when, rules_version="1")
    return run_id


def test_outputs_are_repeatable_hashed_and_do_not_mutate_ingestion(engine, historical, tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    with engine.connect() as conn:
        before = conn.execute(select(ingestion_runs)).all()
    result = prepare_price_dataset(engine, first, CUTOFF, min_history=3)
    other = prepare_price_dataset(engine, second, CUTOFF, min_history=3)
    assert result == other
    assert (first / "examples.jsonl").read_bytes() == (second / "examples.jsonl").read_bytes()
    manifest = result["manifest"]
    assert manifest["dataset_sha256"] == sha256((first / "examples.jsonl").read_bytes())
    assert manifest["normalized_rows"] == 6 and manifest["model_trained"] is False
    assert manifest["availability_assumption"].startswith("valid_from_proxy")
    assert "secreto" not in json.dumps(result)
    assert set(p.name for p in first.iterdir()) == {
        "manifest.json",
        "examples.jsonl",
        "baseline-report.json",
    }
    with engine.connect() as conn:
        assert conn.execute(select(ingestion_runs)).all() == before
        assert repo.get_run(conn, historical)["status"] == "succeeded"
    with pytest.raises(ValueError, match="nuevo"):
        prepare_price_dataset(engine, first, CUTOFF, min_history=3)


def test_missing_history_or_capture_and_unusable_cut_are_rejected(engine, tmp_path, historical):
    with pytest.raises(ValueError, match="ambas"):
        prepare_price_dataset(engine, tmp_path / "bad", CUTOFF + timedelta(days=99), min_history=3)
    assert not (tmp_path / "bad").exists()
    from nafta2go.persistence.schema import raw_captures

    with engine.begin() as conn:
        conn.execute(raw_captures.delete())
    with pytest.raises(ValueError, match="captura"):
        prepare_price_dataset(engine, tmp_path / "missing", CUTOFF)


def test_empty_database_is_not_a_training_dataset(engine, tmp_path):
    with pytest.raises(ValueError, match="histórica"):
        prepare_price_dataset(engine, tmp_path / "empty", CUTOFF)


def test_cli_uses_existing_database_and_keeps_errors_safe(
    historical, database_url, tmp_path, monkeypatch, capsys
):
    monkeypatch.setenv("DATABASE_URL", database_url)
    args = [
        "--output",
        str(tmp_path / "dataset"),
        "--cutoff",
        CUTOFF.isoformat(),
        "--min-history",
        "3",
    ]
    assert main(args) == 0
    assert json.loads(capsys.readouterr().out)["manifest"]["model_trained"] is False
    assert main(args) == 2
    assert "secreto" not in capsys.readouterr().err
    with pytest.raises(SystemExit) as caught:
        main(["--cutoff=secreto-no-fecha"])
    assert caught.value.code == 2 and "secreto" not in capsys.readouterr().err


def test_code_hash_is_available_without_git(monkeypatch):
    from nafta2go.application.price_dataset import code_provenance

    def absent(*args, **kwargs):
        raise FileNotFoundError("git ausente")

    monkeypatch.setattr("nafta2go.application.price_dataset.subprocess.run", absent)
    metadata = code_provenance()
    assert len(metadata["files_sha256"]) == 64
    assert metadata["git_commit"] is metadata["git_dirty"] is None
