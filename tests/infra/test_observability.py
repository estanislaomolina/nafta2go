"""Provisioning reproducible y accesible sólo por loopback; secretos externos."""

import json
from pathlib import Path

import pytest
import yaml

from scripts.prepare_observability_secrets import prepare

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "deploy/observability"


def test_aws_datasource_matches_dashboards_and_metrics_stay_on_loopback():
    source = yaml.safe_load((BASE / "prometheus-aws-datasource.yaml").read_text())["datasources"][0]
    assert source["url"] == "http://127.0.0.1:9090"
    for name in ("business", "operations"):
        dashboard = json.loads((BASE / f"grafana/dashboards/{name}.json").read_text())
        assert all(panel["datasource"]["uid"] == source["uid"] for panel in dashboard["panels"])
    services = yaml.safe_load((BASE / "aws-compose.yaml").read_text())["services"]
    assert "--web.listen-address=127.0.0.1:9090" in services["prometheus"]["command"]
    assert services["grafana"]["environment"]["GF_SERVER_HTTP_ADDR"] == "127.0.0.1"
    assert "--listen_ip=127.0.0.1" in services["cadvisor"]["command"]


def test_dashboards_have_eight_panels_and_the_same_datasource():
    for name in ("business", "operations"):
        dashboard = json.loads((BASE / f"grafana/dashboards/{name}.json").read_text())
        assert len(dashboard["panels"]) == 8
        assert all(p["datasource"]["uid"] == "nafta2go-prometheus" for p in dashboard["panels"])
    rules = json.loads((BASE / "grafana/provisioning/alerting/rules.json").read_text())
    assert len(rules["groups"][0]["rules"]) == 3


def test_no_public_metrics_ports_or_secrets_in_provisioning():
    compose = yaml.safe_load((ROOT / "compose.yaml").read_text())
    for name in ("grafana", "prometheus", "cadvisor"):
        service = compose["services"][name]
        assert service["profiles"] == ["observabilidad"]
        assert all(port.startswith("127.0.0.1:") for port in service.get("ports", []))
    assert not compose["services"]["cadvisor"].get("ports")
    prometheus = yaml.safe_load((BASE / "prometheus.yml").read_text())
    assert prometheus["scrape_configs"][0]["authorization"]["credentials_file"].startswith(
        "/run/secrets/"
    )


def test_prepare_keeps_parent_private_and_never_accepts_empty_credentials(tmp_path):
    directory = tmp_path / "private"
    prepare(directory, "admin", "password-for-local-qa")
    assert directory.stat().st_mode & 0o777 == 0o700
    assert (directory / "api_admin_token").read_text() == "admin"
    with pytest.raises(ValueError):
        prepare(directory, "", "short")
