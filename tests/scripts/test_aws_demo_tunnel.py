"""Quick no requiere token; managed sólo transporta el nombre y rechaza inyección."""

import base64
import subprocess

import pytest

from scripts.aws_demo_tunnel import ROOT, request


def test_quick_has_no_credential_parameter_and_bundles_a_pinned_installer():
    result = request("i-12345678")
    assert result["InstanceIds"] == ["i-12345678"]
    commands = result["Parameters"]["commands"]
    assert commands[-1].endswith("quick")
    installer = base64.b64decode(commands[3].split("'")[3]).decode()
    assert "sha256sum --check --status" in installer and "2026.11.1" in installer
    subprocess.run(["bash", "-n"], input=installer, text=True, check=True)
    unit = (ROOT / "deploy/nafta2go-tunnel.service").read_text()
    assert "DynamicUser=yes" in unit and "--protocol http2" in unit
    assert "token" not in unit
    subprocess.run(
        ["systemd-analyze", "verify", str(ROOT / "deploy/nafta2go-tunnel.service")], check=True
    )


def test_managed_only_uses_a_parameter_reference():
    result = request("i-12345678", "managed", "/nafta2go/demo/cloudflare")
    assert result["Parameters"]["commands"][-1].endswith("managed /nafta2go/demo/cloudflare")
    assert "LoadCredential=" in (ROOT / "deploy/nafta2go-tunnel-managed.conf").read_text()


@pytest.mark.parametrize(
    "instance,mode,parameter",
    [
        ("i-12345678;id", "quick", None),
        ("i-12345678", "other", None),
        ("i-12345678", "managed", None),
        ("i-12345678", "managed", "/nafta2go/demo/x;id"),
        ("i-12345678", "quick", "/nafta2go/demo/unused"),
    ],
)
def test_invalid_parameters_never_produce_a_command(instance, mode, parameter):
    with pytest.raises(ValueError):
        request(instance, mode, parameter)
