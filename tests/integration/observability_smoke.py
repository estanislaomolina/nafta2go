"""QA local reproducible del perfil; base/secretos temporales y rutas grabadas.

PYTHONPATH=. python tests/integration/observability_smoke.py --evidence /tmp/evidencia-nueva
No consume ORS ni reutiliza volúmenes de demo. Requiere Docker Compose en Linux.
"""

import argparse
import json
import os
import secrets
import socket
import subprocess
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

import requests

from scripts.prepare_observability_secrets import prepare

ROOT = Path(__file__).resolve().parents[2]
SERVER = """
from pathlib import Path
import uvicorn
from nafta2go.presentation.http import create_app
from nafta2go.adapters.recorded_routes import RecordedRoutes
uvicorn.run(create_app(provider_factory=lambda: RecordedRoutes(
    Path('docs/evidencia/poc-05-flujo-2026-10-26/matrix.json')),
    routing_provider='openrouteservice-recorded'), host='0.0.0.0', port=8000,
    access_log=False, log_config='deploy/logging.json')
"""
QUERY_PROBE = """
import os,time,requests
body={'origin':{'lat':-34.6037,'lon':-58.3816},'destination':{'lat':-34.5627,'lon':-58.4565},
      'fuel_type':'super','consumption_l_per_100km':'10','tank_capacity_l':'50',
      'remaining_l':'10','budget_ars':'12000','reserve_l':'2'}
for i in range(8):
    r=requests.post('http://127.0.0.1:8000/api/v1/recommendations',json=body,
      headers={'Authorization':'Bearer '+os.environ['NAFTA2GO_API_TOKEN']},timeout=10)
    assert r.status_code==200 and len(r.json()['evaluations'])==10
    time.sleep(4)
"""


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--screenshots", action="store_true")
    args = parser.parse_args()
    args.evidence.mkdir(parents=True, exist_ok=False)
    project = f"nafta2go-observability-qa-{os.getpid()}"
    prometheus_port, grafana_port = free_port(), free_port()
    with tempfile.TemporaryDirectory(prefix=project) as temporary:
        directory = Path(temporary)
        token, password, driver = (secrets.token_urlsafe(32) for _ in range(3))
        prepare(directory / "private", token, password)
        env = os.environ | {
            "NAFTA2GO_API_TOKEN": driver,
            "NAFTA2GO_ADMIN_TOKEN": token,
            "ORS_API_KEY": "",
            "NAFTA2GO_METRICS_TOKEN_FILE": str(directory / "private/api_admin_token"),
            "NAFTA2GO_GRAFANA_PASSWORD_FILE": str(directory / "private/grafana_admin_password"),
        }
        override = {"services": {name: {"image": project} for name in ("api", "query", "migrate")}}
        # Los tags YAML !reset/!override son extensiones de Docker Compose.
        settings = json.dumps(["python", "-c", SERVER])
        content = "services:\n"
        for name in ("migrate", "query", "api"):
            content += f"  {name}:\n    image: {project}\n"
            if name == "api":
                content += f"    ports: !reset []\n    command: {settings}\n"
        content += f'  grafana:\n    ports: !override ["127.0.0.1:{grafana_port}:3000"]\n'
        content += f'  prometheus:\n    ports: !override ["127.0.0.1:{prometheus_port}:9090"]\n'
        override = directory / "override.yaml"
        override.write_text(content)
        command = [
            "docker",
            "compose",
            "-p",
            project,
            "-f",
            str(ROOT / "compose.yaml"),
            "-f",
            str(override),
            "--profile",
            "mvp",
            "--profile",
            "observabilidad",
        ]

        def run(*arguments):
            subprocess.run([*command, *arguments], cwd=ROOT, env=env, check=True)

        try:
            run("up", "--build", "--wait", "--wait-timeout", "60", "grafana")
            run("exec", "-T", "api", "python", "-c", QUERY_PROBE)
            grafana = f"http://127.0.0.1:{grafana_port}"
            prometheus = f"http://127.0.0.1:{prometheus_port}"
            time.sleep(17)
            checked = {}
            for name in ("business", "operations"):
                r = requests.get(
                    grafana + "/api/dashboards/uid/nafta2go-" + name,
                    auth=("admin", password),
                    timeout=10,
                )
                r.raise_for_status()
                assert len(r.json()["dashboard"]["panels"]) == 8
                for panel in r.json()["dashboard"]["panels"]:
                    for target in panel["targets"]:
                        expression = target["expr"].replace("$project", project)
                        response = requests.get(
                            prometheus + "/api/v1/query", params={"query": expression}, timeout=10
                        )
                        response.raise_for_status()
                        assert response.json()["status"] == "success"
                        checked[panel["title"] + target["refId"]] = len(
                            response.json()["data"]["result"]
                        )
            rules = requests.get(
                grafana + "/api/v1/provisioning/alert-rules", auth=("admin", password), timeout=10
            )
            rules.raise_for_status()
            assert len(rules.json()) == 3
            proof = {
                "observed_at_utc": datetime.now(UTC).isoformat(),
                "scope": "local_isolated_recorded_routes",
                "http_recommendations": 8,
                "alert_rules": 3,
                "queries": checked,
                "project": project,
            }
            if args.screenshots:
                subprocess.run(
                    [
                        "node",
                        str(ROOT / "tests/browser/grafana-capture.cjs"),
                        grafana,
                        str(directory / "private/grafana_admin_password"),
                        str(args.evidence.resolve()),
                        project,
                    ],
                    check=True,
                    env=env,
                )
            (args.evidence / "verificacion.json").write_text(json.dumps(proof, indent=2) + "\n")
        finally:
            run("down", "--volumes")


if __name__ == "__main__":
    main()
