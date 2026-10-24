"""Adaptador hacia el catálogo de precios en surtidor de la Secretaría de Energía.

El portal redirige HTTPS a HTTP y ya no ofrece el DataStore: los CSV se bajan
completos por HTTP. La integridad se cubre con el tamaño publicado en el
catálogo y el SHA-256 de lo recibido.
"""

import hashlib
import logging
import os
import tempfile
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from nafta2go.normalization.rules import LOCAL_TIMEZONE
from nafta2go.persistence.models import RawCapture

CATALOG_URL = "http://datos.energia.gob.ar/api/3/action/package_show?id=precios-en-surtidor"
# Conexión y lectura en segundos: el histórico pesa unos 780 MB.
DOWNLOAD_TIMEOUT = (10, 300)
CATALOG_TIMEOUT = (10, 60)
CHUNK_SIZE = 1024 * 1024
# Palabra que identifica a cada recurso en su nombre, en minúscula y sin acentos.
RESOURCE_MARKERS = {"vigente": "vigentes", "historico": "historicos"}

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Resource:
    id: str
    name: str
    url: str
    last_modified: str | None
    size: int | None


class IncompleteDownload(RuntimeError):
    """Los bytes recibidos no coinciden con el tamaño publicado en el catálogo."""


def discover_resources(session: requests.Session) -> dict[str, Resource]:
    response = session.get(CATALOG_URL, timeout=CATALOG_TIMEOUT)
    response.raise_for_status()
    entries = [r for r in response.json()["result"]["resources"] if r.get("format") == "CSV"]

    found = {}
    for source, marker in RESOURCE_MARKERS.items():
        entry = next((r for r in entries if marker in _plain(r.get("name", ""))), None)
        if entry is None:
            raise LookupError(f"El catálogo no tiene el recurso CSV {source!r}")
        found[source] = Resource(
            id=entry["id"],
            name=entry["name"],
            url=entry["url"],
            last_modified=entry.get("last_modified"),
            size=_optional_int(entry.get("size")),
        )
    return found


def download(
    resource: Resource,
    source: str,
    root: Path,
    session: requests.Session,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> RawCapture:
    """Baja el recurso a root/raw/<source>/ sin dejar nunca una captura a medias."""
    target_dir = root / "raw" / source
    target_dir.mkdir(parents=True, exist_ok=True)
    fetched = clock()
    digest = hashlib.sha256()
    received = 0

    handle, part_name = tempfile.mkstemp(dir=target_dir, prefix=".", suffix=".part")
    part = Path(part_name)
    try:
        with os.fdopen(handle, "wb") as out:
            response = session.get(resource.url, stream=True, timeout=DOWNLOAD_TIMEOUT)
            try:
                response.raise_for_status()
                for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                    out.write(chunk)
                    digest.update(chunk)
                    received += len(chunk)
            finally:
                response.close()
        if resource.size is not None and received != resource.size:
            raise IncompleteDownload(
                f"{resource.name}: se recibieron {received} bytes de {resource.size}"
            )
    except BaseException:
        part.unlink(missing_ok=True)
        raise

    sha256 = digest.hexdigest()
    stored = target_dir / f"{fetched.astimezone(UTC):%Y%m%dT%H%M%SZ}_{sha256[:12]}.csv"
    part.replace(stored)
    logger.info("captura descargada", extra={"source": source, "bytes": received, "sha256": sha256})
    return RawCapture(
        source=source,
        url=resource.url,
        sha256=sha256,
        size_bytes=received,
        stored_path=str(stored),
        fetched_at=_local_naive(fetched),
        source_last_modified=resource.last_modified,
    )


def _plain(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _optional_int(value: object) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _local_naive(moment: datetime) -> datetime:
    return moment.astimezone(ZoneInfo(LOCAL_TIMEZONE)).replace(tzinfo=None)
