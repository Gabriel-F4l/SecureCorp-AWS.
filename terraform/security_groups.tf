
# ============================================================
# SecureCorp AWS - Security Groups
# EC2 privada com acesso restrito ao Amazon S3
# ============================================================

# Consulta a Managed Prefix List do Amazon S3
data "aws_prefix_list" "s3" {
  name = "com.amazonaws.${var.aws_region}.s3"
}

# Security Group da futura EC2
resource "aws_security_group" "app_server" {
  name_prefix = "securecorp-app-"
  description = "Security Group da aplicacao SecureCorp"
  vpc_id      = aws_vpc.securecorp.id

  # Nenhuma regra de entrada
  # Nenhuma regra de saida automatica

  tags = {
    Name = "SecureCorp-App-SG"
  }
}

# Permite apenas HTTPS de saida para o Amazon S3
resource "aws_vpc_security_group_egress_rule" "app_to_s3" {
  security_group_id = aws_security_group.app_server.id

  description = "HTTPS para Amazon S3 via Gateway Endpoint"

  ip_protocol = "tcp"
  from_port   = 443
  to_port     = 443

  prefix_list_id = data.aws_prefix_list.s3.id
}
