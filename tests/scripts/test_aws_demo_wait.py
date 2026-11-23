"""Nunca dar por aprobado un despliegue hasta que SSM confirme éxito."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from scripts.aws_demo_wait import wait

INSTANCE, COMMAND = "i-12345678", "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


def result(status):
    return SimpleNamespace(returncode=0, stdout=json.dumps({"Status": status}), stderr="")


def test_waits_for_visibility_and_success_without_a_personal_profile():
    run = Mock(
        side_effect=[
            SimpleNamespace(returncode=1, stderr="InvocationDoesNotExist"),
            result("Pending"),
            result("InProgress"),
            result("Success"),
        ]
    )
    wait(INSTANCE, COMMAND, run=run, sleep=lambda _: None)
    assert run.call_count == 4
    assert "--profile" not in run.call_args.args[0]


@pytest.mark.parametrize("status", ["Failed", "Cancelled", "TimedOut", "Cancelling"])
def test_failed_smoke_is_not_a_successful_deployment(status):
    with pytest.raises(RuntimeError):
        wait(INSTANCE, COMMAND, run=lambda *a, **kw: result(status))


def test_timeout_and_bad_target_never_wait_forever():
    with pytest.raises(TimeoutError):
        wait(INSTANCE, COMMAND, timeout=1, clock=Mock(side_effect=[0, 2]))
    run = Mock()
    with pytest.raises(ValueError):
        wait(INSTANCE, COMMAND + ";id", run=run)
    run.assert_not_called()
