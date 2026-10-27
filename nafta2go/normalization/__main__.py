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

from nafta2go.adapters.energy_source import discover_resources, download
from nafta2go.normalization.pipeline import normalize_capture
from nafta2go.normalization.rules import LOCAL_TIMEZONE, SOURCES
from nafta2go.persistence import repository as repo
from nafta2go.persistence.database import ROOT, create_db_engine, database_url, upgrade_to_head
from nafta2go.persistence.models import RawCapture
from nafta2go.services.ingestion import IngestionFailed, ingest

DATA_DIR = ROOT / "data"
HASH_CHUNK = 1024 * 1024


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.file is None:
        session = requests.Session()
        resource = discover_resources(session)[args.source]
        capture = download(resource, args.source, DATA_DIR, session)
    else:
        capture = capture_from_file(args.file, args.source)

    url = database_url()
    upgrade_to_head(url)
    engine = create_db_engine(url)
    try:
        run_id = ingest(engine, capture, normalize_capture)
        with engine.connect() as conn:
            report = repo.get_run(conn, run_id)["report"]
    except IngestionFailed as exc:
        print(exc, file=sys.stderr)
        return 1
    finally:
        engine.dispose()

    print(f"run_id: {run_id}")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


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
    return parser


if __name__ == "__main__":
    sys.exit(main())
