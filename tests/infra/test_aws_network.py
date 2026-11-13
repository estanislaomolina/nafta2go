"""Invariantes de costo y exposición de la base de red, sin consultar AWS."""

import ipaddress
import json
from pathlib import Path

RESOURCES = json.loads(
    (Path(__file__).resolve().parents[2] / "infra/aws/network.json").read_text()
)["Resources"]


def test_network_does_not_introduce_billed_compute_or_services():
    allowed = {
        "VPC",
        "Subnet",
        "InternetGateway",
        "VPCGatewayAttachment",
        "RouteTable",
        "Route",
        "SubnetRouteTableAssociation",
        "SecurityGroup",
    }
    assert all(r["Type"] in {f"AWS::EC2::{kind}" for kind in allowed} for r in RESOURCES.values())
    assert not any(r.get("DeletionPolicy") == "Retain" for r in RESOURCES.values())


def test_subnet_is_contained_and_does_not_allocate_public_addresses():
    subnet = RESOURCES["Subnet"]["Properties"]
    vpc = RESOURCES["Vpc"]["Properties"]
    assert ipaddress.ip_network(subnet["CidrBlock"]).subnet_of(
        ipaddress.ip_network(vpc["CidrBlock"])
    )
    assert subnet["MapPublicIpOnLaunch"] is False
    assert subnet["VpcId"] == {"Ref": "Vpc"}


def test_application_has_no_inbound_access_and_only_https_egress():
    group = RESOURCES["ApplicationSecurityGroup"]["Properties"]
    assert not group.get("SecurityGroupIngress")
    assert group["VpcId"] == {"Ref": "Vpc"}
    assert group["SecurityGroupEgress"]  # Vacío activa salida por defecto en CloudFormation.
    for rule in group["SecurityGroupEgress"]:
        assert (rule["IpProtocol"], rule["FromPort"], rule["ToPort"]) == ("tcp", 443, 443)


def test_internet_route_waits_for_gateway_and_is_associated_with_subnet():
    route = RESOURCES["InternetRoute"]
    assert route["DependsOn"] == "GatewayAttachment"
    assert route["Properties"]["GatewayId"] == {"Ref": "InternetGateway"}
    assert RESOURCES["SubnetRoute"]["Properties"] == {
        "SubnetId": {"Ref": "Subnet"},
        "RouteTableId": {"Ref": "RouteTable"},
    }
