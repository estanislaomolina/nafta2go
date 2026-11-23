"""Entrega una release revisada por SSM; no recibe ni imprime credenciales.

El parámetro indicado debe ser SecureString y contener el env privado del servidor.
El resultado devuelve sólo el command ID; consultar el estado antes de reintentar.
"""

import argparse
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def request(instance_id, commit, parameter, image, capture_file=None):
    if not re.fullmatch(r"i-(?:[0-9a-f]{8}|[0-9a-f]{17})", instance_id):
        raise ValueError("ID de instancia inválido")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("Se requiere un SHA completo")
    if not re.fullmatch(r"/nafta2go/demo/[a-zA-Z0-9/_-]+", parameter):
        raise ValueError("Nombre de parámetro no admitido")
    if not re.fullmatch(r"ghcr.io/estanislaomolina/nafta2go@sha256:[0-9a-f]{64}", image):
        raise ValueError("Se requiere una imagen de GHCR por digest SHA-256")
    if capture_file is not None and not re.fullmatch(
        r"/app/data/imports/[0-9a-f]{64}\.csv", capture_file
    ):
        raise ValueError("Ruta de captura no admitida")
    capture_arg = " " + capture_file if capture_file else ""
    script = (ROOT / "deploy/aws-demo-release.sh").read_text()
    return {
        "DocumentName": "AWS-RunShellScript",
        "InstanceIds": [instance_id],
        "Comment": "Nafta2Go: instalar release revisada",
        "TimeoutSeconds": 900,
        "Parameters": {
            "commands": [
                f"bash -s -- {commit} {parameter} {image}{capture_arg} <<'NAFTA2GO_RELEASE'\n"
                f"{script}\nNAFTA2GO_RELEASE"
            ],
            "executionTimeout": ["1800"],
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instance-id", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--parameter", required=True)
    parser.add_argument("--image", required=True, help="Referencia GHCR por digest SHA-256")
    parser.add_argument("--capture-file")
    parser.add_argument("--profile", default="nafta2go")
    parser.add_argument("--aws", default="aws")
    args = parser.parse_args(argv)
    payload = request(args.instance_id, args.commit, args.parameter, args.image, args.capture_file)
    # El payload sólo contiene el nombre del parámetro, nunca el env privado.
    result = subprocess.run(
        [
            args.aws,
            "ssm",
            "send-command",
            "--profile",
            args.profile,
            "--region",
            "us-east-2",
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
