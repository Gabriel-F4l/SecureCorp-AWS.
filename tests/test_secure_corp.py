
import json
from pathlib import Path

# ============================================================
# SECURECORP AUTOMOTIVE
# TESTES AUTOMATIZADOS DE INFRAESTRUTURA AWS
# AWS CDK + CLOUDFORMATION + PYTEST
# ============================================================

TEMPLATE_PATH = (
    Path(__file__).resolve().parents[1]
    / "cdk.out"
    / "SecureCorpAWSStack.template.json"
)


def carregar_template():
    """Carrega o template sintetizado pelo AWS CDK."""

    assert TEMPLATE_PATH.is_file(), (
        "Template CloudFormation nao encontrado. "
        "Execute: cdk synth --output cdk.out"
    )

    with TEMPLATE_PATH.open(encoding="utf-8") as arquivo:
        return json.load(arquivo)


def obter_recursos(template, tipo):
    """Filtra recursos CloudFormation pelo tipo."""

    return {
        nome: recurso
        for nome, recurso in template["Resources"].items()
        if recurso["Type"] == tipo
    }


def obter_acoes(statement):
    """Normaliza Action como lista."""

    acoes = statement.get("Action", [])

    if isinstance(acoes, str):
        return [acoes]

    return acoes


def nome_servico_endpoint(propriedades):
    """Identifica o sufixo do servico AWS no endpoint."""

    nome = propriedades.get("ServiceName", "")

    if isinstance(nome, str):
        return nome.split(".")[-1]

    if isinstance(nome, dict):
        partes = nome.get("Fn::Join", [])

        if len(partes) == 2:
            for parte in reversed(partes[1]):
                if isinstance(parte, str) and parte.startswith("."):
                    return parte[1:]

    return None


# ============================================================
# TESTE 1 - EC2 PRIVADA E IMDSV2
# ============================================================

def test_ec2_privada_e_imdsv2():

    template = carregar_template()

    instancias = obter_recursos(
        template, "AWS::EC2::Instance"
    )

    assert len(instancias) == 1, (
        "Esperada exatamente uma instancia EC2"
    )

    instancia = next(iter(instancias.values()))["Properties"]

    subnet_ref = instancia.get("SubnetId", {}).get("Ref", "")

    assert "PrivateSubnet" in subnet_ref, (
        "EC2 nao referencia a subnet privada esperada"
    )

    subnets = obter_recursos(
        template, "AWS::EC2::Subnet"
    )

    assert subnet_ref in subnets, (
        "Subnet da EC2 nao encontrada"
    )

    subnet = subnets[subnet_ref]["Properties"]

    assert subnet.get(
        "MapPublicIpOnLaunch", False
    ) is False, (
        "Subnet permite atribuicao automatica de IP publico"
    )

    # Validar IMDSv2 no Launch Template associado
    launch_templates = obter_recursos(
        template, "AWS::EC2::LaunchTemplate"
    )

    assert launch_templates, (
        "Launch Template nao encontrado"
    )

    referencia_lt = instancia.get("LaunchTemplate", {})

    assert referencia_lt, (
        "EC2 sem Launch Template associado"
    )

    imdsv2_encontrado = False

    for nome, recurso in launch_templates.items():

        dados = recurso["Properties"].get(
            "LaunchTemplateData", {}
        )

        metadata = dados.get("MetadataOptions", {})

        if (
            metadata.get("HttpTokens") == "required"
            and nome in json.dumps(referencia_lt)
        ):
            imdsv2_encontrado = True

    assert imdsv2_encontrado, (
        "IMDSv2 obrigatorio nao encontrado"
    )


# ============================================================
# TESTE 2 - SEGURANCA DO AMAZON S3
# ============================================================

