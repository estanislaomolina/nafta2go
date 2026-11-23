"""Consultar ingestas y conservar alertas sin alterar sus estados ni sus precios."""

from datetime import UTC, datetime

from sqlalchemy import Engine

from nafta2go.domain.ingestion_health import detect_alerts
from nafta2go.persistence import repository as repo


def check_ingestion(engine: Engine, source: str, now: datetime) -> dict:
    if source not in repo.SOURCES:
        raise ValueError("Origen de ingesta desconocido")
    with engine.begin() as conn:
        alerts = detect_alerts(repo.runs_for_monitoring(conn, source), now)
        active = repo.sync_ingestion_alerts(
            conn, source, alerts, now.astimezone(UTC).replace(tzinfo=None)
        )
    for alert in active:
        for key in ("detected_at", "last_seen_at", "resolved_at"):
            if alert[key] is not None:
                alert[key] = alert[key].replace(tzinfo=UTC).isoformat()
    return {
        "source": source,
        "checked_at": now.astimezone(UTC).isoformat(),
        "status": "alerting" if active else "healthy",
        "alerts": active,
    }
