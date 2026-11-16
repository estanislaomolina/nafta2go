"""Reintentos finitos de adquisición remota; nunca repiten la normalización."""

import logging
import time
from collections.abc import Callable
from dataclasses import replace

import requests

from nafta2go.adapters.energy_source import IncompleteDownload
from nafta2go.domain.acquisition import AcquisitionFailed
from nafta2go.persistence.models import RawCapture

RETRY_DELAYS = (60, 120)
logger = logging.getLogger(__name__)


def acquire_with_retries(
    acquire: Callable[[], RawCapture],
    source: str,
    sleep: Callable[[float], None] | None = None,
) -> RawCapture:
    pause = time.sleep if sleep is None else sleep
    for attempt in range(1, len(RETRY_DELAYS) + 2):
        try:
            capture = acquire()
        except Exception as exc:
            delay = (
                RETRY_DELAYS[attempt - 1]
                if attempt <= len(RETRY_DELAYS) and _transient(exc)
                else None
            )
            logger.warning(
                "fallo de adquisición remota: origen=%s intento=%s tipo=%s próxima_espera=%s",
                source,
                attempt,
                type(exc).__name__,
                delay,
                extra={
                    "source": source,
                    "attempt": attempt,
                    "error_type": type(exc).__name__,
                    "retry_in_seconds": delay,
                },
            )
            if delay is None:
                raise AcquisitionFailed(attempt, type(exc).__name__) from exc
            pause(delay)
        else:
            return replace(capture, acquisition_attempts=attempt)
    raise AssertionError("Límite de intentos no respetado")


def _transient(exc: Exception) -> bool:
    if isinstance(exc, (requests.exceptions.SSLError, requests.exceptions.ProxyError)):
        return False
    if isinstance(exc, requests.HTTPError):
        response = exc.response
        return (
            response is not None
            and response.status_code in (502, 503, 504)
            and "Retry-After" not in response.headers
        )
    return isinstance(
        exc,
        (
            requests.ConnectionError,
            requests.Timeout,
            requests.exceptions.ChunkedEncodingError,
            IncompleteDownload,
        ),
    )
