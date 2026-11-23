"""La publicación sólo puede distribuir el artefacto que aprobó los checks."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_publication_waits_for_all_checks_and_cannot_run_on_pr():
    workflow = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())
    publish = workflow["jobs"]["publish"]
    assert set(publish["needs"]) == set(workflow["jobs"]) - {"publish", "deploy"}
    assert publish["if"] == "github.event_name == 'push'"
    assert workflow["permissions"] == {"contents": "read"}
    assert publish["permissions"] == {"contents": "read", "packages": "write"}
    assert all(
        job.get("permissions", {}).get("packages") != "write"
        for name, job in workflow["jobs"].items()
        if name != "publish"
    )


def test_published_image_is_loaded_from_successful_container_job():
    workflow = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())
    containers, publish = (workflow["jobs"][name] for name in ("containers", "publish"))
    assert containers["env"]["NAFTA2GO_IMAGE"] == publish["env"]["NAFTA2GO_IMAGE"]
    steps = containers["steps"]
    smoke_index = next(
        i for i, step in enumerate(steps) if "compose_smoke.py" in step.get("run", "")
    )
    save_index = next(i for i, step in enumerate(steps) if "docker save" in step.get("run", ""))
    assert smoke_index < save_index
    upload = next(
        step for step in steps if step.get("uses", "").startswith("actions/upload-artifact@")
    )
    download = publish["steps"][0]
    assert upload["with"]["name"] == download["with"]["name"]
    assert all("build" not in step.get("run", "") for step in publish["steps"])
    commands = "\n".join(step.get("run", "") for step in publish["steps"])
    assert "docker load" in commands and "docker push" in commands
    assert 'docker pull "$digest_ref"' in commands
