"""Reglas de alertas de la ingesta diaria, sin acceso a datos ni notificaciones."""

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

LOCAL_ZONE = ZoneInfo("America/Argentina/Buenos_Aires")
MAX_RUNNING_TIME = timedelta(hours=2)


def detect_alerts(runs: Sequence[Mapping], now: datetime) -> list[dict]:
    """Espera una ejecución desde las 06:00 locales, con dos horas de tolerancia.

    Las fechas de la base están en UTC sin zona. `now` requiere zona explícita.
    Un `running` excedido se alerta; no se declara muerto ni se modifica.
    """
    if now.utcoffset() is None:
        raise ValueError("now debe tener zona horaria")
    utc_now = now.astimezone(UTC).replace(tzinfo=None)
    due = now.astimezone(LOCAL_ZONE).replace(hour=6, minute=0, second=0, microsecond=0)
    if now < due + MAX_RUNNING_TIME:
        due -= timedelta(days=1)
    expected_since = due.astimezone(UTC).replace(tzinfo=None)
    alerts = []
    if not any(run["started_at"] >= expected_since for run in runs):
        alerts.append({"key": f"missing:{due.date()}", "kind": "missing", "run_id": None})
    completed = [run for run in runs if run["finished_at"] is not None]
    if completed:
        latest = max(completed, key=lambda run: (run["finished_at"], run["id"]))
        if latest["status"] == "failed":
            alerts.append(
                {"key": f"failed:{latest['id']}", "kind": "failed", "run_id": latest["id"]}
            )
    for run in runs:
        if run["status"] == "running" and utc_now - run["started_at"] >= MAX_RUNNING_TIME:
            alerts.append({"key": f"stalled:{run['id']}", "kind": "stalled", "run_id": run["id"]})
    return alerts