def test_s3_seguranca():

    template = carregar_template()

    buckets = obter_recursos(
        template, "AWS::S3::Bucket"
    )

    assert len(buckets) == 1, (
        "Esperado exatamente um bucket S3"
    )

    recurso = next(iter(buckets.values()))
    bucket = recurso["Properties"]

    # Bloqueio de acesso publico
    bloqueio = bucket.get(
        "PublicAccessBlockConfiguration", {}
    )

    for propriedade in [
        "BlockPublicAcls",
        "BlockPublicPolicy",
        "IgnorePublicAcls",
        "RestrictPublicBuckets",
    ]:
        assert bloqueio.get(propriedade) is True, (
            f"{propriedade} nao esta habilitado"
        )

    # Criptografia SSE-S3
    regras = bucket.get(
        "BucketEncryption", {}
    ).get(
        "ServerSideEncryptionConfiguration", []
    )

    assert any(
        regra.get(
            "ServerSideEncryptionByDefault", {}
        ).get("SSEAlgorithm") == "AES256"
        for regra in regras
    ), "Criptografia AES256 nao encontrada"

    # Versionamento
    assert bucket.get(
        "VersioningConfiguration", {}
    ).get("Status") == "Enabled", (
        "Versionamento nao habilitado"
    )

    # Retencao
    assert recurso.get("DeletionPolicy") == "Retain", (
        "Bucket sem politica de retencao"
    )


# ============================================================
# TESTE 3 - IAM LEAST PRIVILEGE S3
# ============================================================

def test_iam_least_privilege_s3():

    template = carregar_template()

    policies = obter_recursos(
        template, "AWS::IAM::Policy"
    )

    assert policies, (
        "Nenhuma IAM Policy encontrada"
    )

    buckets = obter_recursos(
        template, "AWS::S3::Bucket"
    )

    assert len(buckets) == 1

    bucket_id = next(iter(buckets.keys()))

    permissoes_leitura = []

    for recurso in policies.values():

        documento = recurso["Properties"]["PolicyDocument"]

        statements = documento.get("Statement", [])

        if isinstance(statements, dict):
            statements = [statements]

        for statement in statements:

            if statement.get("Effect") != "Allow":
                continue

            acoes = obter_acoes(statement)

            assert "*" not in acoes, (
                "Permissao administrativa global encontrada"
            )

            assert "s3:*" not in acoes, (
                "Permissao S3 irrestrita encontrada"
            )

            if "s3:GetObject" in acoes:
                permissoes_leitura.append(statement)

    assert permissoes_leitura, (
        "Permissao s3:GetObject nao encontrada"
    )

    assert any(
        bucket_id in json.dumps(
            statement.get("Resource", "")
        )
        and "/*" in json.dumps(
            statement.get("Resource", "")
        )
        for statement in permissoes_leitura
    ), (
        "Permissao de leitura nao esta limitada "
        "aos objetos do bucket SecureCorp"
    )


# ============================================================
# TESTE 4 - VPC ENDPOINTS
# ============================================================

def test_vpc_endpoints():

    template = carregar_template()

    recursos = obter_recursos(
        template, "AWS::EC2::VPCEndpoint"
    )

    assert len(recursos) >= 3, (
        "Esperados pelo menos 3 VPC Endpoints"
    )

    endpoints = {}

    for recurso in recursos.values():

        propriedades = recurso["Properties"]
        servico = nome_servico_endpoint(propriedades)

        if servico:
            endpoints.setdefault(
                servico, []
            ).append(propriedades)

    # S3 Gateway Endpoint
    assert len(endpoints.get("s3", [])) == 1, (
        "Endpoint S3 nao encontrado"
    )

    s3 = endpoints["s3"][0]

    assert s3.get("VpcEndpointType") == "Gateway", (
        "Endpoint S3 nao e Gateway"
    )

    assert s3.get("RouteTableIds"), (
        "Endpoint S3 sem Route Tables"
    )

    # SSM Interface Endpoints
    for servico in ["ssm", "ssmmessages"]:

        encontrados = endpoints.get(servico, [])

        assert len(encontrados) == 1, (
            f"Endpoint {servico} nao encontrado"
        )

        endpoint = encontrados[0]

        assert endpoint.get(
            "VpcEndpointType"
        ) == "Interface", (
            f"Endpoint {servico} nao e Interface"
        )

        assert endpoint.get(
            "PrivateDnsEnabled"
        ) is True, (
            f"DNS privado desabilitado para {servico}"
        )

        assert endpoint.get("SecurityGroupIds"), (
            f"Endpoint {servico} sem Security Group"
        )

        assert endpoint.get("SubnetIds"), (
            f"Endpoint {servico} sem subnets"
        )


