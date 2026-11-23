"""python -m nafta2go.monitor: alertas locales persistidas y resumen JSON."""

import argparse
import json
import logging
import sys
from datetime import UTC, datetime

from sqlalchemy.exc import SQLAlchemyError

from nafta2go.application.ingestion_monitor import check_ingestion
from nafta2go.normalization.rules import SOURCES
from nafta2go.persistence.database import create_db_engine

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=SOURCES, default="vigente")
    args = parser.parse_args(argv)
    now = datetime.now(UTC)
    engine = None
    try:
        engine = create_db_engine()
        summary = check_ingestion(engine, args.source, now)
    except (SQLAlchemyError, OSError, ValueError) as exc:
        # El mensaje de una excepción de conexión puede contener credenciales.
        summary = {
            "source": args.source,
            "checked_at": now.isoformat(),
            "status": "monitor_error",
            "error_type": type(exc).__name__,
        }
        logger.error("No se pudo verificar la ingesta; revisar base y migraciones")
        print(json.dumps(summary, ensure_ascii=False))
        return 2
    finally:
        if engine is not None:
            engine.dispose()
    print(json.dumps(summary, ensure_ascii=False))
    if summary["alerts"]:
        logger.error(
            "Alertas de ingesta activas: %s", ", ".join(a["key"] for a in summary["alerts"])
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
