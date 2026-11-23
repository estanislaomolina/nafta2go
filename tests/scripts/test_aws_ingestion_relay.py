"""Ejecutar el receptor real con transporte y contenedor sustituidos, sin AWS."""

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from nafta2go.adapters.capture_relay import receipt_for
from nafta2go.normalization.rules import LOCAL_TIMEZONE
from nafta2go.persistence.models import RawCapture

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("mode", ["success", "download_failed", "tampered"])
def test_receiver_preserves_originals_and_imports_only_verified_bytes(tmp_path, mode):
    base = tmp_path / "host"
    (base / "private").mkdir(parents=True)
    (base / "private/runtime.env").touch()
    (base / "current-image").write_text("nafta2go:test")
    source = tmp_path / "source.csv"
    source.write_bytes((ROOT / "tests/fixtures/vigente_sample.csv").read_bytes())
    capture = RawCapture(
        "vigente",
        "http://datos.energia.gob.ar/vigente.csv",
        hashlib.sha256(source.read_bytes()).hexdigest(),
        source.stat().st_size,
        str(source),
        datetime.now(ZoneInfo(LOCAL_TIMEZONE)).replace(tzinfo=None),
    )
    receipt = tmp_path / "receipt.json"
    receipt.write_text(
        json.dumps(
            receipt_for(
                capture,
                "https://github.com/estanislaomolina/nafta2go/actions/runs/123",
                "a" * 40,
            )
        )
    )
    commands = tmp_path / "bin"
    commands.mkdir()
    stubs = {
        "aws": """
import os, shutil, sys
from pathlib import Path
key = sys.argv[sys.argv.index('--key') + 1]
if key.endswith('.csv') and os.environ['RELAY_MODE'] == 'download_failed':
    sys.exit(1)
src = os.environ['RELAY_RECEIPT'] if key.endswith('.json') else os.environ['RELAY_CSV']
shutil.copyfile(src, sys.argv[-1])
if key.endswith('.csv') and os.environ['RELAY_MODE'] == 'tampered':
    Path(sys.argv[-1]).write_text('corrupto')
""",
        "chown": "# No cambiar propietarios reales en la prueba.\n",
        "docker": """
import os, subprocess, sys
from pathlib import Path
Path(os.environ['RELAY_DOCKER_CALLED']).touch()
args = sys.argv[sys.argv.index('python') + 1:]
args = [s.replace('/app/data/', os.environ['NAFTA2GO_DEPLOY_BASE'] + '/data/') for s in args]
sys.exit(subprocess.run([os.environ['RELAY_PYTHON'], *args]).returncode)
""",
    }
    for name, body in stubs.items():
        path = commands / name
        path.write_text(f"#!/usr/bin/env python3\n{body}")
        path.chmod(0o700)
    database = tmp_path / "ingestion.db"
    called = tmp_path / "docker-called"
    result = subprocess.run(
        ["bash", str(ROOT / "deploy/aws-ingestion-relay.sh")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=20,
        env=dict(
            os.environ,
            PATH=f"{commands}:{os.environ['PATH']}",
            NAFTA2GO_DEPLOY_BASE=str(base),
            NAFTA2GO_CAPTURE_BUCKET="test-captures",
            RELAY_MODE=mode,
            RELAY_CSV=str(source),
            RELAY_RECEIPT=str(receipt),
            RELAY_DOCKER_CALLED=str(called),
            RELAY_PYTHON=sys.executable,
            DATABASE_URL=f"sqlite:///{database}",
        ),
    )
    transfers = list((base / "data/imports").glob("relay-*"))
    if mode == "download_failed":
        assert result.returncode != 0
        assert not called.exists()
        assert transfers == []
        assert not database.exists()
    else:
        assert called.exists(), result.stderr
        # Conservar los originales también en fallos posteriores al inicio del importador.
        assert len(transfers) == 1
        assert (transfers[0] / "receipt.json").exists()
        summary = json.loads(result.stdout)
        assert summary["status"] == ("succeeded" if mode == "success" else "failed")
        assert result.returncode == (0 if mode == "success" else 1)
        if mode == "success":
            assert (transfers[0] / "capture.csv").read_bytes() == source.read_bytes()
            assert summary["report"]["acquisition_provenance"]["method"] == "github-actions-s3"
