"""Guardas de la programación: un encendido, zona explícita y una sola instancia."""

import json
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parents[2] / "infra/aws/demo-start-once.json"


def test_schedule_cannot_become_recurring_or_add_compute():
    template = json.loads(TEMPLATE.read_text())
    resources = template["Resources"]
    assert {r["Type"] for r in resources.values()} == {
        "AWS::Scheduler::Schedule",
        "AWS::Scheduler::ScheduleGroup",
        "AWS::IAM::Role",
    }
    schedule = resources["StartSchedule"]["Properties"]
    assert schedule["ScheduleExpression"] == {"Fn::Sub": "at(${StartAtLocal})"}
    assert schedule["ScheduleExpressionTimezone"] == "America/Argentina/Buenos_Aires"
    assert schedule["FlexibleTimeWindow"] == {"Mode": "OFF"}
    assert schedule["Target"]["RetryPolicy"]["MaximumEventAgeInSeconds"] == 300
    assert schedule["Target"]["RetryPolicy"]["MaximumRetryAttempts"] == 2


def test_execution_role_can_only_start_the_target_instance_from_its_group():
    role = json.loads(TEMPLATE.read_text())["Resources"]["StartRole"]["Properties"]
    trust = role["AssumeRolePolicyDocument"]["Statement"]
    assert len(trust) == 1 and trust[0]["Principal"] == {"Service": "scheduler.amazonaws.com"}
    assert trust[0]["Condition"]["StringEquals"] == {
        "aws:SourceAccount": {"Ref": "AWS::AccountId"},
        "aws:SourceArn": {"Fn::GetAtt": ["StartGroup", "Arn"]},
    }
    assert len(role["Policies"]) == 1
    assert role["Policies"][0]["PolicyDocument"]["Statement"] == [
        {
            "Effect": "Allow",
            "Action": "ec2:StartInstances",
            "Resource": {
                "Fn::Sub": "arn:${AWS::Partition}:ec2:${AWS::Region}:"
                "${AWS::AccountId}:instance/${InstanceId}"
            },
        }
    ]
