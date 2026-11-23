"""Corte conservador de cómputo: presupuesto total, margen y datos preservados."""

import os
from datetime import UTC, datetime
from decimal import Decimal

BUDGET_TAG = "Nafta2GoBudget"


def cutoff(budget, now):
    updated = budget["LastUpdatedTime"]
    age_hours = Decimal(str(max(0, (now - updated).total_seconds()) / 3600))
    spent = Decimal(budget["CalculatedSpend"]["ActualSpend"]["Amount"])
    # Cubre la demora contable con una cota conservadora de cómputo/red/disco.
    upper = spent + age_hours * Decimal("0.05")
    return upper >= Decimal("15") or age_hours > 36, upper


def handler(event, context):
    import boto3

    budget = boto3.client("budgets", region_name="us-east-1").describe_budget(
        AccountId=os.environ["ACCOUNT"], BudgetName="nafta2go-17-usd-total"
    )["Budget"]
    stop, upper = cutoff(budget, datetime.now(UTC))
    if stop:
        ec2 = boto3.client("ec2", region_name=os.environ["REGION"])
        instance = os.environ["INSTANCE"]
        ec2.create_tags(Resources=[instance], Tags=[{"Key": BUDGET_TAG, "Value": "exhausted"}])
        ec2.stop_instances(InstanceIds=[instance])
    return {
        "stop_requested": stop,
        "estimated_upper_usd": str(upper),
        "reserve_usd": "2",
        "data_deleted": False,
    }
