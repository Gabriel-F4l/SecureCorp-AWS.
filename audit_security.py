
import json
import sys
from pathlib import Path

# ==========================================================
# SECURECORP AWS - AUTOMATED SECURITY AUDIT
# ==========================================================

BASE_DIR = Path(__file__).resolve().parent
CDK_OUT = BASE_DIR / "cdk.out"

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
    if not CDK_OUT.is_dir():
        raise SystemExit(
            f"Diretorio nao encontrado: {CDK_OUT}\n"
            "Execute: cdk synth --output cdk.out"
        )

    templates = sorted(CDK_OUT.glob("*.template.json"))

    if len(templates) != 1:
        encontrados = [p.name for p in templates]
        raise SystemExit(
            "Esperado exatamente um template CloudFormation. "
            f"Encontrados: {encontrados}"
        )

    arquivo = templates[0]

    try:
        template = json.loads(
            arquivo.read_text(encoding="utf-8-sig")
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as erro:
        raise SystemExit(
            f"Erro ao carregar template: {erro}"
        ) from erro

    if not isinstance(template, dict):
        raise SystemExit("Template CloudFormation invalido.")

    recursos = template.get("Resources")

    if not isinstance(recursos, dict):
        raise SystemExit("Secao Resources invalida.")

    print(f"[OK] Template carregado: {arquivo.name}")
    print(f"[INFO] Recursos encontrados: {len(recursos)}")

    return recursos


def obter_recursos(recursos, tipo):
    return [
        recurso.get("Properties", {})
        for recurso in recursos.values()
        if recurso.get("Type") == tipo
    ]


def como_lista(valor):
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

    verificar("Bucket S3 presente", bool(buckets))

    for bucket in buckets:
        bloqueio = bucket.get(
            "PublicAccessBlockConfiguration", {}
        )

        chaves = [
            "BlockPublicAcls",
            "BlockPublicPolicy",
            "IgnorePublicAcls",
            "RestrictPublicBuckets"
        ]

        verificar(
            "S3 com acesso publico bloqueado",
            all(bloqueio.get(k) is True for k in chaves)
        )

        verificar(
            "Versionamento habilitado",
            bucket.get(
                "VersioningConfiguration", {}
            ).get("Status") == "Enabled"
        )

        verificar(
            "Criptografia configurada",
            bool(
                bucket.get(
                    "BucketEncryption", {}
                ).get("ServerSideEncryptionConfiguration")
            )
        )


def auditoria_endpoints(recursos):
    print("\n=== AUDITORIA VPC ENDPOINT ===\n")

    endpoints = obter_recursos(
        recursos, "AWS::EC2::VPCEndpoint"
    )

    gateways = [
        endpoint
        for endpoint in endpoints
        if endpoint.get("VpcEndpointType") == "Gateway"
        and "s3" in json.dumps(
            endpoint.get("ServiceName", {})
        ).lower()
    ]

    verificar(
        "Gateway Endpoint S3 configurado",
        bool(gateways)
    )

    for gateway in gateways:
        rotas = gateway.get("RouteTableIds", [])

        verificar(
            "Gateway associado a duas Route Tables",
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
        bool(documentos)
    )

    for documento in documentos:
        for statement in como_lista(
            documento.get("Statement", [])
        ):
            if not isinstance(statement, dict):
                continue

            if statement.get("Effect") != "Allow":
                continue

            actions = como_lista(
                statement.get("Action", [])
            )

            resources = como_lista(
                statement.get("Resource", [])
            )

            print(f"[INFO] Acoes: {actions}")
            print(f"[INFO] Recursos: {resources}")

            if "*" in actions:
                alerta("IAM permite todas as acoes")

            if "*" in resources:
                alerta("IAM permite Resource '*'")

            if any(
                isinstance(a, str) and a.endswith(":*")
                for a in actions
            ):
                alerta("IAM possui permissao ampla por servico")


def auditoria_security_groups(recursos):
    print("\n=== AUDITORIA SECURITY GROUP ===\n")

    regras = []

    for nome, recurso in recursos.items():
        tipo = recurso.get("Type", "")
        props = recurso.get("Properties", {})

        if tipo in [
            "AWS::EC2::SecurityGroupIngress",
            "AWS::EC2::SecurityGroupEgress"
        ]:
            regras.append((nome, tipo, props))

        elif tipo == "AWS::EC2::SecurityGroup":
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
        bool(regras)
    )

    for nome, tipo, props in regras:
        direcao = (
            "ENTRADA" if tipo.endswith("Ingress")
            else "SAIDA"
        )

        cidr = props.get("CidrIp")
        ipv6 = props.get("CidrIpv6")
        porta = props.get("FromPort")
        protocolo = props.get("IpProtocol")

        print(f"\nRecurso: {nome}")
        print(f"Direcao: {direcao}")
        print(f"CIDR IPv4: {cidr}")
        print(f"CIDR IPv6: {ipv6}")
        print(f"Porta: {porta}")
        print(f"Protocolo: {protocolo}")

        if cidr == "0.0.0.0/0":
            alerta(f"{nome}: acesso IPv4 irrestrito")

        if ipv6 == "::/0":
            alerta(f"{nome}: acesso IPv6 irrestrito")

        if not cidr and not ipv6:
            print(
                "[INFO] Destino pode usar SG ou Prefix List"
            )


def main():
    print("\n====================================")
    print(" SECURECORP AWS - SECURITY AUDIT")
    print("====================================\n")

    recursos = carregar_template()

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

    if falhas:
        print("\n[FAIL] Auditoria reprovada.")
        return 1

    print("\n[OK] Auditoria concluida.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
