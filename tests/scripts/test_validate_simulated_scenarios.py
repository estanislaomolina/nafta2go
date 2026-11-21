"""La simulación técnica no genera participantes ni métricas de comprensión."""

import json

import pytest

from nafta2go.adapters.routing import ProviderTimeout
from scripts import validate_simulated_scenarios as validation


def test_ten_scenarios_audit_stored_results_and_restore_access(monkeypatch):
    monkeypatch.setenv("NAFTA2GO_API_TOKEN", "valor-previo")
    report = validation.measure()
    assert report["real_participants"] == 0
    assert report["scope"] == "technical_scenarios_not_user_study"
    assert report["passed_cases"] == 10 and report["audit_passed"]
    assert report["latency_s"]["UC01"]["requests"] == report["latency_s"]["UC02"]["requests"] == 5
    assert report["audit"]["privacidad"]["cumplen"] == 10
    assert "valor-previo" not in json.dumps(report)
    assert validation.os.environ["NAFTA2GO_API_TOKEN"] == "valor-previo"


def test_provider_failure_is_not_counted_as_success():
    class Timeout:
        def matrix(self, sources, destinations):
            raise ProviderTimeout("No disponible")

    report = validation.measure(Timeout)
    assert report["passed_cases"] == 0
    assert all(case["http_status"] == 504 for case in report["cases"])


def test_live_requires_key_and_default_remains_offline(tmp_path, monkeypatch):
    monkeypatch.delenv("ORS_API_KEY", raising=False)
    with pytest.raises(SystemExit) as error:
        validation.main(["--live-routes", "--output", str(tmp_path / "no.json")])
    assert error.value.code == 2 and not (tmp_path / "no.json").exists()
