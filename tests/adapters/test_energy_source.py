"""Tests del adaptador de la fuente de precios con una sesión HTTP falsa (sin red)."""

import hashlib
from datetime import UTC, datetime

import pytest
import requests

from nafta2go.adapters.energy_source import (
    CATALOG_URL,
    IncompleteDownload,
    Resource,
    discover_resources,
    download,
)

CONTENT = b"idempresa,precio\n6270,2129\n" * 1000
CONTENT_SIZE = len(CONTENT)
NOW = datetime(2026, 10, 24, 21, 30, 5, tzinfo=UTC)


def fixed_clock():
    return NOW


class FakeResponse:
    def __init__(self, payload=None, chunks=(), error=None, status_code=200):
        self._payload = payload
        self._chunks = chunks
        self._error = error
        self.status_code = status_code
        self.closed = False

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def iter_content(self, chunk_size):
        self.chunk_size = chunk_size
        yield from self._chunks
        if self._error is not None:
            raise self._error

    def close(self):
        self.closed = True


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, stream=False, timeout=None):
        self.calls.append({"url": url, "stream": stream, "timeout": timeout})
        return self.response


def resource_entry(name, fmt="CSV", size=9268946):
    return {
        "id": name.lower().replace(" ", "-"),
        "name": name,
        "url": f"http://datos.energia.gob.ar/{name}.csv",
        "format": fmt,
        "last_modified": "2026-10-24T18:00:24",
        "size": size,
    }


def catalog(*resources):
    return FakeResponse({"success": True, "result": {"resources": list(resources)}})


VIGENTE = resource_entry("Precios vigentes en surtidor - Resolución 314/2016")
HISTORICO = resource_entry("Precios históricos", size=778654156)


def resource(size=CONTENT_SIZE):
    return Resource(
        id="r1",
        name="Precios vigentes",
        url="http://datos.energia.gob.ar/vigentes.csv",
        last_modified="2026-10-24T18:00:24",
        size=size,
    )


def chunks(content=CONTENT, size=1000):
    return [content[i : i + size] for i in range(0, len(content), size)]


def test_discovers_vigente_and_historico():
    session = FakeSession(catalog(VIGENTE, HISTORICO))
    found = discover_resources(session)
    assert session.calls[0]["url"] == CATALOG_URL
    assert found["vigente"].name == VIGENTE["name"]
    assert found["historico"].url == HISTORICO["url"]
    assert found["historico"].size == 778654156
    assert found["vigente"].last_modified == "2026-10-24T18:00:24"


def test_ignores_resources_that_are_not_csv():
    pdf = resource_entry("Precios vigentes - diccionario", fmt="PDF")
    found = discover_resources(FakeSession(catalog(pdf, VIGENTE, HISTORICO)))
    assert found["vigente"].name == VIGENTE["name"]


def test_missing_resource_raises_lookup():
    with pytest.raises(LookupError, match="historico"):
        discover_resources(FakeSession(catalog(VIGENTE)))


def test_download_stores_raw_and_returns_capture(tmp_path):
    session = FakeSession(FakeResponse(chunks=chunks()))
    capture = download(resource(), "vigente", tmp_path, session, clock=fixed_clock)
    sha = hashlib.sha256(CONTENT).hexdigest()
    stored = tmp_path / "raw" / "vigente" / f"20261024T213005Z_{sha[:12]}.csv"
    assert capture.stored_path == str(stored)
    assert stored.read_bytes() == CONTENT
    assert capture.sha256 == sha
    assert capture.size_bytes == len(CONTENT)
    assert capture.source == "vigente"
    assert capture.url == "http://datos.energia.gob.ar/vigentes.csv"
    assert capture.source_last_modified == "2026-10-24T18:00:24"
    # Hora local de Argentina sin zona, comparable con las fechas de la fuente.
    assert capture.fetched_at == datetime(2026, 10, 24, 18, 30, 5)
    assert list(stored.parent.iterdir()) == [stored]


def test_download_streams_with_timeout(tmp_path):
    response = FakeResponse(chunks=chunks())
    session = FakeSession(response)
    download(resource(), "vigente", tmp_path, session, clock=fixed_clock)
    assert session.calls[0]["stream"] is True
    assert session.calls[0]["timeout"] == (10, 300)
    assert response.chunk_size == 1024 * 1024
    assert response.closed


def test_incomplete_download_leaves_no_files(tmp_path):
    session = FakeSession(FakeResponse(chunks=chunks()[:-1]))
    with pytest.raises(IncompleteDownload):
        download(resource(), "vigente", tmp_path, session, clock=fixed_clock)
    assert list((tmp_path / "raw" / "vigente").iterdir()) == []


def test_interrupted_download_leaves_no_files(tmp_path):
    response = FakeResponse(chunks=chunks()[:3], error=requests.ConnectionError("cortado"))
    with pytest.raises(requests.ConnectionError):
        download(resource(), "vigente", tmp_path, FakeSession(response), clock=fixed_clock)
    assert list((tmp_path / "raw" / "vigente").iterdir()) == []
    assert response.closed


def test_http_error_leaves_no_files(tmp_path):
    session = FakeSession(FakeResponse(status_code=503))
    with pytest.raises(requests.HTTPError):
        download(resource(), "vigente", tmp_path, session, clock=fixed_clock)
    assert list((tmp_path / "raw" / "vigente").iterdir()) == []


def test_unknown_size_skips_size_check(tmp_path):
    session = FakeSession(FakeResponse(chunks=chunks()))
    capture = download(resource(size=None), "vigente", tmp_path, session, clock=fixed_clock)
    assert capture.size_bytes == len(CONTENT)
