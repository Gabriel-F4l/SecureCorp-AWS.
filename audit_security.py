
import json
import sys
from pathlib import Path

# =====================================================
# SECURECORP AWS - SECURITY AUDIT
# Auditoria automatizada de infraestrutura CloudFormation
# =====================================================

BASE_DIR = Path(__file__).resolve().parent

TEMPLATE_PATH = (
    BASE_DIR
    / "cdk.out"
    / "SecureCorpAwsStack.template.json"
)

aprovados = 0
falhas = 0
alertas = 0


def verificar(nome, condicao):
    global aprovados, falhas

    if condicao:
        aprovados += 1
        print(f"[OK] {nome}")
    else:
        falhas += 1
        print(f"[FALHA] {nome}")


def alerta(mensagem):
    global alertas
    alertas += 1
    print(f"[ALERTA] {mensagem}")


def carregar_template():
    if not TEMPLATE_PATH.is_file():
        raise SystemExit(
            f"Template nao encontrado: {TEMPLATE_PATH}\n"
            "Execute: cdk synth --output cdk.out"
        )

    try:
        with TEMPLATE_PATH.open(
            "r", encoding="utf-8-sig"
        ) as arquivo:
            template = json.load(arquivo)

    except (OSError, UnicodeError, json.JSONDecodeError) as erro:
        raise SystemExit(
            f"Erro ao carregar template: {erro}"
        ) from erro

    if not isinstance(template, dict):
        raise SystemExit("Template CloudFormation invalido.")

    print(f"[OK] Template carregado: {TEMPLATE_PATH.name}")

    return template


def obter_recursos(recursos, tipo):
    return [
        r.get("Properties", {})
        for r in recursos.values()
        if r.get("Type") == tipo
    ]


def lista(valor):
    if valor is None:
        return []
    if isinstance(valor, list):
        return valor
    return [valor]


def auditoria_s3(recursos):
    print("\n=== AUDITORIA S3 ===\n")

    buckets = obter_recursos(
        recursos, "AWS::S3::Bucket"
    )

    verificar(
        "Bucket S3 presente",
        len(buckets) > 0
    )

    for bucket in buckets:
        bloqueio = bucket.get(
            "PublicAccessBlockConfiguration", {}
        )

        verificar(
            "S3 com acesso publico bloqueado",
            all(
                bloqueio.get(chave) is True
                for chave in [
                    "BlockPublicAcls",
                    "BlockPublicPolicy",
                    "IgnorePublicAcls",
                    "RestrictPublicBuckets"
                ]
            )
        )

        verificar(
            "Versionamento habilitado",
            bucket.get(
                "VersioningConfiguration", {}
            ).get("Status") == "Enabled"
        )

        criptografia = bucket.get(
            "BucketEncryption", {}
        )

        verificar(
            "Criptografia configurada",
            bool(criptografia.get(
                "ServerSideEncryptionConfiguration"
            ))
        )


def auditoria_endpoints(recursos):
    print("\n=== AUDITORIA VPC ENDPOINT ===\n")

    endpoints = obter_recursos(
        recursos, "AWS::EC2::VPCEndpoint"
    )

    gateway_s3 = [
        endpoint
        for endpoint in endpoints
        if endpoint.get("VpcEndpointType") == "Gateway"
        and "s3" in json.dumps(
            endpoint.get("ServiceName", {})
        ).lower()
    ]

    verificar(
        "Gateway Endpoint S3 configurado",
        len(gateway_s3) > 0
    )

    for endpoint in gateway_s3:
        rotas = endpoint.get("RouteTableIds", [])

        verificar(
            "Gateway S3 associado a duas route tables",
            len(rotas) == 2
        )


