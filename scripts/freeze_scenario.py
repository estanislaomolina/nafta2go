"""Congela el escenario histórico de POC-02 a partir de una captura vigente.

Verifica el SHA-256 de la captura completa, conserva solo las filas de CABA y
nafta con el encabezado original y escribe el recorte y su ficha en
docs/evidencia/escenario-<id>/. Correrlo dos veces produce los mismos bytes.

Uso, desde la raíz del repositorio:

    python scripts/freeze_scenario.py --file data/raw/vigente/<captura>.csv \\
        --sha256 <sha256> --url <url> --fetched-at 2026-10-24T17:57:10
"""

import argparse
import csv
import hashlib
import io
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nafta2go.application.coverage_rules import (  # noqa: E402
    HISTORICAL_SCENARIO_DIR,
    HISTORICAL_SCENARIO_ID,
    HISTORICAL_SCENARIO_REFERENCE_AT,
)
from nafta2go.normalization.rules import CABA_PROVINCE, NAPHTHA_PRODUCTS  # noqa: E402

EXTRACT_NAME = "precios_caba_nafta.csv"
SCENARIO_NAME = "escenario.json"
LICENSE = "CC-BY-4.0"
BOM = "﻿"
_PRODUCT_IDS = {str(product_id) for product_id in NAPHTHA_PRODUCTS}


class ChecksumMismatch(ValueError):
    """La captura no es la que se quiere congelar."""


def freeze(
    source: Path,
    expected_sha256: str,
    url: str,
    fetched_at: datetime,
    out_dir: Path = HISTORICAL_SCENARIO_DIR,
) -> dict:
    content = source.read_bytes()
    actual = hashlib.sha256(content).hexdigest()
    if actual != expected_sha256:
        raise ChecksumMismatch(f"{source.name}: SHA-256 {actual}, se esperaba {expected_sha256}")

    extract, rows = _extract(content.decode("utf-8-sig"))
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / EXTRACT_NAME).write_bytes(extract)
    scenario = {
        "scenario_id": HISTORICAL_SCENARIO_ID,
        "reference_at": HISTORICAL_SCENARIO_REFERENCE_AT.isoformat(),
        "source": {
            "url": url,
            "sha256": actual,
            "bytes": len(content),
            "fetched_at_local": fetched_at.isoformat(),
            "license": LICENSE,
        },
        "extract": {
            "file": EXTRACT_NAME,
            "sha256": hashlib.sha256(extract).hexdigest(),
            "rows": rows,
            "rule": (
                f"provincia == {CABA_PROVINCE!r} (sin distinguir mayúsculas) e idproducto en "
                f"{sorted(_PRODUCT_IDS)}; encabezado y orden de filas del archivo original"
            ),
        },
    }
    text = json.dumps(scenario, ensure_ascii=False, indent=2) + "\n"
    (out_dir / SCENARIO_NAME).write_text(text, encoding="utf-8")
    return scenario


def _extract(text: str) -> tuple[bytes, int]:
    reader = csv.reader(io.StringIO(text, newline=""))
    header = next(reader)
    province, product = header.index("provincia"), header.index("idproducto")
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(header)
    rows = 0
    for row in reader:
        in_scope = row[province].strip().upper() == CABA_PROVINCE
        if in_scope and row[product].strip() in _PRODUCT_IDS:
            writer.writerow(row)
            rows += 1
    return (BOM + out.getvalue()).encode("utf-8"), rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--fetched-at", type=datetime.fromisoformat, required=True)
    parser.add_argument("--out", type=Path, default=HISTORICAL_SCENARIO_DIR)
    args = parser.parse_args(argv)
    try:
        scenario = freeze(args.file, args.sha256, args.url, args.fetched_at, args.out)
    except ChecksumMismatch as exc:
        print(exc, file=sys.stderr)
        return 1
    print(json.dumps(scenario["extract"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
