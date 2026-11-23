"""Instalar el servicio HTTPS por SSM, sin transportar credenciales Cloudflare."""

import argparse
import base64
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = ("install-tunnel.sh", "nafta2go-tunnel.service", "nafta2go-tunnel-managed.conf")


def request(instance_id, mode="quick", parameter=None):
    if not re.fullmatch(r"i-(?:[0-9a-f]{8}|[0-9a-f]{17})", instance_id):
        raise ValueError("Instancia inválida")
    if mode not in {"quick", "managed"}:
        raise ValueError("Modo inválido")
    if mode == "managed" and not re.fullmatch(r"/nafta2go/demo/[a-zA-Z0-9/_-]+", parameter or ""):
        raise ValueError("El túnel administrado requiere el nombre de SecureString")
    if mode == "quick" and parameter is not None:
        raise ValueError("Quick Tunnel no usa token persistente")
    directory = "/opt/nafta2go-tunnel"
    commands = ["set -eu", "umask 077", "mkdir -p " + directory]
    for name in FILES:
        encoded = base64.b64encode((ROOT / "deploy" / name).read_bytes()).decode()
        commands.append(f"printf '%s' '{encoded}' | base64 -d > {directory}/{name}")
    commands.append(
        f"bash {directory}/install-tunnel.sh {mode}" + (" " + parameter if parameter else "")
    )
    return {
        "DocumentName": "AWS-RunShellScript",
        "InstanceIds": [instance_id],
        "Comment": "Nafta2Go: instalar tunel HTTPS versionado",
        "TimeoutSeconds": 300,
        "Parameters": {"commands": commands, "executionTimeout": ["600"]},
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instance-id", required=True)
    parser.add_argument("--mode", choices=("quick", "managed"), default="quick")
    parser.add_argument("--parameter")
    parser.add_argument("--profile", default="nafta2go")
    parser.add_argument("--aws", default="aws")
    args = parser.parse_args(argv)
    payload = request(args.instance_id, args.mode, args.parameter)
    result = subprocess.run(
        [
            args.aws,
            "ssm",
            "send-command",
            "--region",
            "us-east-2",
            "--profile",
            args.profile,
            "--cli-input-json",
            json.dumps(payload),
            "--query",
            "Command.CommandId",
            "--output",
            "text",
            "--no-cli-pager",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    print(result.stdout.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
