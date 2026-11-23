"""El presupuesto es acumulativo y el corte conserva los datos."""

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from deploy.budget_guard import cutoff


def test_spend_is_not_reset_at_month_boundary():
    now = datetime(2026, 12, 1, tzinfo=UTC)
    budget = {
        "LastUpdatedTime": now - timedelta(hours=2),
        "CalculatedSpend": {"ActualSpend": {"Amount": "14.95"}},
    }
    stop, estimate = cutoff(budget, now)
    assert stop and estimate == Decimal("15.05")


def test_fresh_low_spend_keeps_compute_and_stale_data_stops_it():
    now = datetime(2026, 11, 23, tzinfo=UTC)
    budget = {"LastUpdatedTime": now, "CalculatedSpend": {"ActualSpend": {"Amount": "0.105"}}}
    assert cutoff(budget, now) == (False, Decimal("0.105"))
    assert cutoff(budget, now + timedelta(hours=37))[0]


def test_deployed_lambda_matches_the_tested_guard():
    root = Path(__file__).resolve().parents[2]
    template = json.loads((root / "infra/aws/public-api.json").read_text())
    inline = template["Resources"]["BudgetGuard"]["Properties"]["Code"]["ZipFile"]
    assert inline == (root / "deploy/budget_guard.py").read_text()
