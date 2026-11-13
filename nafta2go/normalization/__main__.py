"""Ingesta de una captura de precios: python -m nafta2go.normalization --source historico.

Sin --file descubre el recurso en el catálogo y lo descarga a data/raw/. Con
--file usa un CSV ya descargado. En los dos casos normaliza, guarda la
ejecución en la base de DATABASE_URL e imprime el run_id y el reporte.
"""

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from nafta2go.adapters.acquisition import acquire_with_retries
from nafta2go.adapters.energy_source import discover_resources, download
from nafta2go.normalization.pipeline import normalize_capture
from nafta2go.normalization.rules import LOCAL_TIMEZONE, SOURCES
from nafta2go.persistence import repository as repo
from nafta2go.persistence.database import ROOT, create_db_engine, database_url, upgrade_to_head
from nafta2go.persistence.models import RawCapture
from nafta2go.services.ingestion import IngestionFailed, ingest_from_source

DATA_DIR = ROOT / "data"
HASH_CHUNK = 1024 * 1024


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    def acquire() -> RawCapture:
        if args.file is not None:
            return capture_from_file(args.file, args.source)
        return acquire_with_retries(acquire_remote, args.source)

    def acquire_remote() -> RawCapture:
        with requests.Session() as session:
            resource = discover_resources(session)[args.source]
            return download(resource, args.source, DATA_DIR, session)

    url = database_url()
    upgrade_to_head(url)
    engine = create_db_engine(url)
    exit_code = 0
    try:
        try:
            run_id = ingest_from_source(engine, args.source, acquire, normalize_capture)
        except IngestionFailed as exc:
            run_id = exc.run_id
            exit_code = 1
            if not args.json:
                print(exc, file=sys.stderr)
        with engine.connect() as conn:
            run = repo.get_run(conn, run_id)
    finally:
        engine.dispose()

    if args.json:
        # No exportar mensajes arbitrarios de excepciones: pueden incluir URLs o secretos.
        summary = {key: run[key] for key in ("source", "status", "rules_version", "report")}
        summary.update(
            run_id=run_id,
            started_at=run["started_at"].isoformat() + "Z",
            finished_at=run["finished_at"].isoformat() + "Z",
            duration_seconds=(run["finished_at"] - run["started_at"]).total_seconds(),
        )
        print(json.dumps(summary, ensure_ascii=False))
    elif exit_code == 0:
        print(f"run_id: {run_id}")
        print(json.dumps(run["report"], ensure_ascii=False, indent=2))
    return exit_code


def capture_from_file(path: Path, source: str) -> RawCapture:
    """Captura de un CSV ya descargado; fetched_at es su fecha de modificación local."""
    path = path.resolve()
    digest = hashlib.sha256()
    with path.open("rb") as raw:
        while chunk := raw.read(HASH_CHUNK):
            digest.update(chunk)
    return RawCapture(
        source=source,
        url=path.as_uri(),
        sha256=digest.hexdigest(),
        size_bytes=path.stat().st_size,
        stored_path=str(path),
        fetched_at=datetime.fromtimestamp(path.stat().st_mtime, ZoneInfo(LOCAL_TIMEZONE)).replace(
            tzinfo=None
        ),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m nafta2go.normalization", description=__doc__)
    parser.add_argument("--source", required=True, choices=SOURCES)
    parser.add_argument("--file", type=Path, help="CSV ya descargado; si falta, se descarga")
    parser.add_argument("--json", action="store_true", help="Estado, duración y calidad en JSON")
    return parser


if __name__ == "__main__":
    sys.exit(main())
