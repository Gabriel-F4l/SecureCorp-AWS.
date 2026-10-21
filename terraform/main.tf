
# ============================================================
# SecureCorp AWS
# Terraform - Network Foundation
# Arquitetura Multi-AZ com acesso privado ao Amazon S3
# ============================================================

# ------------------------------------------------------------
# DATA SOURCES
# ------------------------------------------------------------

# Consulta a regiao AWS configurada no provider
data "aws_region" "current" {}

# Consulta as zonas de disponibilidade da regiao
data "aws_availability_zones" "available" {
  state = "available"
}

# ------------------------------------------------------------
# LOCAL VARIABLES
# ------------------------------------------------------------

locals {
  project = var.project_name

  az_a = data.aws_availability_zones.available.names[0]
  az_b = data.aws_availability_zones.available.names[1]
}

# ------------------------------------------------------------
# VPC
# ------------------------------------------------------------

resource "aws_vpc" "securecorp" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name    = "SecureCorp-VPC"
    Project = local.project
  }
}

# ------------------------------------------------------------
# INTERNET GATEWAY
# ------------------------------------------------------------

resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.securecorp.id

  tags = {
    Name    = "SecureCorp-IGW"
    Project = local.project
  }
}

# ------------------------------------------------------------
# PUBLIC SUBNETS - TWO AVAILABILITY ZONES
# ------------------------------------------------------------

resource "aws_subnet" "public_a" {
  vpc_id                  = aws_vpc.securecorp.id
  cidr_block              = "10.20.1.0/24"
  availability_zone       = local.az_a
  map_public_ip_on_launch = false

  tags = {
    Name    = "SecureCorp-Public-A"
    Project = local.project
    Tier    = "Public"
  }
}

resource "aws_subnet" "public_b" {
  vpc_id                  = aws_vpc.securecorp.id
  cidr_block              = "10.20.2.0/24"
  availability_zone       = local.az_b
  map_public_ip_on_launch = false

  tags = {
    Name    = "SecureCorp-Public-B"
    Project = local.project
    Tier    = "Public"
  }
}

# ------------------------------------------------------------
# PRIVATE ISOLATED SUBNETS
# No automatic public IP assignment
# No default route to the internet
# ------------------------------------------------------------

resource "aws_subnet" "private_a" {
  vpc_id                  = aws_vpc.securecorp.id
  cidr_block              = "10.20.11.0/24"
  availability_zone       = local.az_a
  map_public_ip_on_launch = false

  tags = {
    Name    = "SecureCorp-Private-A"
    Project = local.project
    Tier    = "Isolated"
  }
}

resource "aws_subnet" "private_b" {
  vpc_id                  = aws_vpc.securecorp.id
  cidr_block              = "10.20.12.0/24"
  availability_zone       = local.az_b
  map_public_ip_on_launch = false

  tags = {
    Name    = "SecureCorp-Private-B"
    Project = local.project
    Tier    = "Isolated"
  }
}

# ------------------------------------------------------------
# PUBLIC ROUTE TABLE
# Default route through Internet Gateway
# ------------------------------------------------------------

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.securecorp.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.igw.id
  }

  tags = {
    Name    = "SecureCorp-Public-RT"
    Project = local.project
  }
}

# Associate public subnet A
resource "aws_route_table_association" "public_a" {
  subnet_id      = aws_subnet.public_a.id
  route_table_id = aws_route_table.public.id
}

# Associate public subnet B
resource "aws_route_table_association" "public_b" {
  subnet_id      = aws_subnet.public_b.id
  route_table_id = aws_route_table.public.id
}

# ------------------------------------------------------------
# PRIVATE ISOLATED ROUTE TABLE
# No route to Internet Gateway or NAT Gateway
# ------------------------------------------------------------

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.securecorp.id

  tags = {
    Name    = "SecureCorp-Isolated-RT"
    Project = local.project
  }
}

# Associate private subnet A
resource "aws_route_table_association" "private_a" {
  subnet_id      = aws_subnet.private_a.id
  route_table_id = aws_route_table.private.id
}

# Associate private subnet B
resource "aws_route_table_association" "private_b" {
  subnet_id      = aws_subnet.private_b.id
  route_table_id = aws_route_table.private.id
}

# ------------------------------------------------------------
# AMAZON S3 GATEWAY VPC ENDPOINT
# Private connectivity to Amazon S3
# No NAT Gateway required
# ------------------------------------------------------------

resource "aws_vpc_endpoint" "s3" {
  vpc_id = aws_vpc.securecorp.id

  service_name = "com.amazonaws.${data.aws_region.current.region}.s3"

  vpc_endpoint_type = "Gateway"

  route_table_ids = [
    aws_route_table.private.id
  ]

  tags = {
    Name    = "SecureCorp-S3-Endpoint"
    Project = local.project
  }
}

# ============================================================
# END - SecureCorp Terraform Network Foundation
# ============================================================
