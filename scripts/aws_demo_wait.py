"""Esperar SSM con timeout explícito, sin imprimir el env ni la salida del host."""

import argparse
import json
import re
import subprocess
import time


def wait(
    instance_id,
    command_id,
    *,
    aws="aws",
    profile=None,
    timeout=1800,
    run=subprocess.run,
    sleep=time.sleep,
    clock=time.monotonic,
):
    if not re.fullmatch(r"i-(?:[0-9a-f]{8}|[0-9a-f]{17})", instance_id):
        raise ValueError("Instancia inválida")
    if not re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", command_id):
        raise ValueError("ID de comando inválido")
    if timeout <= 0:
        raise ValueError("Timeout inválido")
    deadline = clock() + timeout
    while clock() < deadline:
        result = run(
            [
                aws,
                "ssm",
                "get-command-invocation",
                "--region",
                "us-east-2",
                *(["--profile", profile] if profile else []),
                "--command-id",
                command_id,
                "--instance-id",
                instance_id,
                "--output",
                "json",
                "--no-cli-pager",
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode:
            if "InvocationDoesNotExist" not in result.stderr:
                raise RuntimeError("No se pudo consultar el comando SSM")
        else:
            status = json.loads(result.stdout)["Status"]
            if status == "Success":
                return
            if status not in {"Pending", "InProgress", "Delayed"}:
                raise RuntimeError("Despliegue SSM fallido: " + status)
        sleep(10)
    raise TimeoutError("Tiempo de despliegue agotado")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instance-id", required=True)
    parser.add_argument("--command-id", required=True)
    parser.add_argument("--aws", default="aws")
    parser.add_argument("--profile")
    args = parser.parse_args(argv)
    try:
        wait(args.instance_id, args.command_id, aws=args.aws, profile=args.profile)
    except (RuntimeError, TimeoutError, ValueError) as exc:
        print(str(exc))
        return 1
    print("Despliegue y smoke aprobados por SSM")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
