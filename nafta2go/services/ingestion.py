"""Ciclo de vida de una ejecución de ingesta.

La ejecución se registra como `running` en su propia transacción. Captura,
precios, rechazos y cierre van juntos en una segunda transacción: si algo
falla se revierte entera y la ejecución queda `failed` con el error. Un
proceso cortado a mitad deja `running`, nunca `succeeded`.
"""

import logging
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import Engine

from nafta2go.persistence import repository as repo
from nafta2go.persistence.models import NormalizationResult, RawCapture

Normalizer = Callable[[RawCapture], NormalizationResult]
MAX_ERROR_LENGTH = 2000

logger = logging.getLogger(__name__)


class IngestionFailed(RuntimeError):
    def __init__(self, run_id: int, message: str):
        super().__init__(message)
        self.run_id = run_id


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def ingest(
    engine: Engine,
    capture: RawCapture,
    normalize: Normalizer,
    clock: Callable[[], datetime] = utc_now,
) -> int:
    with engine.begin() as conn:
        run_id = repo.start_run(conn, capture.source, clock())

    try:
        result = normalize(capture)
        _check_report(result)
        with engine.begin() as conn:
            report = dict(result.report)
            previous = repo.find_run_by_sha256(conn, capture.source, capture.sha256)
            if previous is not None:
                report["duplicate_of_run_id"] = previous
            repo.add_raw_capture(conn, run_id, capture)
            repo.add_prices(conn, run_id, result.rows)
            repo.add_rejections(conn, run_id, result.rejections)
            repo.finish_run(
                conn,
                run_id,
                "succeeded",
                clock(),
                report=report,
                rules_version=result.rules_version,
            )
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"[:MAX_ERROR_LENGTH]
        with engine.begin() as conn:
            repo.finish_run(conn, run_id, "failed", clock(), error=error)
        logger.error("ingesta fallida", extra={"run_id": run_id, "error": error})
        raise IngestionFailed(run_id, f"La ejecución {run_id} falló: {error}") from exc

    logger.info(
        "ingesta exitosa",
        extra={"run_id": run_id, "rows": len(result.rows), "rejections": len(result.rejections)},
    )
    return run_id


def _check_report(result: NormalizationResult) -> None:
    expected = {"filas_validas": len(result.rows), "filas_rechazadas": len(result.rejections)}
    for key, actual in expected.items():
        if key in result.report and result.report[key] != actual:
            raise ValueError(
                f"{key}: el reporte declara {result.report[key]} pero se recibieron {actual}"
            )
