# ============================================================
# SecureCorp AWS - Terraform Network Foundation
# Cloud Engineering | Networking | Security | IaC
#
# Arquitetura:
# - VPC 10.20.0.0/16
# - 2 Availability Zones com identidades fixas
# - 2 sub-redes publicas
# - 2 sub-redes privadas isoladas
# - Internet Gateway
# - Tabelas de roteamento segregadas
# - Gateway VPC Endpoint para Amazon S3
# - Sem NAT Gateway
# - Sem IP publico automatico
# ============================================================

# ------------------------------------------------------------
# DATA SOURCES
# ------------------------------------------------------------

data "aws_region" "current" {}

# ------------------------------------------------------------
# LOCAL VARIABLES
# ------------------------------------------------------------

locals {
  project = var.project_name

  # IDs de zonas fixados nas variaveis
  az_a = var.availability_zone_ids[0]
  az_b = var.availability_zone_ids[1]

  common_tags = {
    Project     = local.project
    ManagedBy   = "Terraform"
    Environment = "Lab"
  }
}

# ------------------------------------------------------------
# VPC
# ------------------------------------------------------------

resource "aws_vpc" "securecorp" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = merge(local.common_tags, {
    Name = "SecureCorp-VPC"
  })
}

# ------------------------------------------------------------
# INTERNET GATEWAY
# ------------------------------------------------------------

resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.securecorp.id

  tags = merge(local.common_tags, {
    Name = "SecureCorp-IGW"
  })
}

# ------------------------------------------------------------
# PUBLIC SUBNET A
# ------------------------------------------------------------

resource "aws_subnet" "public_a" {
  vpc_id                  = aws_vpc.securecorp.id
  cidr_block              = "10.20.1.0/24"
  availability_zone_id    = local.az_a
  map_public_ip_on_launch = false

  tags = merge(local.common_tags, {
    Name = "SecureCorp-Public-A"
    Tier = "Public"
  })
}

# ------------------------------------------------------------
# PUBLIC SUBNET B
# ------------------------------------------------------------

resource "aws_subnet" "public_b" {
  vpc_id                  = aws_vpc.securecorp.id
  cidr_block              = "10.20.2.0/24"
  availability_zone_id    = local.az_b
  map_public_ip_on_launch = false

  tags = merge(local.common_tags, {
    Name = "SecureCorp-Public-B"
    Tier = "Public"
  })
}

# ------------------------------------------------------------
# PRIVATE ISOLATED SUBNET A
# ------------------------------------------------------------

resource "aws_subnet" "private_a" {
  vpc_id                  = aws_vpc.securecorp.id
  cidr_block              = "10.20.11.0/24"
  availability_zone_id    = local.az_a
  map_public_ip_on_launch = false

  tags = merge(local.common_tags, {
    Name = "SecureCorp-Private-A"
    Tier = "Isolated"
  })
}

# ------------------------------------------------------------
# PRIVATE ISOLATED SUBNET B
# ------------------------------------------------------------

resource "aws_subnet" "private_b" {
  vpc_id                  = aws_vpc.securecorp.id
  cidr_block              = "10.20.12.0/24"
  availability_zone_id    = local.az_b
  map_public_ip_on_launch = false

  tags = merge(local.common_tags, {
    Name = "SecureCorp-Private-B"
    Tier = "Isolated"
  })
}

# ------------------------------------------------------------
# PUBLIC ROUTE TABLE
# ------------------------------------------------------------

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.securecorp.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.igw.id
  }

  tags = merge(local.common_tags, {
    Name = "SecureCorp-Public-RT"
  })
}

# ------------------------------------------------------------
# PUBLIC ROUTE ASSOCIATIONS
# ------------------------------------------------------------

resource "aws_route_table_association" "public_a" {
  subnet_id      = aws_subnet.public_a.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "public_b" {
  subnet_id      = aws_subnet.public_b.id
  route_table_id = aws_route_table.public.id
}

# ------------------------------------------------------------
# PRIVATE ISOLATED ROUTE TABLE
# Sem rota default para Internet ou NAT
# ------------------------------------------------------------

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.securecorp.id

  tags = merge(local.common_tags, {
    Name = "SecureCorp-Isolated-RT"
  })
}

# ------------------------------------------------------------
# PRIVATE ROUTE ASSOCIATIONS
# ------------------------------------------------------------

resource "aws_route_table_association" "private_a" {
  subnet_id      = aws_subnet.private_a.id
  route_table_id = aws_route_table.private.id
}

resource "aws_route_table_association" "private_b" {
  subnet_id      = aws_subnet.private_b.id
  route_table_id = aws_route_table.private.id
}

# ------------------------------------------------------------
# AMAZON S3 GATEWAY VPC ENDPOINT
# Acesso privado ao S3 sem NAT Gateway
# ------------------------------------------------------------

resource "aws_vpc_endpoint" "s3" {
  vpc_id = aws_vpc.securecorp.id

  service_name = "com.amazonaws.${data.aws_region.current.region}.s3"

  vpc_endpoint_type = "Gateway"

  route_table_ids = [
    aws_route_table.private.id
  ]

  tags = merge(local.common_tags, {
    Name = "SecureCorp-S3-Endpoint"
  })
}

# ============================================================
# END - SECURECORP NETWORK FOUNDATION
# ============================================================
