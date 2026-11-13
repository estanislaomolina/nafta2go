"""Prueba Docker aislada; elimina únicamente el proyecto temporal que crea."""

import argparse
import json
import os
import secrets
import subprocess
import tempfile
from pathlib import Path

PROBE = """
import os
import requests
from nafta2go.application.coverage_rules import configured_max_price_age_days
assert configured_max_price_age_days() == 14
from nafta2go.adapters.recorded_routes import shared_cache
cache = shared_cache()
assert (cache.ttl, cache.capacity, cache.per_minute, cache.per_day) == (19, 17, 2, 9)
base = 'http://127.0.0.1:8000'
assert requests.get(base + '/ready', timeout=3).status_code == 200
html = requests.get(base + '/', timeout=3)
assert html.status_code == 200 and 'Nafta2Go' in html.text
assert requests.get(base + '/assets/app.js', timeout=3).status_code == 200
assert requests.get(base + '/operacion', timeout=3).status_code == 200
assert requests.get(base + '/assets/operation.js', timeout=3).status_code == 200
denied = requests.post(base + '/api/v1/recommendations?token=private-probe', json={}, timeout=3)
assert denied.status_code == 401 and denied.headers['x-request-id']
metrics = requests.get(base + '/api/v1/operations', timeout=3,
    headers={'Authorization': 'Bearer ' + os.environ['NAFTA2GO_API_TOKEN']}).json()
assert metrics['queries']['http_status'] == {'401': 1}
assert requests.get(base + '/api/v1/operations/ingestion', timeout=3).status_code == 401
ingestion = requests.get(base + '/api/v1/operations/ingestion', timeout=3,
    headers={'Authorization': 'Bearer ' + os.environ['NAFTA2GO_API_TOKEN']}).json()
assert ingestion['status'] == 'alerting' and ingestion['latest_successful'] is None
assert ingestion['conditions'][0]['kind'] == 'missing'
schema = requests.get(base + '/openapi.json', timeout=3).json()
field = schema['components']['schemas']['RecommendationInput']['properties']['max_candidates']
assert field['maximum'] == 20
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="nafta2go:local", help="Imagen ya construida localmente")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    environment = os.environ | {
        "NAFTA2GO_API_TOKEN": secrets.token_urlsafe(32),
        "ORS_API_KEY": "",
        "ORS_CACHE_TTL_SECONDS": "19",
        "ORS_CACHE_MAX_ENTRIES": "17",
        "ORS_REQUESTS_PER_MINUTE": "2",
        "ORS_REQUESTS_PER_DAY": "9",
        "NAFTA2GO_MAX_PRICE_AGE_DAYS": "14",
    }
    with tempfile.TemporaryDirectory(prefix="nafta2go-compose-qa-") as directory:
        override = Path(directory) / "override.yaml"
        settings = f"    image: {json.dumps(args.image)}\n    pull_policy: never\n"
        services = "".join(f"  {name}:\n{settings}" for name in ("migrate", "query", "api"))
        override.write_text("services:\n" + services + "    ports: !reset []\n")
        command = [
            "docker",
            "compose",
            "-p",
            f"nafta2go-integracion-{os.getpid()}",
            "-f",
            str(root / "compose.yaml"),
            "-f",
            str(override),
            "--profile",
            "mvp",
            "--profile",
            "poc",
        ]
        options = {"env": environment, "cwd": root}
        try:
            subprocess.run(
                [*command, "up", "--no-build", "--wait", "--wait-timeout", "30", "api"],
                check=True,
                **options,
            )
            subprocess.run(
                [*command, "exec", "-T", "api", "python", "-c", PROBE], check=True, **options
            )
            logs = subprocess.run(
                [*command, "logs", "--no-log-prefix", "api"],
                check=True,
                text=True,
                capture_output=True,
                **options,
            ).stdout
            assert '"event": "query_completed"' in logs and "private-probe" not in logs
            assert environment["NAFTA2GO_API_TOKEN"] not in logs
            policy_query = subprocess.run(
                [*command, "run", "--rm", "--no-deps", "query", "--origin=-34.71,-58.33", "--json"],
                check=True,
                text=True,
                capture_output=True,
                **options,
            )
            policy_result = json.loads(policy_query.stdout)
            assert policy_result["query"]["max_price_age_days"] == 14
            assert policy_result["outcome"] == "insufficient_coverage"
            output = subprocess.run(
                [
                    *command,
                    "run",
                    "--rm",
                    "--no-deps",
                    "-e",
                    "NAFTA2GO_MAX_PRICE_AGE_DAYS=30",
                    "query",
                    "--origin=-34.6037,-58.3816",
                    "--destination=-34.5627,-58.4565",
                    "--matrix-file",
                    "docs/evidencia/poc-05-flujo-2026-10-26/matrix.json",
                    "--json",
                ],
                check=True,
                text=True,
                capture_output=True,
                **options,
            )
            result = json.loads(output.stdout)
            assert result["status"] == "historical_scenario" and result["outcome"] == "recommended"
            assert len(result["evaluations"]) == 10 and result["recommendation_id"] is not None
            assert result["routes"]["replayed"] and result["navigation"]
            assert result["query"]["max_price_age_days"] == 30
            cli_events = [
                json.loads(line)
                for line in output.stderr.splitlines()
                if line.startswith('{"event":')
            ]
            assert len(cli_events) == 1
            assert cli_events[0]["channel"] == "cli" and cli_events[0]["exit_code"] == 0
            assert cli_events[0]["outcome"] == "recommended"
            assert "-34.6037" not in output.stderr and "-58.4565" not in output.stderr
        finally:
            subprocess.run([*command, "down", "--volumes"], check=True, **options)
    print(
        json.dumps(
            {
                "api_web_ready": True,
                "cache_environment_forwarded": True,
                "historical_evaluations": len(result["evaluations"]),
                "host_ports_published": False,
                "temporary_resources_removed": True,
            }
        )
    )


if __name__ == "__main__":
    main()
