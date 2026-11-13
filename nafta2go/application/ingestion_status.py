"""Lectura operativa de ingestas; no ejecuta ni modifica el monitor persistido."""

from datetime import UTC, datetime

from sqlalchemy import Engine

from nafta2go.domain.ingestion_health import detect_alerts
from nafta2go.persistence import repository as repo

CONDITION_LIMIT = 20


def ingestion_status(engine: Engine, source: str, now: datetime) -> dict:
    if source not in repo.SOURCES or now.utcoffset() is None:
        raise ValueError("Origen conocido y fecha con zona requeridos")
    with engine.begin() as conn:
        runs = repo.runs_for_monitoring(conn, source)
        conditions = sorted(detect_alerts(runs, now), key=lambda condition: condition["key"])
        latest = max(runs, key=lambda run: (run["started_at"], run["id"]), default=None)
        successful = repo.latest_successful_run(conn, source)

        def summary(run_id):
            if run_id is None:
                return None
            result = repo.ingestion_run_summary(conn, run_id)
            until = result["finished_at"] or now.astimezone(UTC).replace(tzinfo=None)
            result["duration_seconds"] = max(0, (until - result["started_at"]).total_seconds())
            for key in ("started_at", "finished_at"):
                if result[key] is not None:
                    result[key] = result[key].replace(tzinfo=UTC).isoformat()
            return result

        return {
            "source": source,
            "observed_at": now.astimezone(UTC).isoformat(),
            "status": "alerting" if conditions else "healthy",
            "latest_attempt": summary(latest["id"] if latest else None),
            "latest_successful": summary(successful),
            "conditions": conditions[:CONDITION_LIMIT],
            "condition_count": len(conditions),
            "conditions_truncated": len(conditions) > CONDITION_LIMIT,
        }
