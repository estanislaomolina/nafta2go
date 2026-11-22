"""El transporte SSM sólo envía referencias; entradas inválidas no llegan a AWS."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from scripts import aws_demo_command as deploy

IMAGE = "ghcr.io/estanislaomolina/nafta2go@sha256:" + "b" * 64
PREVIOUS = "ghcr.io/estanislaomolina/nafta2go@sha256:" + "c" * 64


@pytest.mark.parametrize(
    "field,value",
    [
        ("instance_id", "i-123456789"),
        ("instance_id", "i-12345678;id"),
        ("commit", "dev"),
        ("commit", "a" * 40 + ";id"),
        ("image", "nafta2go:latest"),
        ("image", IMAGE + ";id"),
        ("image", "ghcr.io/otro/repo@sha256:" + "b" * 64),
        ("parameter", "/otro/privado"),
        ("parameter", "/nafta2go/demo/x;id"),
    ],
)
def test_invalid_target_never_executes(field, value, monkeypatch):
    values = dict(instance_id="i-12345678", commit="a" * 40, parameter="/nafta2go/demo/runtime")
    values["image"] = IMAGE
    values[field] = value
    run = Mock()
    monkeypatch.setattr(deploy.subprocess, "run", run)
    with pytest.raises(ValueError):
        deploy.request(**values)
    run.assert_not_called()


def test_send_contains_only_parameter_reference_and_pinned_commit(monkeypatch, capsys):
    run = Mock(return_value=SimpleNamespace(stdout="command-id\n"))
    monkeypatch.setattr(deploy.subprocess, "run", run)
    assert (
        deploy.main(
            [
                "--instance-id",
                "i-12345678",
                "--commit",
                "a" * 40,
                "--parameter",
                "/nafta2go/demo/runtime",
                "--image",
                IMAGE,
            ]
        )
        == 0
    )
    args = run.call_args.args[0]
    payload = json.loads(args[args.index("--cli-input-json") + 1])
    assert payload["InstanceIds"] == ["i-12345678"]
    assert payload["DocumentName"] == "AWS-RunShellScript"
    assert "/nafta2go/demo/runtime" in payload["Parameters"]["commands"][0]
    assert IMAGE in payload["Parameters"]["commands"][0]
    assert "a" * 40 in payload["Parameters"]["commands"][0]
    assert capsys.readouterr().out == "command-id\n"
    assert "--with-decryption" in payload["Parameters"]["commands"][0]


@pytest.mark.parametrize("failure", ["pull", "revision", "start", "readiness", "none"])
def test_release_preserves_or_recovers_previous_service(tmp_path, failure):
    import os
    import subprocess

    base = tmp_path / "server"
    binary = tmp_path / "bin"
    binary.mkdir()
    sha = "a" * 40
    release = base / "releases" / sha
    release.mkdir(parents=True)
    (release / "Dockerfile").write_text("fixture")
    (base / "current-image").write_text(PREVIOUS + "\n")
    state, log = tmp_path / "active", tmp_path / "docker.log"
    state.write_text(PREVIOUS)
    commands = {
        "aws": (
            '#!/bin/sh\nprintf "NAFTA2GO_API_TOKEN=qa-secret\\n'
            'NAFTA2GO_ADMIN_TOKEN=qa-admin\\nORS_API_KEY=qa-ors\\n"\n'
        ),
        "chown": "#!/bin/sh\nexit 0\n",
        "sleep": "#!/bin/sh\nexit 0\n",
        "curl": """#!/usr/bin/env python3
import os,pathlib,sys
active=pathlib.Path(os.environ['QA_STATE']).read_text()
sys.exit(1 if os.environ['QA_FAILURE']=='readiness' and active != os.environ['QA_PREVIOUS'] else 0)
""",
        "docker": """#!/usr/bin/env python3
import os,pathlib,sys
args=sys.argv[1:]
with open(os.environ['QA_LOG'],'a') as file:file.write(' '.join(args)+'\\n')
if args[0]=='pull' and os.environ['QA_FAILURE']=='pull':sys.exit(1)
if args[:2]==['image','inspect']:
 print('incorrect' if os.environ['QA_FAILURE']=='revision' else 'a'*40)
if args[0]=='run' and '--name' in args:
 image=next(a for a in args if a.startswith('ghcr.io/'))
 if os.environ['QA_FAILURE']=='start' and image!=os.environ['QA_PREVIOUS']:sys.exit(1)
 pathlib.Path(os.environ['QA_STATE']).write_text(image)
""",
    }
    for name, content in commands.items():
        script = binary / name
        script.write_text(content)
        script.chmod(0o755)
    env = dict(
        os.environ,
        PATH=str(binary) + os.pathsep + os.environ["PATH"],
        NAFTA2GO_DEPLOY_BASE=str(base),
        QA_STATE=str(state),
        QA_LOG=str(log),
        QA_FAILURE=failure,
        QA_PREVIOUS=PREVIOUS,
    )
    result = subprocess.run(
        [
            "bash",
            str(deploy.ROOT / "deploy/aws-demo-release.sh"),
            sha,
            "/nafta2go/demo/runtime",
            IMAGE,
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    assert "build " not in log.read_text()
    output = result.stdout + result.stderr
    assert "qa-secret" not in output and "qa-admin" not in output and "qa-ors" not in output
    if failure == "none":
        assert result.returncode == 0
        assert state.read_text() == IMAGE
        assert (base / "current-image").read_text().strip() == IMAGE
        assert "-p 127.0.0.1:8000:8000" in log.read_text()
        assert (base / "releases" / (sha + ".image")).read_text().strip() == IMAGE
    else:
        assert result.returncode != 0
        assert state.read_text() == PREVIOUS
        assert (base / "current-image").read_text().strip() == PREVIOUS
        if failure in {"pull", "revision"}:
            assert "rm -f nafta2go-api" not in log.read_text()
        else:
            assert PREVIOUS + " uvicorn" in log.read_text()


def test_transferred_capture_requires_hash_filename():
    values = ("i-12345678", "a" * 40, "/nafta2go/demo/runtime", IMAGE)
    with pytest.raises(ValueError):
        deploy.request(*values, capture_file="/app/data/imports/../../secret")
    path = "/app/data/imports/" + "b" * 64 + ".csv"
    assert path in deploy.request(*values, capture_file=path)["Parameters"]["commands"][0]
