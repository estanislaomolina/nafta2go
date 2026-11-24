"""Invariantes de aislamiento de la identidad y del canal de capturas."""

import json
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = json.loads((ROOT / "infra/aws/capture-relay.json").read_text())


def test_oidc_denies_pull_requests_other_repositories_and_environments():
    role = TEMPLATE["Resources"]["AcquisitionRole"]["Properties"]
    statements = role["AssumeRolePolicyDocument"]["Statement"]
    assert len(statements) == 1
    conditions = statements[0]["Condition"]["StringEquals"]
    assert conditions["token.actions.githubusercontent.com:aud"] == "sts.amazonaws.com"
    prefix = "repo:estanislaomolina@129418393/nafta2go@1375908771:"
    subjects = conditions["token.actions.githubusercontent.com:sub"]
    assert set(subjects) == {prefix + f"ref:refs/heads/{b}" for b in ("main", "dev")}
    for denied in ("pull_request", "environment:demo", "ref:refs/heads/feature"):
        assert prefix + denied not in subjects
    assert prefix.replace("1375908771", "999") + "ref:refs/heads/main" not in subjects


@pytest.mark.parametrize(
    "role,action", [("AcquisitionRole", "s3:PutObject"), ("HostReadPolicy", "s3:GetObject")]
)
def test_roles_cannot_change_infrastructure_delete_or_cross_the_capture_prefix(role, action):
    properties = TEMPLATE["Resources"][role]["Properties"]
    policy = (
        properties.get("Policies", [{}])[0].get("PolicyDocument") or properties["PolicyDocument"]
    )
    assert len(policy["Statement"]) == 1
    statement = policy["Statement"][0]
    assert statement["Action"] == action
    assert statement["Effect"] == "Allow"
    resources = {resource["Fn::Sub"] for resource in statement["Resource"]}
    assert resources == {"${Captures.Arn}/vigente/*.csv", "${Captures.Arn}/vigente/latest.json"}


def test_storage_is_private_encrypted_and_retained_after_stack_deletion():
    bucket = TEMPLATE["Resources"]["Captures"]
    assert bucket["DeletionPolicy"] == bucket["UpdateReplacePolicy"] == "Retain"
    props = bucket["Properties"]
    assert all(props["PublicAccessBlockConfiguration"].values())
    assert props["OwnershipControls"]["Rules"] == [{"ObjectOwnership": "BucketOwnerEnforced"}]
    assert (
        props["BucketEncryption"]["ServerSideEncryptionConfiguration"][0][
            "ServerSideEncryptionByDefault"
        ]["SSEAlgorithm"]
        == "AES256"
    )
    denial = TEMPLATE["Resources"]["TransportPolicy"]["Properties"]["PolicyDocument"]["Statement"][
        0
    ]
    assert denial["Effect"] == "Deny"
    assert denial["Condition"]["Bool"]["aws:SecureTransport"] == "false"


def test_acquisition_has_no_environment_or_sso_dependency_and_runs_serially():
    workflow = yaml.safe_load((ROOT / ".github/workflows/acquire-prices.yml").read_text())
    job = workflow["jobs"]["acquire"]
    assert "NAFTA2GO_ACQUISITION_RUNNER" in job["runs-on"]
    setup = next(s for s in job["steps"] if s.get("uses") == "actions/setup-python@v5")
    assert setup["if"] == "runner.environment == 'github-hosted'"
    isolation = next(
        s for s in job["steps"] if s.get("name") == "Aislar dependencias de adquisición"
    )
    assert 'python3.12 -m venv "$RUNNER_TEMP/' in isolation["run"]
    assert '"$GITHUB_PATH"' in isolation["run"]
    assert "environment" not in job
    assert job["permissions"] == {"contents": "read", "id-token": "write"}
    assert workflow["concurrency"]["cancel-in-progress"] is False
    assert job["timeout-minutes"] == 20
    text = json.dumps(workflow)
    assert "--profile" not in text
    assert "AWS_ACCESS_KEY_ID" not in text
    assert "AWS_SECRET_ACCESS_KEY" not in text


def test_aws_timers_recover_missed_schedule_without_changing_local_services():
    for name in ("ingestion", "monitor"):
        timer = (ROOT / f"deploy/nafta2go-aws-{name}.timer").read_text()
        assert "Persistent=true" in timer
        assert f"Unit=nafta2go-aws-{name}.service" in timer
    ingestion = (ROOT / "deploy/nafta2go-aws-ingestion.service").read_text()
    assert "OnFailure=nafta2go-aws-monitor.service" in ingestion
    assert "TimeoutStartSec=30min" in ingestion
