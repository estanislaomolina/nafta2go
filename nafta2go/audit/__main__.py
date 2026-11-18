"""python -m nafta2go.audit: trazabilidad, frescura y privacidad de las recomendaciones.

Lee la base de DATABASE_URL sin modificarla e imprime un resumen JSON. Termina con 0 si
todas las recomendaciones cumplen, 1 si alguna falla y 2 si no pudo leer la base.
"""

import argparse
import json
import logging
import sys

from sqlalchemy.exc import SQLAlchemyError

from nafta2go.application.recommendation_audit import audit_recommendations
from nafta2go.persistence import repository as repo
from nafta2go.persistence.database import create_db_engine

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    engine = None
    try:
        engine = create_db_engine()
        with engine.connect() as conn:
            report = audit_recommendations(repo.recommendations_with_run_status(conn))
    except (SQLAlchemyError, OSError, ValueError, KeyError, TypeError) as exc:
        # El mensaje de una excepción de conexión puede contener credenciales.
        logger.error("No se pudo auditar la base; revisar conexión y migraciones")
        print(json.dumps({"status": "audit_error", "error_type": type(exc).__name__}))
        return 2
    finally:
        if engine is not None:
            engine.dispose()
    print(json.dumps(report, ensure_ascii=False))
    return 1 if any(report["fallas"].values()) else 0


if __name__ == "__main__":
    sys.exit(main())
