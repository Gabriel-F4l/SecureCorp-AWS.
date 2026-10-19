"""Security regression tests for the synthesized CloudFormation template.

No AWS account or deployment is required.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def template(tmp_path_factory):
    out = tmp_path_factory.mktemp("cdk-out")
    subprocess.run(
        [sys.executable, "app.py", "--output", str(out)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    path = out / "SecureCorpAWSStack.template.json"
    return json.loads(path.read_text(encoding="utf-8"))


def resources(template, resource_type):
    return [
        item.get("Properties", {})
        for item in template.get("Resources", {}).values()
        if item.get("Type") == resource_type
    ]


def test_vpc_cidr(template):
    assert any(vpc.get("CidrBlock") == "10.20.0.0/16" for vpc in resources(template, "AWS::EC2::VPC"))


def test_s3_public_access_blocked(template):
    buckets = resources(template, "AWS::S3::Bucket")
    assert buckets, "Expected at least one S3 bucket"
    for bucket in buckets:
        block = bucket.get("PublicAccessBlockConfiguration", {})
        assert all(block.get(key) is True for key in (
            "BlockPublicAcls", "BlockPublicPolicy",
            "IgnorePublicAcls", "RestrictPublicBuckets"
        ))


def test_s3_encryption_and_versioning(template):
    buckets = resources(template, "AWS::S3::Bucket")
    assert buckets
    for bucket in buckets:
        assert bucket.get("BucketEncryption"), "S3 encryption missing"
        assert bucket.get("VersioningConfiguration", {}).get("Status") == "Enabled"


def test_gateway_endpoint_for_s3(template):
    endpoints = resources(template, "AWS::EC2::VPCEndpoint")
    assert any(
        e.get("VpcEndpointType") == "Gateway"
        and "s3" in json.dumps(e.get("ServiceName", "")).lower()
        for e in endpoints
    )


def test_no_world_open_security_group_rules(template):
    rules = (
        resources(template, "AWS::EC2::SecurityGroupIngress")
        + resources(template, "AWS::EC2::SecurityGroupEgress")
    )
    for sg in resources(template, "AWS::EC2::SecurityGroup"):
        rules.extend(sg.get("SecurityGroupIngress", []))
        rules.extend(sg.get("SecurityGroupEgress", []))
    for rule in rules:
        assert rule.get("CidrIp") != "0.0.0.0/0", "Unrestricted IPv4 SG rule"
        assert rule.get("CidrIpv6") != "::/0", "Unrestricted IPv6 SG rule"


def test_ec2_requires_imdsv2(template):
    instances = resources(template, "AWS::EC2::Instance")
    assert instances, "Expected an EC2 instance"
    for instance in instances:
        assert instance.get("MetadataOptions", {}).get("HttpTokens") == "required"


def test_cloudwatch_alarm_present(template):
    assert resources(template, "AWS::CloudWatch::Alarm"), "Expected a CloudWatch alarm"
