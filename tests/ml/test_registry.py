"""El registro conserva corridas reales, aplica ADR-014 y no habilita umbrales incompatibles."""

import copy
import hashlib
import json

import pytest

from nafta2go.domain import price_alert
from nafta2go.ml import registry as reg

ROOT = reg.REGISTRY.parents[2]
EVIDENCE = ROOT / "docs/evidencia"
CURRENT = EVIDENCE / "actualizacion-precios-2026-11-22"


@pytest.fixture
def registry():
    return reg.load()


def test_registered_runs_match_their_conserved_files(registry):
    for version, run in registry["runs"].items():
        manifest = (ROOT / run["manifest"]).read_bytes()
        assert hashlib.sha256(manifest).hexdigest() == version
        if run["report"]:
            report = ROOT / run["report"]
            assert hashlib.sha256(report.read_bytes()).hexdigest() == run["report_sha256"]
        model = json.loads(manifest)
        assert run["artifacts"][model["artifact_file"]]["sha256"] == model["artifact_sha256"]
    assert registry["missing"]


def test_champion_is_the_selection_winner_and_models_are_challengers(registry):
    champion = registry["aliases"]["champion"]
    run = registry["runs"][champion["run"]]
    assert champion["method"] == reg.selection_winner(run) == "bandera_reciente"
    assert {c["method"] for c in registry["aliases"]["challengers"]} == {"boosting", "ridge"}
    assert {m for m, c in run["candidates"].items() if c["kind"] == "reference"} == set(
        reg.REFERENCES
    )


def test_serving_accepts_exactly_the_audited_runs_of_the_registry(registry):
    audited = {v for v, r in registry["runs"].items() if r["policy"] == "conservative-v1"}
    assert price_alert.AUDITED_MODEL_VERSIONS == audited
    assert registry["aliases"]["champion"]["run"] in audited
    assert reg.audited_versions("conservative-v1", "boosting", registry) == frozenset()


def test_promotion_ignores_validation_and_rejects_incompatible_runs(registry):
    champion = registry["aliases"]["champion"]["run"]
    trial = copy.deepcopy(registry)
    run = trial["runs"][champion]
    # Boosting gana en validación 2026, pero eso no cuenta para elegir (ADR-014).
    assert (
        run["candidates"]["boosting"]["validation_mae_ars_per_l"]
        < (run["candidates"]["bandera_reciente"]["validation_mae_ars_per_l"])
    )
    reg.promote(trial, champion)
    assert trial["aliases"] == registry["aliases"]

    without_policy = next(v for v, r in trial["runs"].items() if r["policy"] is None)
    without_report = next(v for v, r in trial["runs"].items() if r["candidates"] is None)
    for version in (without_policy, without_report, "desconocida"):
        with pytest.raises(reg.RegistryError):
            reg.promote(trial, version)
    assert trial["aliases"] == registry["aliases"]

    run["candidates"]["boosting"]["selection_mae_ars_per_l"] = 1.0
    with pytest.raises(reg.RegistryError):
        reg.promote(trial, champion)


def test_register_refuses_duplicates_and_unknown_policies(registry, tmp_path):
    trial = copy.deepcopy(registry)
    manifest, report = CURRENT / "model-manifest.json", CURRENT / "model-report.json"
    with pytest.raises(reg.RegistryError):
        reg.register(trial, manifest, report, None)
    copied = tmp_path / "model-manifest.json"
    copied.write_bytes(manifest.read_bytes() + b"\n")
    with pytest.raises(reg.RegistryError):
        reg.register(trial, copied, report, "otra-politica")
    version = reg.register(trial, copied, report, None)
    assert trial["runs"][version]["candidates"]["ridge"]["kind"] == "model"
    assert reg.audited_versions("conservative-v1", "bandera_reciente", trial) == (
        price_alert.AUDITED_MODEL_VERSIONS
    )


def test_cli_promotion_failure_leaves_the_file_untouched(tmp_path, monkeypatch, capsys):
    path = tmp_path / "registry.json"
    path.write_bytes(reg.REGISTRY.read_bytes())
    monkeypatch.setattr(reg, "REGISTRY", path)
    monkeypatch.setattr(reg.load, "__defaults__", (path,))
    monkeypatch.setattr(reg.save, "__defaults__", (path,))
    before = path.read_bytes()
    assert reg.main(["promote", "--run", "desconocida"]) == 1
    assert path.read_bytes() == before
    assert reg.main(["show"]) == 0
    assert "champion" in capsys.readouterr().out
