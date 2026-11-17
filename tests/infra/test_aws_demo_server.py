"""Evitar exposición, cargos accesorios y permisos extras en el servidor de demo."""

import json
import re
import subprocess
from pathlib import Path

TEMPLATE = json.loads(
    (Path(__file__).resolve().parents[2] / "infra/aws/demo-server.json").read_text()
)
RESOURCES = TEMPLATE["Resources"]
INSTANCE = RESOURCES["DemoInstance"]["Properties"]


def test_compute_is_bounded_without_optional_billed_services():
    assert sorted(r["Type"] for r in RESOURCES.values()) == sorted(
        [
            "AWS::EC2::Instance",
            "AWS::EC2::SecurityGroup",
            "AWS::IAM::Role",
            "AWS::IAM::InstanceProfile",
        ]
    )
    assert INSTANCE["InstanceType"] == "t3.small"
    assert INSTANCE["CreditSpecification"]["CPUCredits"] == "standard"
    assert INSTANCE["Monitoring"] is False
    assert not any(r.get("DeletionPolicy") == "Retain" for r in RESOURCES.values())


def test_ssm_access_does_not_open_ingress_and_only_uses_https_outbound():
    group = RESOURCES["DemoSecurityGroup"]["Properties"]
    assert group["VpcId"] == {"Ref": "VpcId"}
    assert not group.get("SecurityGroupIngress")
    assert group["SecurityGroupEgress"]  # Vacío habilita salida general por defecto.
    for rule in group["SecurityGroupEgress"]:
        assert (rule["IpProtocol"], rule["FromPort"], rule["ToPort"]) == ("tcp", 443, 443)
    (interface,) = INSTANCE["NetworkInterfaces"]
    assert interface["GroupSet"] == [{"Ref": "DemoSecurityGroup"}]
    assert interface["SubnetId"] == {"Ref": "SubnetId"}
    assert interface["AssociatePublicIpAddress"] is True  # Salida sin NAT; IPv4 facturable.
    assert interface["DeleteOnTermination"] is True
    assert "KeyName" not in INSTANCE


def test_disk_and_identity_do_not_leak_secrets_or_leave_retained_disks():
    (disk,) = INSTANCE["BlockDeviceMappings"]
    assert disk["Ebs"]["Encrypted"] is True and disk["Ebs"]["DeleteOnTermination"] is True
    assert disk["Ebs"]["VolumeType"] == "gp3" and disk["Ebs"]["VolumeSize"] == 16
    assert set(disk["Ebs"]) == {"Encrypted", "DeleteOnTermination", "VolumeType", "VolumeSize"}
    assert INSTANCE["MetadataOptions"]["HttpTokens"] == "required"
    assert INSTANCE["MetadataOptions"]["HttpPutResponseHopLimit"] == 1
    assert INSTANCE["IamInstanceProfile"] == {"Ref": "DemoProfile"}
    role = RESOURCES["DemoRole"]["Properties"]
    assert role["ManagedPolicyArns"] == [
        {"Fn::Sub": "arn:${AWS::Partition}:iam::aws:policy/AmazonSSMManagedInstanceCore"}
    ]
    assert "Policies" not in role
    assert all("Default" not in p for p in TEMPLATE["Parameters"].values())
    assert INSTANCE["ImageId"] == {"Ref": "ImageId"}  # AMI fijada al revisar el change set.
    script = INSTANCE["UserData"]["Fn::Base64"]
    assert "git clone" not in script and "TOKEN" not in script and "API_KEY" not in script


def test_stop_timer_is_enabled_each_boot_before_dependency_installation(tmp_path):
    assert INSTANCE["InstanceInitiatedShutdownBehavior"] == "stop"
    script = INSTANCE["UserData"]["Fn::Base64"]
    assert "OnBootSec=2h" in script
    assert "ExecStart=/usr/bin/systemctl poweroff" in script
    assert "WantedBy=timers.target" in script
    assert script.index("systemctl enable --now nafta2go-demo-stop.timer") < script.index(
        "dnf install"
    )
    subprocess.run(["bash", "-n"], input=script, text=True, check=True, capture_output=True)
    paths = []
    for name, content in re.findall(
        r"cat > /etc/systemd/system/(\S+) <<'UNIT'\n(.*?)\nUNIT", script, re.S
    ):
        path = tmp_path / name
        path.write_text(content + "\n")
        paths.append(str(path))
    assert len(paths) == 2
    subprocess.run(["systemd-analyze", "verify", *paths], check=True, capture_output=True)
