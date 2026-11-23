"""Adquirir y publicar una captura vigente en S3 con identidad de máquina.

El puntero latest.json se publica después del CSV y de validar su calidad.
Un fallo previo al recibo deja el puntero anterior; el consumidor limita su edad.
"""

import argparse
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

import requests

from nafta2go.adapters.acquisition import acquire_with_retries
from nafta2go.adapters.capture_relay import capture_from_receipt, receipt_for
from nafta2go.adapters.energy_source import discover_resources, download
from nafta2go.normalization.pipeline import normalize_capture


def publish(bucket, directory: Path, run_url, commit, run=subprocess.run):
    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", bucket):
        raise ValueError("Nombre de bucket inválido")

    def acquire():
        with requests.Session() as session:
            resource = discover_resources(session)["vigente"]
            return download(resource, "vigente", directory, session)

    capture = acquire_with_retries(acquire, "vigente")
    receipt = directory / "receipt.json"
    receipt.write_text(json.dumps(receipt_for(capture, run_url, commit), sort_keys=True))
    verified = capture_from_receipt(Path(capture.stored_path), receipt)
    result = normalize_capture(verified)
    if not result.rows:
        raise ValueError("La captura no contiene precios utilizables de CABA")
    env = dict(os.environ, AWS_RETRY_MODE="standard", AWS_MAX_ATTEMPTS="3")
    # Cada llamada tiene reintentos acotados y timeout, sin un perfil SSO personal.
    for path, key in (
        (Path(capture.stored_path), f"vigente/{capture.sha256}.csv"),
        (receipt, "vigente/latest.json"),
    ):
        run(
            [
                "aws",
                "s3api",
                "put-object",
                "--region",
                "us-east-2",
                "--bucket",
                bucket,
                "--key",
                key,
                "--body",
                str(path),
                "--server-side-encryption",
                "AES256",
                "--no-cli-pager",
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            env=env,
            timeout=300,
        )
    return {
        "sha256": capture.sha256,
        "size_bytes": capture.size_bytes,
        "valid_rows": len(result.rows),
        "workflow_run": run_url,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bucket", required=True)
    args = parser.parse_args(argv)
    with tempfile.TemporaryDirectory(prefix="nafta2go-capture-") as directory:
        result = publish(
            args.bucket,
            Path(directory),
            f"https://github.com/estanislaomolina/nafta2go/actions/runs/{os.environ['GITHUB_RUN_ID']}",
            os.environ["GITHUB_SHA"],
        )
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
