"""La confianza OIDC y el environment restringen juntos quién despliega."""

import json
from pathlib import Path

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
