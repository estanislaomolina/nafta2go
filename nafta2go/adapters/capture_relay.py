"""Recibo verificable de una captura vigente adquirida fuera del host AWS.

Conserva origen y fecha de adquisición; copiar el CSV no renueva su fecha.
El recibo viaja por un canal autenticado (S3 privado), no es una firma del catálogo.
"""

import hashlib
import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from nafta2go.normalization.rules import LOCAL_TIMEZONE
from nafta2go.persistence.models import RawCapture

MAX_AGE = timedelta(hours=36)
MAX_BYTES = 100 * 1024 * 1024
RUN_URL = r"https://github\.com/estanislaomolina/nafta2go/actions/runs/[1-9][0-9]*"


def receipt_for(capture: RawCapture, run_url: str, commit: str) -> dict:
    """Serializa sólo metadatos públicos; el archivo local no viaja en el recibo."""
    fetched = capture.fetched_at.replace(tzinfo=ZoneInfo(LOCAL_TIMEZONE))
    return {
        "schema_version": 1,
        "source": capture.source,
        "url": capture.url,
        "sha256": capture.sha256,
        "size_bytes": capture.size_bytes,
        "fetched_at": fetched.astimezone(UTC).isoformat(),
        "source_last_modified": capture.source_last_modified,
        "acquisition_attempts": capture.acquisition_attempts,
        "workflow_run": run_url,
        "commit": commit,
    }


def read_receipt(path: Path, now: datetime | None = None) -> dict:
    if path.stat().st_size > 16 * 1024:
        raise ValueError("Recibo demasiado grande")
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError("Recibo inválido")
    if data.get("schema_version") != 1 or data.get("source") != "vigente":
        raise ValueError("Versión u origen de recibo no admitido")
    if not re.fullmatch(r"[0-9a-f]{64}", str(data.get("sha256", ""))):
        raise ValueError("SHA-256 inválido")
    if type(data.get("size_bytes")) is not int or not 0 < data["size_bytes"] <= MAX_BYTES:
        raise ValueError("Tamaño de captura inválido")
    if type(data.get("acquisition_attempts")) is not int or not (
        1 <= data["acquisition_attempts"] <= 3
    ):
        raise ValueError("Cantidad de intentos inválida")
    if not re.fullmatch(RUN_URL, str(data.get("workflow_run", ""))):
        raise ValueError("Corrida de adquisición inválida")
    if not re.fullmatch(r"[0-9a-f]{40}", str(data.get("commit", ""))):
        raise ValueError("Commit de adquisición inválido")
    url = urlsplit(data.get("url", ""))
    if (
        url.scheme not in ("http", "https")
        or url.netloc != "datos.energia.gob.ar"
        or url.username
        or url.password
        or url.query
        or url.fragment
    ):
        raise ValueError("Origen de captura no admitido")
    modified = data.get("source_last_modified")
    if modified is not None and (not isinstance(modified, str) or len(modified) > 100):
        raise ValueError("Fecha de fuente inválida")
    try:
        fetched = datetime.fromisoformat(data["fetched_at"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Fecha de adquisición inválida") from exc
    if fetched.tzinfo is None:
        raise ValueError("La adquisición debe indicar zona horaria")
    age = (now or datetime.now(UTC)) - fetched
    if not -timedelta(minutes=5) <= age <= MAX_AGE:
        raise ValueError("Captura adquirida fuera de la ventana permitida")
    return data


def capture_from_receipt(
    csv_path: Path, receipt_path: Path, now: datetime | None = None
) -> RawCapture:
    data = read_receipt(receipt_path, now)
    if csv_path.stat().st_size != data["size_bytes"]:
        raise ValueError("El tamaño recibido no coincide con el recibo")
    with csv_path.open("rb") as raw:
        digest = hashlib.file_digest(raw, "sha256").hexdigest()
    if digest != data["sha256"]:
        raise ValueError("El SHA-256 recibido no coincide con el recibo")
    fetched = datetime.fromisoformat(data["fetched_at"])
    return RawCapture(
        source="vigente",
        url=data["url"],
        sha256=digest,
        size_bytes=data["size_bytes"],
        stored_path=str(csv_path.resolve()),
        fetched_at=fetched.astimezone(ZoneInfo(LOCAL_TIMEZONE)).replace(tzinfo=None),
        source_last_modified=data["source_last_modified"],
        acquisition_attempts=data["acquisition_attempts"],
        provenance={
            "method": "github-actions-s3",
            "workflow_run": data["workflow_run"],
            "commit": data["commit"],
            "receipt_sha256": hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
        },
    )