def auditoria_iam(recursos):
    print("\n=== AUDITORIA IAM ===\n")

    documentos = []

    for tipo in [
        "AWS::IAM::Policy",
        "AWS::IAM::ManagedPolicy"
    ]:
        for policy in obter_recursos(recursos, tipo):
            documentos.append(
                policy.get("PolicyDocument", {})
            )

    for role in obter_recursos(
        recursos, "AWS::IAM::Role"
    ):
        for policy in role.get("Policies", []):
            documentos.append(
                policy.get("PolicyDocument", {})
            )

    verificar(
        "Politicas IAM encontradas",
        len(documentos) > 0
    )

    for documento in documentos:
        statements = lista(
            documento.get("Statement", [])
        )

        for statement in statements:
            if not isinstance(statement, dict):
                continue

            if statement.get("Effect") != "Allow":
                continue

            actions = lista(
                statement.get("Action", [])
            )

            resources = lista(
                statement.get("Resource", [])
            )

            print(f"[INFO] Acoes IAM: {actions}")
            print(f"[INFO] Recursos IAM: {resources}")

            if "*" in actions:
                alerta(
                    "Permissao IAM com Action '*' detectada"
                )

            if "*" in resources:
                alerta(
                    "Permissao IAM com Resource '*' detectada"
                )


def auditoria_security_groups(recursos):
    print("\n=== AUDITORIA SECURITY GROUP ===\n")

    regras = []

    for nome, recurso in recursos.items():
        tipo = recurso.get("Type", "")

        if tipo in [
            "AWS::EC2::SecurityGroupIngress",
            "AWS::EC2::SecurityGroupEgress"
        ]:
            regras.append(
                (nome, tipo, recurso.get("Properties", {}))
            )

        elif tipo == "AWS::EC2::SecurityGroup":
            props = recurso.get("Properties", {})

            for regra in props.get("SecurityGroupIngress", []):
                regras.append(
                    (nome, "AWS::EC2::SecurityGroupIngress", regra)
                )

            for regra in props.get("SecurityGroupEgress", []):
                regras.append(
                    (nome, "AWS::EC2::SecurityGroupEgress", regra)
                )

    verificar(
        "Regras de Security Group encontradas",
        len(regras) > 0
    )

    for nome, tipo, props in regras:
        cidr = props.get("CidrIp")
        cidr_ipv6 = props.get("CidrIpv6")
        porta = props.get("FromPort")
        protocolo = props.get("IpProtocol")

        direcao = (
            "ENTRADA"
            if tipo.endswith("Ingress")
            else "SAIDA"
        )

        print(f"\nRecurso: {nome}")
        print(f"Direcao: {direcao}")
        print(f"CIDR IPv4: {cidr}")
        print(f"CIDR IPv6: {cidr_ipv6}")
        print(f"Porta: {porta}")
        print(f"Protocolo: {protocolo}")

        if cidr == "0.0.0.0/0":
            alerta(
                f"{nome}: regra aberta para qualquer IPv4"
            )

        if cidr_ipv6 == "::/0":
            alerta(
                f"{nome}: regra aberta para qualquer IPv6"
            )

        if not cidr and not cidr_ipv6:
            print(
                "[INFO] Destino pode utilizar "
                "Security Group ou Prefix List"
            )


def main():
    print("\n====================================")
    print(" SECURECORP AWS - SECURITY AUDIT")
    print("====================================")

    template = carregar_template()

    recursos = template.get("Resources", {})

    if not isinstance(recursos, dict):
        raise SystemExit("Resources invalido.")

    print(f"[INFO] Recursos encontrados: {len(recursos)}")

    auditoria_s3(recursos)
    auditoria_endpoints(recursos)
    auditoria_iam(recursos)
    auditoria_security_groups(recursos)

    print("\n====================================")
    print(" RESUMO DA AUDITORIA")
    print("====================================")

    print(f"Verificacoes aprovadas: {aprovados}")
    print(f"Verificacoes reprovadas: {falhas}")
    print(f"Alertas: {alertas}")

    if falhas > 0:
        print("\n[FAIL] Auditoria reprovada.")
        return 1

    print("\n[OK] Auditoria concluida.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
