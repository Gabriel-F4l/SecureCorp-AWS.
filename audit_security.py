
import json
from pathlib import Path

arquivo = Path("securecorp-check.json")

if not arquivo.exists():
    raise SystemExit("Template nao encontrado. Execute cdk synth primeiro.")

template = json.loads(arquivo.read_text(encoding="utf-16"))
recursos = template.get("Resources", {})

def verificar(nome, condicao):
    status = "OK" if condicao else "FALHA"
    print(f"[{status}] {nome}")

buckets = [
    r["Properties"]
    for r in recursos.values()
    if r.get("Type") == "AWS::S3::Bucket"
]

endpoints = [
    r["Properties"]
    for r in recursos.values()
    if r.get("Type") == "AWS::EC2::VPCEndpoint"
]

print("\n=== SECURECORP SECURITY AUDIT ===\n")

verificar("Bucket S3 presente", len(buckets) > 0)

for bucket in buckets:
    bloqueio = bucket.get("PublicAccessBlockConfiguration", {})
    verificar(
        "S3 com acesso publico bloqueado",
        all(bloqueio.get(k) is True for k in [
            "BlockPublicAcls",
            "BlockPublicPolicy",
            "IgnorePublicAcls",
            "RestrictPublicBuckets"
        ])
    )

    verificar(
        "Versionamento habilitado",
        bucket.get("VersioningConfiguration", {}).get("Status") == "Enabled"
    )

    verificar(
        "Criptografia configurada",
        bool(bucket.get("BucketEncryption"))
    )

verificar(
    "Gateway Endpoint S3 configurado",
    any(
        e.get("VpcEndpointType") == "Gateway"
        and "s3" in json.dumps(e.get("ServiceName", {})).lower()
        and len(e.get("RouteTableIds", [])) == 2
        for e in endpoints
    )
)

print("\nAuditoria local concluida.")


print("\n=== AUDITORIA IAM ===\n")

policies = [
    r["Properties"]
    for r in recursos.values()
    if r.get("Type") == "AWS::IAM::Policy"
]

for policy in policies:
    statements = policy.get("PolicyDocument", {}).get("Statement", [])

    if isinstance(statements, dict):
        statements = [statements]

    for statement in statements:
        actions = statement.get("Action", [])
        if isinstance(actions, str):
            actions = [actions]

        effect = statement.get("Effect")
        resource = statement.get("Resource")

        if effect == "Allow" and "*" in actions:
            print("[ALERTA] Permissao global de acao detectada!")
        elif effect == "Allow":
            print("[INFO] Acoes permitidas:", actions)
            print("[INFO] Recursos autorizados:", resource)    
print("\n=== AUDITORIA SECURITY GROUP ===\n")

for nome, recurso in recursos.items():

    tipo = recurso.get("Type", "")

    if tipo not in [
        "AWS::EC2::SecurityGroupIngress",
        "AWS::EC2::SecurityGroupEgress"
    ]:
        continue

    propriedades = recurso.get("Properties", {})

    cidr = propriedades.get("CidrIp")
    porta = propriedades.get("FromPort")
    protocolo = propriedades.get("IpProtocol")

    print(f"\nRecurso: {nome}")
    print(f"Tipo: {tipo}")
    print(f"Origem/Destino: {cidr}")
    print(f"Porta inicial: {porta}")
    print(f"Protocolo: {protocolo}")

    if cidr == "0.0.0.0/0":
        print("[ALERTA] Regra aberta para qualquer IPv4")
    elif cidr:
        print("[INFO] Regra com CIDR especifico")
    else:
        print("[INFO] Verificar outros tipos de destino")
