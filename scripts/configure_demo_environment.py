"""Aplicar protecciones de demo; requiere permisos administrativos en GitHub."""

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENDPOINT = "repos/estanislaomolina/nafta2go/environments/demo"


def main():
    def call(method, path, body=None):
        args = ["gh", "api", "--method", method, path]
        if body is not None:
            args += ["--input", "-"]
        result = subprocess.run(
            args,
            input=json.dumps(body) if body is not None else None,
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(result.stdout)

    settings = json.loads((ROOT / "infra/github/demo-environment.json").read_text())
    desired = json.loads((ROOT / "infra/github/demo-branches.json").read_text())
    call("PUT", ENDPOINT, settings)
    endpoint = ENDPOINT + "/deployment-branch-policies"
    current = call("GET", endpoint)["branch_policies"]
    allowed = {(rule["name"], rule["type"]) for rule in desired}
    if any((rule["name"], rule["type"]) not in allowed for rule in current):
        raise RuntimeError("Hay reglas adicionales: revisarlas antes de desplegar")
    for rule in desired:
        if (rule["name"], rule["type"]) not in {(r["name"], r["type"]) for r in current}:
            call("POST", endpoint, rule)
    print("Environment demo protegido; verificar revisores y ramas en GitHub")


if __name__ == "__main__":
    main()
