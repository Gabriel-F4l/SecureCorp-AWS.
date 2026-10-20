from aws_cdk import (
    CfnOutput,
    CfnParameter,
    Duration,
    RemovalPolicy,
    Stack,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cloudwatch_actions,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_s3 as s3,
    aws_sns as sns,
    aws_sns_subscriptions as subscriptions,
)
from constructs import Construct


class SecureCorpAWSStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # 1. VPC corporativa: duas AZs, sem NAT Gateway.
        vpc = ec2.Vpc(
            self, "SecureCorpVPC",
            ip_addresses=ec2.IpAddresses.cidr("10.20.0.0/16"),
            max_azs=2,
            nat_gateways=0,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public", subnet_type=ec2.SubnetType.PUBLIC, cidr_mask=24
                ),
                ec2.SubnetConfiguration(
                    name="Private", subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                    cidr_mask=24,
                ),
            ],
        )
        CfnOutput(self, "SecureCorpVpcId", value=vpc.vpc_id)

        # 2. Security Group restritivo dos servidores.
        sg_servidores = ec2.SecurityGroup(
            self, "SecureCorpServersSG", vpc=vpc,
            description="Security Group dos servidores internos",
            allow_all_outbound=False, disable_inline_rules=True,
        )
        # Acesso futuro: requer rota/conectividade com a rede corporativa.
        sg_servidores.add_ingress_rule(
            ec2.Peer.ipv4("10.10.0.0/16"), ec2.Port.tcp(443),
            "HTTPS da matriz - acesso futuro",
        )
        CfnOutput(self, "ServersSecurityGroupId", value=sg_servidores.security_group_id)

        # 3. IAM: permissões mínimas e SSM.
        role_servidores = iam.Role(
            self, "SecureCorpServersRole",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            description="Role dos servidores privados SecureCorp",
        )
        role_servidores.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "AmazonSSMManagedInstanceCore"
            )
        )

        # 4. Bucket corporativo com criptografia e bloqueio público.
        bucket_documentos = s3.Bucket(
            self, "SecureCorpDocumentos",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            versioned=True,
            removal_policy=RemovalPolicy.RETAIN,
        )
        role_servidores.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["s3:GetObject"],
                resources=[bucket_documentos.arn_for_objects("*")],
            )
        )
        CfnOutput(self, "SecureCorpBucketName", value=bucket_documentos.bucket_name)

        # 5. Gateway endpoint para S3 nas subnets isoladas.
        endpoint_s3 = vpc.add_gateway_endpoint(
            "SecureCorpS3Endpoint",
            service=ec2.GatewayVpcEndpointAwsService.S3,
            subnets=[ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_ISOLATED
            )],
        )
        # ATENÇÃO: acessos GetObject fora do endpoint também serão negados.
        bucket_documentos.add_to_resource_policy(
            iam.PolicyStatement(
                effect=iam.Effect.DENY,
                actions=["s3:GetObject"],
                resources=[bucket_documentos.arn_for_objects("*")],
                principals=[iam.AnyPrincipal()],
                conditions={"StringNotEquals": {
                    "aws:SourceVpce": endpoint_s3.vpc_endpoint_id
                }},
            )
        )

        # 6. Egress HTTPS para S3 usando prefix list regional.
        s3_prefix_list_id = CfnParameter(
            self, "S3PrefixListId", type="String",
            description="ID da Prefix List gerenciada do Amazon S3",
            allowed_pattern=r"pl-[0-9a-f]+",
        )
        sg_servidores.add_egress_rule(
            ec2.Peer.prefix_list(s3_prefix_list_id.value_as_string),
            ec2.Port.tcp(443), "HTTPS para Amazon S3",
        )

        # 7. Security Group dos endpoints SSM.
        sg_endpoints = ec2.SecurityGroup(
            self, "SecureCorpEndpointsSG", vpc=vpc,
            description="HTTPS privado para endpoints SSM",
            allow_all_outbound=False, disable_inline_rules=True,
        )
        sg_endpoints.add_ingress_rule(
            sg_servidores, ec2.Port.tcp(443), "HTTPS dos servidores privados"
        )
        sg_servidores.add_egress_rule(
            sg_endpoints, ec2.Port.tcp(443), "HTTPS para endpoints SSM"
        )

        # 8. Endpoints privados SSM e SSMMessages.
        endpoint_subnets = ec2.SubnetSelection(
            subnet_type=ec2.SubnetType.PRIVATE_ISOLATED
        )
        endpoint_ssm = vpc.add_interface_endpoint(
            "SecureCorpSSMEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.SSM,
            subnets=endpoint_subnets, security_groups=[sg_endpoints],
            private_dns_enabled=True, open=False,
        )
        endpoint_ssmmessages = vpc.add_interface_endpoint(
            "SecureCorpSSMMessagesEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.SSM_MESSAGES,
            subnets=endpoint_subnets, security_groups=[sg_endpoints],
            private_dns_enabled=True, open=False,
        )

        # 9. EC2 privada com IMDSv2 obrigatório.
        servidor_app = ec2.Instance(
            self, "SecureCorpAppServer",
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.T3, ec2.InstanceSize.MICRO
            ),
            machine_image=ec2.MachineImage.latest_amazon_linux2023(),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_ISOLATED
            ),
            security_group=sg_servidores,
            role=role_servidores,
            require_imdsv2=True,
        )
        cfn_servidor_app = servidor_app.node.default_child
        if not isinstance(cfn_servidor_app, ec2.CfnInstance):
            raise TypeError("Recurso EC2 inesperado no SecureCorpAppServer")
        cfn_servidor_app.add_property_override(
            "MetadataOptions.HttpTokens", "required"
        )
        CfnOutput(self, "SecureCorpAppServerId", value=servidor_app.instance_id)

        # 10. CloudWatch: CPU média em janelas de 5 minutos.
        metrica_cpu = cloudwatch.Metric(
            namespace="AWS/EC2", metric_name="CPUUtilization",
            dimensions_map={"InstanceId": servidor_app.instance_id},
            statistic="Average", period=Duration.minutes(5),
            unit=cloudwatch.Unit.PERCENT,
        )
        alarme_cpu = cloudwatch.Alarm(
            self, "SecureCorpHighCPUAlarm",
            alarm_name="SecureCorp-EC2-HighCPU",
            alarm_description="CPU media superior a 80% no SecureCorpAppServer",
            metric=metrica_cpu,
            threshold=80,
            evaluation_periods=1,
            datapoints_to_alarm=1,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.MISSING,
        )

        # 11. SNS para notificações.
        topico_alertas = sns.Topic(
            self, "SecureCorpAlertsTopic",
            display_name="SecureCorp - Alertas Cloud",
        )
        alarme_cpu.add_alarm_action(cloudwatch_actions.SnsAction(topico_alertas))

        # 12. E-mail configurável via CloudFormation (confirmar assinatura).
        email_alertas = CfnParameter(
            self, "SecureCorpAlertEmail", type="String",
            description="E-mail que recebera os alertas da SecureCorp",
            allowed_pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
            constraint_description="Informe um endereco de e-mail valido",
        )
        topico_alertas.add_subscription(
            subscriptions.EmailSubscription(email_alertas.value_as_string)
        )

        # 13. Alarmes de integridade EC2: sistema e instância.
        alarmes_status = []
        for tipo, nome_metrica in {
            "System": "StatusCheckFailed_System",
            "Instance": "StatusCheckFailed_Instance",
        }.items():
            metrica_status = cloudwatch.Metric(
                namespace="AWS/EC2", metric_name=nome_metrica,
                dimensions_map={"InstanceId": servidor_app.instance_id},
                statistic="Maximum", period=Duration.minutes(1),
            )
            alarme_status = cloudwatch.Alarm(
                self, f"SecureCorp{tipo}StatusAlarm",
                alarm_name=f"SecureCorp-EC2-{tipo}StatusFailed",
                alarm_description=f"Falha de integridade EC2: {tipo}",
                metric=metrica_status,
                threshold=0,
                evaluation_periods=2,
                datapoints_to_alarm=2,
                comparison_operator=(
                    cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD
                ),
                treat_missing_data=cloudwatch.TreatMissingData.MISSING,
            )
            alarme_status.add_alarm_action(
                cloudwatch_actions.SnsAction(topico_alertas)
            )
            alarmes_status.append(alarme_status)

        # 14. Dashboard CloudWatch com CPU e estado dos alarmes.
        dashboard = cloudwatch.Dashboard(
            self, "SecureCorpOperationsDashboard",
            dashboard_name="SecureCorp-Cloud-Operations",
        )
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="EC2 - Utilizacao de CPU", left=[metrica_cpu],
                width=12, height=6,
            ),
            cloudwatch.AlarmStatusWidget(
                title="Status dos Alarmes",
                alarms=[alarme_cpu, *alarmes_status],
                width=12, height=6,
            ),
        )

        # 15. Outputs CloudFormation.
        CfnOutput(
            self, "SecureCorpSSMEndpointId", value=endpoint_ssm.vpc_endpoint_id
        )
        CfnOutput(
            self, "SecureCorpSSMMessagesEndpointId",
            value=endpoint_ssmmessages.vpc_endpoint_id,
        )
        CfnOutput(self, "SecureCorpCPUAlarmName", value=alarme_cpu.alarm_name)
        CfnOutput(self, "SecureCorpAlertsTopicArn", value=topico_alertas.topic_arn)
