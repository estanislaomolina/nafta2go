"""Servidor HTTP aislado para pruebas de carga (#158), sin red ni cuota de ORS.

Levanta la API real con uvicorn sobre una base SQLite temporal que usa el escenario
histórico del 24/10/2026, y reemplaza ORS por la matriz capturada en POC-05. Con
`--quota-per-minute` las rutas grabadas pasan por la caché y el cupo reales, sin
reutilizar matrices, para comprobar que bajo carga el cupo bloquea en lugar de
agotar la cuota del proveedor.

Con `--source-database` mide el cuello de botella real: copia en modo lectura una
base con las ingestas histórica y vigente, fija el reloj en `--reference-at` y usa
rutas sintéticas, como `measure_real_history_diagnostics` (#152). El modelo se toma
de NAFTA2GO_PRICE_MODEL_DIR; `--model-run` sirve otra corrida auditada en lugar del
campeón, sin modificar el registro versionado.

Uso, desde la raíz del repositorio:

    python scripts/load_server.py --port 8100 --database /tmp/carga.db
"""

import argparse
import json
import os
import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import uvicorn  # noqa: E402

from nafta2go.adapters.recorded_routes import RecordedRoutes  # noqa: E402
from nafta2go.adapters.route_cache import RouteCache  # noqa: E402
from nafta2go.domain.price_alert import POLICY_METHOD, POLICY_VERSION  # noqa: E402
from nafta2go.ml import registry  # noqa: E402
from nafta2go.persistence.database import create_db_engine, upgrade_to_head  # noqa: E402
from nafta2go.presentation.http import create_app  # noqa: E402
from scripts.validate_simulated_scenarios import SyntheticRoutes  # noqa: E402

MATRIX = ROOT / "docs/evidencia/poc-05-flujo-2026-10-26/matrix.json"
TOKEN = "token-de-carga-local"
ADMIN_TOKEN = "token-admin-de-carga-local"
QUOTA_SCOPE = b"carga-local"
# Misma vigencia que la medición de #152 sobre la copia del histórico real.
REAL_HISTORY_MAX_AGE_DAYS = "30"


class QuotaLimitedRoutes:
    """Rutas grabadas que consumen el cupo real; sin caché para que cada consulta cuente."""

    def __init__(self, recorded: RecordedRoutes, cache: RouteCache):
        self._recorded, self._cache = recorded, cache
        self.evidence, self.sha256 = recorded.evidence, recorded.sha256
        self.cache_hit = False

    def matrix(self, sources, destinations):
        key = ("carga", tuple(sources), tuple(destinations))
        value, self.cache_hit = self._cache.get(
            key, QUOTA_SCOPE, lambda: self._recorded.matrix(sources, destinations)
        )
        return value


def provider_factory(quota_per_minute=None, quota_per_day=None):
    recorded = RecordedRoutes(MATRIX)
    if quota_per_minute is None:
        return lambda: recorded
    cache = RouteCache(
        ttl=0,
        per_minute=quota_per_minute,
        per_day=quota_per_day if quota_per_day is not None else max(quota_per_minute, 450),
    )
    return lambda: QuotaLimitedRoutes(recorded, cache)


def build_app(database_url, quota_per_minute=None, quota_per_day=None):
    upgrade_to_head(database_url)
    return create_app(
        create_db_engine(database_url),
        provider_factory=provider_factory(quota_per_minute, quota_per_day),
        routing_provider="openrouteservice-recorded",
    )


def serve_audited_run(run: str, directory: Path) -> None:
    """Apunta el alias champion a una corrida auditada, en una copia temporal del registro."""
    current = registry.load()
    if run not in registry.audited_versions(POLICY_VERSION, POLICY_METHOD, current):
        raise registry.RegistryError(f"La corrida {run} no está auditada para {POLICY_VERSION}")
    current["aliases"]["champion"] = {"run": run, "method": POLICY_METHOD}
    copy = directory / "registry.json"
    copy.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    registry.REGISTRY = copy


def build_real_history_app(source: Path, database: Path, reference_at: datetime):
    if reference_at.utcoffset() is None:
        raise ValueError("--reference-at requiere zona horaria")
    with sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True) as original:
        with sqlite3.connect(database) as destination:
            original.backup(destination)
    database_url = f"sqlite:///{database}"
    upgrade_to_head(database_url)
    os.environ["NAFTA2GO_MAX_PRICE_AGE_DAYS"] = REAL_HISTORY_MAX_AGE_DAYS
    return create_app(
        create_db_engine(database_url),
        provider_factory=SyntheticRoutes,
        clock=lambda: reference_at,
        routing_provider="synthetic-routes-real-history",
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8100)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--quota-per-minute", type=int)
    parser.add_argument("--quota-per-day", type=int)
    parser.add_argument("--source-database", type=Path, help="Base con histórico real")
    parser.add_argument("--reference-at", type=datetime.fromisoformat)
    parser.add_argument("--model-run", help="Corrida auditada a servir en lugar del campeón")
    args = parser.parse_args(argv)
    if args.source_database and args.reference_at is None:
        parser.error("--source-database requiere --reference-at")
    os.environ["NAFTA2GO_API_TOKEN"] = TOKEN
    os.environ["NAFTA2GO_ADMIN_TOKEN"] = ADMIN_TOKEN
    with tempfile.TemporaryDirectory() as directory:
        if args.model_run:
            serve_audited_run(args.model_run, Path(directory))
        if args.source_database:
            app = build_real_history_app(args.source_database, args.database, args.reference_at)
        else:
            app = build_app(f"sqlite:///{args.database}", args.quota_per_minute, args.quota_per_day)
        uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning", access_log=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
