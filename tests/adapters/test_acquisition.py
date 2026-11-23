"""Política de reintentos con operaciones falsas y sin esperas reales."""

from datetime import datetime
from unittest.mock import Mock

import pytest
import requests

from nafta2go.adapters.acquisition import acquire_with_retries
from nafta2go.adapters.energy_source import IncompleteDownload
from nafta2go.domain.acquisition import AcquisitionFailed
from nafta2go.persistence.models import RawCapture

CAPTURE = RawCapture(
    "vigente", "https://example.test/file", "b" * 64, 1, "file.csv", datetime(2026, 11, 12)
)


def http_error(status, headers=None):
    response = requests.Response()
    response.status_code = status
    response.headers.update(headers or {})
    return requests.HTTPError("token=secreto", response=response)


@pytest.mark.parametrize(
    "error",
    [
        requests.ConnectionError("DNS"),
        requests.Timeout("timeout"),
        requests.exceptions.ChunkedEncodingError("corte"),
        IncompleteDownload("tamaño"),
        http_error(502),
        http_error(503),
        http_error(504),
    ],
)
def test_transient_failure_recovers_with_finite_backoff(error, caplog):
    operation = Mock(side_effect=[error, error, CAPTURE])
    sleep = Mock()
    captured = acquire_with_retries(operation, "vigente", sleep)
    assert captured.acquisition_attempts == 3
    assert CAPTURE.acquisition_attempts == 1
    assert operation.call_count == 3
    assert [call.args[0] for call in sleep.call_args_list] == [60, 120]
    assert [record.attempt for record in caplog.records] == [1, 2]


@pytest.mark.parametrize(
    "error",
    [
        http_error(400),
        http_error(401),
        http_error(403),
        http_error(404),
        http_error(429),
        http_error(500),
        http_error(503, {"Retry-After": "120"}),
        http_error(503, {"Retry-After": "invalid"}),
        requests.exceptions.SSLError("TLS"),
        requests.exceptions.ProxyError("proxy"),
        requests.HTTPError("sin respuesta"),
        requests.exceptions.InvalidURL("url"),
        ValueError("catálogo"),
        FileNotFoundError("archivo"),
    ],
)
def test_permanent_or_server_directed_failure_is_not_retried(error):
    operation = Mock(side_effect=error)
    sleep = Mock()
    with pytest.raises(AcquisitionFailed) as caught:
        acquire_with_retries(operation, "vigente", sleep)
    assert caught.value.attempts == 1
    assert caught.value.__cause__ is error
    operation.assert_called_once_with()
    sleep.assert_not_called()


def test_exhaustion_is_bounded_and_logs_no_exception_content(caplog):
    operation = Mock(side_effect=requests.ConnectionError("https://secret.test?token=secreto"))
    sleep = Mock()
    with pytest.raises(AcquisitionFailed) as caught:
        acquire_with_retries(operation, "vigente", sleep)
    assert caught.value.attempts == 3
    assert operation.call_count == 3
    assert sleep.call_count == 2
    assert [record.retry_in_seconds for record in caplog.records] == [60, 120, None]
    assert all(f"intento={attempt}" in caplog.text for attempt in (1, 2, 3))
    assert "secreto" not in str(caught.value) + str([r.__dict__ for r in caplog.records])


def test_immediate_success_does_not_wait():
    sleep = Mock()
    assert acquire_with_retries(lambda: CAPTURE, "vigente", sleep).acquisition_attempts == 1
    sleep.assert_not_called()


def test_interruption_is_not_retried():
    operation, sleep = Mock(side_effect=KeyboardInterrupt), Mock()
    with pytest.raises(KeyboardInterrupt):
        acquire_with_retries(operation, "vigente", sleep)
    operation.assert_called_once_with()
    sleep.assert_not_called()
