
from aws_cdk import (
    Stack,
    CfnOutput,
    CfnParameter,
    RemovalPolicy,
    Duration,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_s3 as s3,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cloudwatch_actions,
    aws_sns as sns,
    aws_sns_subscriptions as subscriptions,
)
from constructs import Construct


class SecureCorpAWSStack(Stack):

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        **kwargs
    ) -> None:

        super().__init__(scope, construct_id, **kwargs)

        # =====================================================
        # 1. VPC CORPORATIVA
        # =====================================================

        vpc = ec2.Vpc(
            self,
            "SecureCorpVPC",
            ip_addresses=ec2.IpAddresses.cidr(
                "10.20.0.0/16"
            ),
            max_azs=2,
            nat_gateways=0,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                    cidr_mask=24,
                ),
            ],
        )

        CfnOutput(
            self,
            "SecureCorpVpcId",
            value=vpc.vpc_id,
        )

        # =====================================================
        # 2. SECURITY GROUP DOS SERVIDORES
        # =====================================================

        sg_servidores = ec2.SecurityGroup(
            self,
            "SecureCorpServersSG",
            vpc=vpc,
            description="Security Group dos servidores internos",
            allow_all_outbound=False,
            disable_inline_rules=True,
        )

        # HTTPS da matriz - acesso futuro.
        # Exige conectividade corporativa adicional.
        sg_servidores.add_ingress_rule(
            peer=ec2.Peer.ipv4("10.10.0.0/16"),
            connection=ec2.Port.tcp(443),
            description="HTTPS da matriz - acesso futuro",
        )

        CfnOutput(
            self,
            "ServersSecurityGroupId",
            value=sg_servidores.security_group_id,
        )

        # =====================================================
        # 3. IAM ROLE DOS SERVIDORES
        # =====================================================

        role_servidores = iam.Role(
            self,
            "SecureCorpServersRole",
            assumed_by=iam.ServicePrincipal(
                "ec2.amazonaws.com"
            ),
            description="Role dos servidores privados SecureCorp",
        )

        # Permissoes para o SSM Agent
        role_servidores.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "AmazonSSMManagedInstanceCore"
            )
        )

        # =====================================================
        # 4. BUCKET S3 CORPORATIVO
        # =====================================================

        bucket_documentos = s3.Bucket(
            self,
            "SecureCorpDocumentos",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            versioned=True,
            removal_policy=RemovalPolicy.RETAIN,
        )

        # Permissao minima para leitura de objetos
        role_servidores.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["s3:GetObject"],
                resources=[
                    bucket_documentos.arn_for_objects("*")
                ],
            )
        )

        CfnOutput(
            self,
            "SecureCorpBucketName",
            value=bucket_documentos.bucket_name,
        )

        # =====================================================
        # 5. GATEWAY VPC ENDPOINT PARA S3
        # =====================================================

        endpoint_s3 = vpc.add_gateway_endpoint(
            "SecureCorpS3Endpoint",
            service=ec2.GatewayVpcEndpointAwsService.S3,
            subnets=[
                ec2.SubnetSelection(
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED
                )
            ],
        )

        # Restricao de leitura ao endpoint autorizado.
        # Revisar antes de deploy: acessos administrativos
        # fora do endpoint tambem serao negados.
        bucket_documentos.add_to_resource_policy(
            iam.PolicyStatement(
                effect=iam.Effect.DENY,
                actions=["s3:GetObject"],
                resources=[
                    bucket_documentos.arn_for_objects("*")
                ],
                principals=[iam.AnyPrincipal()],
                conditions={
                    "StringNotEquals": {
                        "aws:SourceVpce":
                            endpoint_s3.vpc_endpoint_id
                    }
                },
            )
        )

        # =====================================================
        # 6. SAIDA HTTPS PARA S3
        # =====================================================

        s3_prefix_list_id = CfnParameter(
            self,
            "S3PrefixListId",
            type="String",
            description=(
                "ID da Prefix List gerenciada do Amazon S3"
            ),
            allowed_pattern=r"pl-[0-9a-f]+",
        )

        sg_servidores.add_egress_rule(
            peer=ec2.Peer.prefix_list(
                s3_prefix_list_id.value_as_string
            ),
            connection=ec2.Port.tcp(443),
            description="HTTPS para Amazon S3",
        )

        # =====================================================
        # 7. SECURITY GROUP DOS INTERFACE ENDPOINTS
        # =====================================================

        sg_endpoints = ec2.SecurityGroup(
            self,
            "SecureCorpEndpointsSG",
            vpc=vpc,
            description="HTTPS privado para endpoints SSM",
            allow_all_outbound=False,
            disable_inline_rules=True,
        )

        sg_endpoints.add_ingress_rule(
            peer=sg_servidores,
            connection=ec2.Port.tcp(443),
            description="HTTPS dos servidores privados",
        )

        sg_servidores.add_egress_rule(
            peer=sg_endpoints,
            connection=ec2.Port.tcp(443),
            description="HTTPS para endpoints SSM",
        )

        # =====================================================
        # 8. INTERFACE VPC ENDPOINTS DO SYSTEMS MANAGER
        # =====================================================

        endpoint_subnets = ec2.SubnetSelection(
            subnet_type=ec2.SubnetType.PRIVATE_ISOLATED
        )

        endpoint_ssm = vpc.add_interface_endpoint(
            "SecureCorpSSMEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.SSM,
            subnets=endpoint_subnets,
            security_groups=[sg_endpoints],
            private_dns_enabled=True,
            open=False,
        )

        endpoint_ssmmessages = vpc.add_interface_endpoint(
            "SecureCorpSSMMessagesEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.SSM_MESSAGES,
            subnets=endpoint_subnets,
            security_groups=[sg_endpoints],
            private_dns_enabled=True,
            open=False,
        )

        # =====================================================
        # 9. EC2 PRIVADA
        # =====================================================

        servidor_app = ec2.Instance(
            self,
            "SecureCorpAppServer",
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.T3,
                ec2.InstanceSize.MICRO,
            ),
            machine_image=(
                ec2.MachineImage.latest_amazon_linux2023()
            ),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_ISOLATED
            ),
            security_group=sg_servidores,
            role=role_servidores,
            require_imdsv2=True,
        )

        # Garante IMDSv2 no template CloudFormation sintetizado.
        # O teste de seguranca valida MetadataOptions.HttpTokens=required.
        cfn_servidor_app = servidor_app.node.default_child
        if not isinstance(cfn_servidor_app, ec2.CfnInstance):
            raise TypeError("Recurso EC2 inesperado no construct SecureCorpAppServer")
        cfn_servidor_app.add_property_override(
            "MetadataOptions.HttpTokens", "required"
        )

        CfnOutput(
            self,
            "SecureCorpAppServerId",
            value=servidor_app.instance_id,
        )

        # =====================================================
        # 10. CLOUDWATCH - METRICA DE CPU
        # =====================================================

        metrica_cpu = cloudwatch.Metric(
            namespace="AWS/EC2",
            metric_name="CPUUtilization",
            dimensions_map={
                "InstanceId": servidor_app.instance_id,
            },
            statistic="Average",
            period=Duration.minutes(5),
            unit=cloudwatch.Unit.PERCENT,
        )

        alarme_cpu = cloudwatch.Alarm(
            self,
            "SecureCorpHighCPUAlarm",
            alarm_name="SecureCorp-EC2-HighCPU",
            alarm_description=(
                "CPU media superior a 80 por cento "
                "no servidor SecureCorpAppServer"
            ),
            metric=metrica_cpu,
            threshold=80,
            evaluation_periods=1,
            datapoints_to_alarm=1,
            comparison_operator=(
                cloudwatch.ComparisonOperator
                .GREATER_THAN_THRESHOLD
            ),
            treat_missing_data=(
                cloudwatch.TreatMissingData.MISSING
            ),
        )

        # =====================================================
        # 11. AMAZON SNS - TOPICO DE ALERTAS
        # =====================================================

        topico_alertas = sns.Topic(
            self,
            "SecureCorpAlertsTopic",
            display_name="SecureCorp - Alertas Cloud",
        )

        # Vincula o alarme CloudWatch ao topico SNS
        alarme_cpu.add_alarm_action(
            cloudwatch_actions.SnsAction(
                topico_alertas
            )
        )

        # =====================================================
        # 12. ASSINATURA DE E-MAIL PARAMETRIZADA
        # =====================================================

        # Endereco fornecido no CloudFormation.
        # Nao armazenar e-mail pessoal no codigo.
        email_alertas = CfnParameter(
            self,
            "SecureCorpAlertEmail",
            type="String",
            description=(
                "E-mail que recebera os alertas da SecureCorp"
            ),
            allowed_pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
            constraint_description=(
                "Informe um endereco de e-mail valido"
            ),
        )

        # O destinatario precisa confirmar a assinatura
        topico_alertas.add_subscription(
            subscriptions.EmailSubscription(
                email_alertas.value_as_string
            )
        )

        # =====================================================
        # 13. OUTPUTS CLOUDFORMATION
        # =====================================================

        CfnOutput(
            self,
            "SecureCorpSSMEndpointId",
            value=endpoint_ssm.vpc_endpoint_id,
        )

        CfnOutput(
            self,
            "SecureCorpSSMMessagesEndpointId",
            value=endpoint_ssmmessages.vpc_endpoint_id,
        )

        CfnOutput(
            self,
            "SecureCorpCPUAlarmName",
            value=alarme_cpu.alarm_name,
        )

        CfnOutput(
            self,
            "SecureCorpAlertsTopicArn",
            value=topico_alertas.topic_arn,
        )
