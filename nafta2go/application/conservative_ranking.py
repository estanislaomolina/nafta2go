"""Filtra evaluaciones ya enrutadas con la política provisional de ADR-021."""

from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from nafta2go.application.price_diagnostic import (
    DiagnosticUnavailable,
    price_diagnostics_on_connection,
)
from nafta2go.domain import price_alert
from nafta2go.domain.ranking import rank_alternatives
from nafta2go.normalization.rules import LOCAL_TIMEZONE


def conservative_ranking(conn, evaluations, rows, *, status, run_id, product_id, schedule_id, now):
    block = {
        "status": "unavailable",
        "reason": "historical_or_insufficient_coverage",
        "policy_version": price_alert.POLICY_VERSION,
        "notice": price_alert.NOTICE,
        "data_run_id": run_id,
        "alternatives": [],
        "excluded_station_ids": [],
        "without_reference_station_ids": [],
        "diagnostics": [],
    }
    if status != "ready":
        return block
    diagnostics, excluded, unknown = [], [], []
    try:
        batch = price_diagnostics_on_connection(
            conn,
            [int(station) for station, value in evaluations.items() if value.feasible],
            product_id,
            schedule_id,
            now,
        )
        for station_id, evaluation in evaluations.items():
            if not evaluation.feasible:
                continue
            item = batch[int(station_id)]
            if (
                item is None
                or item["data_run_id"] != run_id
                or (
                    Decimal(item["official_price_ars_per_l"])
                    != rows[station_id].candidate.price_ars_per_l
                    or datetime.fromisoformat(item["published_at"])
                    .astimezone(ZoneInfo(LOCAL_TIMEZONE))
                    .replace(tzinfo=None)
                    != rows[station_id].published_at_local
                )
            ):
                return block | {"reason": "publication_mismatch"}
            if not price_alert.policy_compatible(item["method"], item["version"]):
                return block | {"reason": "policy_not_compatible"}
            diagnostics.append(item)
            if item["reference_ars_per_l"] is None:
                unknown.append(station_id)
            elif item["alert_level"] == "provisional_deviation":
                excluded.append(station_id)
            elif item["alert_level"] != "provisional_within_threshold":
                return block | {"reason": "policy_not_compatible"}
    except DiagnosticUnavailable:
        return block | {"reason": "diagnostic_not_available"}
    if not diagnostics:
        return block | {"reason": "no_feasible_stations"}
    choices = rank_alternatives(
        {key: value for key, value in evaluations.items() if key not in excluded}
    )
    return block | {
        "status": "available",
        "reason": "provisional_comparison" if choices else "all_feasible_excluded",
        "alternatives": [asdict(choice) for choice in choices],
        "excluded_station_ids": excluded,
        "without_reference_station_ids": unknown,
        "diagnostics": diagnostics,
    }
