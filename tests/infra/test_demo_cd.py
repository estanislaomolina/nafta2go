"""La confianza OIDC y el environment restringen juntos quién despliega."""

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_role_trust_is_exact_and_permissions_cannot_modify_other_instances():
    template = json.loads((ROOT / "infra/aws/demo-cd.json").read_text())
    role = template["Resources"]["DeployRole"]["Properties"]
    (statement,) = role["AssumeRolePolicyDocument"]["Statement"]
    conditions = statement["Condition"]["StringEquals"]
    assert conditions["token.actions.githubusercontent.com:aud"] == "sts.amazonaws.com"
    assert conditions["token.actions.githubusercontent.com:sub"] == (
        "repo:estanislaomolina@129418393/nafta2go@1375908771:environment:demo"
    )
    policies = role["Policies"][0]["PolicyDocument"]["Statement"]
    assert not any("iam:" in json.dumps(policy) for policy in policies)
    for policy in policies:
        if policy["Action"] in ("ssm:SendCommand", "ec2:StartInstances"):
            assert "${InstanceId}" in json.dumps(policy["Resource"])
            assert policy["Resource"] != "*"


def test_deploy_requires_environment_and_the_published_artifact():
    workflow = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())
    deploy = workflow["jobs"]["deploy"]
    assert deploy["needs"] == "publish" and deploy["environment"] == "demo"
    assert "refs/heads/main" in deploy["if"] and "refs/tags/entrega-" in deploy["if"]
    assert deploy["permissions"] == {"contents": "read", "id-token": "write"}
    assert not deploy["concurrency"]["cancel-in-progress"]
    settings = json.loads((ROOT / "infra/github/demo-environment.json").read_text())
    assert settings["prevent_self_review"] and not settings["can_admins_bypass"]
    assert settings["reviewers"] == [{"type": "User", "id": 141249883}]
    assert settings["deployment_branch_policy"]["custom_branch_policies"]

    assert json.loads((ROOT / "infra/github/demo-branches.json").read_text()) == [
        {"name": "main", "type": "branch"},
        {"name": "entrega-*", "type": "tag"},
    ]


def test_environment_setup_is_idempotent_and_rejects_extra_rules(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import Mock

    from scripts import configure_demo_environment as setup

    rules = json.loads((ROOT / "infra/github/demo-branches.json").read_text())
    run = Mock(
        side_effect=[
            SimpleNamespace(stdout="{}"),
            SimpleNamespace(stdout=json.dumps({"branch_policies": rules})),
        ]
    )
    monkeypatch.setattr(setup.subprocess, "run", run)
    setup.main()
    assert run.call_count == 2
    run = Mock(
        side_effect=[
            SimpleNamespace(stdout="{}"),
            SimpleNamespace(
                stdout=json.dumps({"branch_policies": [{"name": "*", "type": "branch"}]})
            ),
        ]
    )
    monkeypatch.setattr(setup.subprocess, "run", run)
    import pytest

    with pytest.raises(RuntimeError):
        setup.main()
