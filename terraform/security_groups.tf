
# ============================================================
# SecureCorp Automotive AWS - Security Groups
# Cloud Engineering | Cloud Security | Terraform IaC
#
# Objetivos:
# - Restringir o Security Group padrao da VPC
# - Bloquear conexoes de entrada na futura EC2
# - Permitir saida HTTPS somente para Amazon S3
# - Aplicar o principio do menor privilegio
# - Validar configuracoes com Checkov
#
# Ambiente:
# - Laboratorio de infraestrutura como codigo
# - Nenhuma EC2 provisionada nesta etapa
# - Nenhum terraform apply automatico
# ============================================================


# ------------------------------------------------------------
# 1. MANAGED PREFIX LIST - AMAZON S3
# ------------------------------------------------------------

data "aws_prefix_list" "s3" {
  name = "com.amazonaws.${var.aws_region}.s3"
}


# ------------------------------------------------------------
# 2. SECURITY GROUP - APLICACAO SECURECORP
# ------------------------------------------------------------

resource "aws_security_group" "app_server" {

  # Excecao temporaria de seguranca:
  # O Security Group sera associado a uma EC2 privada
  # em uma futura etapa do projeto.
  #
  # A ausencia de associacao e intencional nesta fase.
  #
  #checkov:skip=CKV2_AWS_5:Security Group reservado para futura EC2 privada

  name_prefix = "securecorp-app-"

  description = "Security Group da aplicacao SecureCorp"

  vpc_id = aws_vpc.securecorp.id

  # ----------------------------------------------------------
  # INGRESS - ENTRADA
  # ----------------------------------------------------------

  # Bloqueia todas as conexoes de entrada.
  # Principio: Deny by Default.

  ingress = []

  # ----------------------------------------------------------
  # EGRESS - SAIDA
  # ----------------------------------------------------------

  # Remove as permissoes padrao de saida.
  # O acesso ao S3 sera definido em regra separada.

  egress = []

  # ----------------------------------------------------------
  # TAGS
  # ----------------------------------------------------------

  tags = {
    Name        = "SecureCorp-App-SG"
    Project     = var.project_name
    Environment = "Lab"
    ManagedBy   = "Terraform"
    Security    = "Restricted"
  }
}


# ------------------------------------------------------------
# 3. EGRESS RULE - HTTPS PARA AMAZON S3
# ------------------------------------------------------------

resource "aws_vpc_security_group_egress_rule" "app_to_s3" {

  security_group_id = aws_security_group.app_server.id

  description = "HTTPS para Amazon S3 via Gateway Endpoint"

  ip_protocol = "tcp"

  from_port = 443
  to_port   = 443

  # Restringe o destino aos prefixos gerenciados do S3.
  prefix_list_id = data.aws_prefix_list.s3.id
}


# ------------------------------------------------------------
# 4. DEFAULT SECURITY GROUP - VPC
# ------------------------------------------------------------

resource "aws_default_security_group" "default" {

  vpc_id = aws_vpc.securecorp.id

  # Bloqueia todas as conexoes de entrada.
  ingress = []

  # Bloqueia todas as conexoes de saida.
  egress = []

  tags = {
    Name        = "SecureCorp-Default-SG-Restricted"
    Project     = var.project_name
    Environment = "Lab"
    ManagedBy   = "Terraform"
    Security    = "DenyAll"
  }
}


# ============================================================
# END - SECURECORP AUTOMOTIVE SECURITY GROUPS
# ============================================================
