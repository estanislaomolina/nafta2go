"""Verifica que el ensayo mida veinte diagnósticos y restaure la configuración."""

import os

from nafta2go.domain import price_alert
from scripts.measure_active_diagnostics import measure


def test_active_load_is_explicitly_synthetic_and_restores_policy(monkeypatch):
    original = price_alert.AUDITED_MODEL_VERSIONS
    monkeypatch.setenv("NAFTA2GO_API_TOKEN", "codigo-previo")
    report = measure(runs=1, history_days=6)
    assert report["passed"]
    assert report["history_rows"] == 120
    assert report["runs"][0]["diagnostics"] == report["runs"][0]["evaluated"] == 20
    assert report["scope"] == "synthetic_active_diagnostics_not_real_history"
    assert report["policy_compatibility"] == "synthetic_manifest_override_only_in_harness"
    assert price_alert.AUDITED_MODEL_VERSIONS == original
    assert os.environ["NAFTA2GO_API_TOKEN"] == "codigo-previo"