# ============================================================
# TESTE 5 - CLOUDWATCH + SNS
# ============================================================


def test_cloudwatch_sns():
    """Valida os tres alarmes CloudWatch e a integracao SNS."""

    template = carregar_template()

    alarmes = obter_recursos(
        template, "AWS::CloudWatch::Alarm"
    )
    topicos = obter_recursos(
        template, "AWS::SNS::Topic"
    )
    assinaturas = obter_recursos(
        template, "AWS::SNS::Subscription"
    )

    nomes_esperados = {
        "SecureCorp-EC2-HighCPU",
        "SecureCorp-EC2-SystemStatusFailed",
        "SecureCorp-EC2-InstanceStatusFailed",
    }

    alarmes_por_nome = {
        recurso["Properties"]["AlarmName"]: recurso["Properties"]
        for recurso in alarmes.values()
    }

    assert set(alarmes_por_nome) == nomes_esperados, (
        f"Alarmes incorretos: {set(alarmes_por_nome)}"
    )

    assert len(topicos) == 1, (
        "Esperado exatamente um topico SNS"
    )

    assert len(assinaturas) == 1, (
        "Esperada exatamente uma assinatura SNS"
    )

    topico_id = next(iter(topicos.keys()))

    # Verifica que todos os alarmes notificam o SNS
    for nome, alarme in alarmes_por_nome.items():
        assert alarme.get("Namespace") == "AWS/EC2", (
            f"Namespace incorreto: {nome}"
        )

        assert {"Ref": topico_id} in alarme.get(
            "AlarmActions", []
        ), f"Alarme sem notificacao SNS: {nome}"

        assert alarme.get("TreatMissingData") == "missing", (
            f"Tratamento de dados ausentes incorreto: {nome}"
        )

    # Alarme de CPU
    cpu = alarmes_por_nome["SecureCorp-EC2-HighCPU"]

    assert cpu["MetricName"] == "CPUUtilization"
    assert cpu["Statistic"] == "Average"
    assert cpu["Threshold"] == 80
    assert cpu["Period"] == 300
    assert cpu["EvaluationPeriods"] == 1
    assert cpu["DatapointsToAlarm"] == 1
    assert cpu["ComparisonOperator"] == "GreaterThanThreshold"

    # Alarmes de integridade EC2
    metricas_status = {
        "SecureCorp-EC2-SystemStatusFailed":
            "StatusCheckFailed_System",
        "SecureCorp-EC2-InstanceStatusFailed":
            "StatusCheckFailed_Instance",
    }

    for nome, metrica in metricas_status.items():
        alarme = alarmes_por_nome[nome]

        assert alarme["MetricName"] == metrica
        assert alarme["Statistic"] == "Maximum"
        assert alarme["Threshold"] == 0
        assert alarme["Period"] == 60
        assert alarme["EvaluationPeriods"] == 2
        assert alarme["DatapointsToAlarm"] == 2
        assert (
            alarme["ComparisonOperator"]
            == "GreaterThanThreshold"
        )

    # Assinatura de notificacoes SNS
    assinatura = next(
        iter(assinaturas.values())
    )["Properties"]

    assert assinatura["Protocol"] == "email"
    assert assinatura["TopicArn"] == {"Ref": topico_id}
    assert assinatura.get("Endpoint"), (
        "Assinatura SNS sem destinatario"
    )
