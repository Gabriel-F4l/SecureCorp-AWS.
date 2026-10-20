"""Unit tests for the current SecureCorp AWS CDK stack."""
import aws_cdk as core
from aws_cdk import assertions

from secure_corp_aws.secure_corp_aws_stack import SecureCorpAWSStack


def test_securecorp_vpc_created():
    app = core.App()
    stack = SecureCorpAWSStack(app, "SecureCorpAWSStack")
    template = assertions.Template.from_stack(stack)
    template.has_resource_properties("AWS::EC2::VPC", {
        "CidrBlock": "10.20.0.0/16",
    })
