"""El registro conserva corridas reales, aplica ADR-014 y no habilita umbrales incompatibles."""

import copy
import hashlib
import json
from decimal import Decimal

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
        reg.register(trial, copied, report, "otra-politica", CURRENT / "alert-evaluation.json")
    version = reg.register(trial, copied, report, None)
    assert trial["runs"][version]["candidates"]["ridge"]["kind"] == "model"
    assert reg.audited_versions("conservative-v1", "bandera_reciente", trial) == (
        price_alert.AUDITED_MODEL_VERSIONS
    )


def test_policy_requires_a_verified_audit_of_the_same_run(registry, tmp_path):
    """Cambiar la semilla y reusar el reporte no habilita los umbrales sin su auditoría."""
    trial = copy.deepcopy(registry)
    model = json.loads((CURRENT / "model-manifest.json").read_bytes())
    model["parameters"]["random_seed"] = 1
    manifest = tmp_path / "model-manifest.json"
    manifest.write_text(json.dumps(model))
    report, audit = CURRENT / "model-report.json", CURRENT / "alert-evaluation.json"
    with pytest.raises(reg.RegistryError):
        reg.register(trial, manifest, report, "conservative-v1")
    with pytest.raises(reg.RegistryError):
        reg.register(trial, manifest, report, "conservative-v1", audit)
    forged = json.loads(audit.read_bytes())
    forged["model_manifest_sha256"] = hashlib.sha256(manifest.read_bytes()).hexdigest()
    next(iter(forged["segments"].values()))["relative_deviation_threshold"] = 0.2
    (tmp_path / "audit.json").write_text(json.dumps(forged))
    with pytest.raises(reg.RegistryError):
        reg.register(trial, manifest, report, "conservative-v1", tmp_path / "audit.json")
    assert trial == registry
    version = reg.register(trial, manifest, report, None)
    trial["runs"][version]["policy"] = "conservative-v1"  # Etiqueta sin auditoría.
    with pytest.raises(reg.RegistryError):
        reg.promote(trial, version)
    assert trial["aliases"] == registry["aliases"]
    assert version not in reg.audited_versions("conservative-v1", "bandera_reciente", trial)


def test_audited_runs_match_their_audit_and_the_served_thresholds(registry):
    policy = registry["policies"]["conservative-v1"]
    assert {int(k): Decimal(v) for k, v in policy["thresholds"].items()} == price_alert.THRESHOLDS
    for version, run in registry["runs"].items():
        if run["policy"] is None:
            assert run["audit"] is None
            continue
        audit = ROOT / run["audit"]["file"]
        assert hashlib.sha256(audit.read_bytes()).hexdigest() == run["audit"]["sha256"]
        assert reg.verified_audit(registry, version, run["policy"], audit) == run["audit"]


def test_cli_promotion_failure_leaves_the_file_untouched(tmp_path, monkeypatch, capsys):
    path = tmp_path / "registry.json"
    path.write_bytes(reg.REGISTRY.read_bytes())
    monkeypatch.setattr(reg, "REGISTRY", path)
    before = path.read_bytes()
    assert reg.main(["promote", "--run", "desconocida"]) == 1
    assert path.read_bytes() == before
    assert reg.main(["show"]) == 0
    assert "champion" in capsys.readouterr().out
