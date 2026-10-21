# ============================================================
# SecureCorp AWS - VPC Flow Logs
# Cloud Security | Observability | Infrastructure as Code
#
# Recursos:
# - CloudWatch Logs com retencao de 365 dias
# - Criptografia com AWS KMS
# - Rotacao automatica da chave KMS
# - IAM Role dedicada ao VPC Flow Logs
# - Captura de trafego ACCEPT e REJECT
# ============================================================

# ------------------------------------------------------------
# DATA SOURCES
# ------------------------------------------------------------

data "aws_caller_identity" "current" {}

# ------------------------------------------------------------
# AWS KMS - ENCRYPTION KEY
# ------------------------------------------------------------

resource "aws_kms_key" "vpc_logs" {
  description             = "SecureCorp VPC Flow Logs encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Sid    = "EnableAccountAdministration"
        Effect = "Allow"

        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }

        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "AllowCloudWatchLogs"
        Effect = "Allow"

        Principal = {
          Service = "logs.${var.aws_region}.amazonaws.com"
        }

        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:DescribeKey"
        ]

        Resource = "*"

        Condition = {
          ArnEquals = {
            "kms:EncryptionContext:aws:logs:arn" = "arn:${data.aws_partition.current.partition}:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/vpc/securecorp-flow-logs"
          }
        }
      }
    ]
  })

  tags = {
    Name    = "SecureCorp-VPC-Logs-KMS"
    Project = local.project
  }
}

# ------------------------------------------------------------
# AWS PARTITION
# ------------------------------------------------------------

data "aws_partition" "current" {}

# ------------------------------------------------------------
# KMS ALIAS
# ------------------------------------------------------------

resource "aws_kms_alias" "vpc_logs" {
  name          = "alias/securecorp-vpc-flow-logs"
  target_key_id = aws_kms_key.vpc_logs.key_id
}

# ------------------------------------------------------------
# CLOUDWATCH LOG GROUP
# ------------------------------------------------------------

resource "aws_cloudwatch_log_group" "vpc_flow_logs" {
  name = "/aws/vpc/securecorp-flow-logs"

  retention_in_days = 365

  kms_key_id = aws_kms_key.vpc_logs.arn

  tags = {
    Name    = "SecureCorp-VPC-FlowLogs"
    Project = local.project
  }
}

# ------------------------------------------------------------
# IAM ROLE - VPC FLOW LOGS
# ------------------------------------------------------------

resource "aws_iam_role" "vpc_flow_logs" {
  name_prefix = "securecorp-vpc-flow-logs-"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Sid    = "AllowVPCFlowLogsService"
        Effect = "Allow"

        Principal = {
          Service = "vpc-flow-logs.amazonaws.com"
        }

        Action = "sts:AssumeRole"

        Condition = {
          StringEquals = {
            "aws:SourceAccount" = data.aws_caller_identity.current.account_id
          }
          ArnLike = {
            "aws:SourceArn" = "arn:${data.aws_partition.current.partition}:ec2:${var.aws_region}:${data.aws_caller_identity.current.account_id}:vpc-flow-log/*"
          }
        }
      }
    ]
  })

  tags = {
    Name    = "SecureCorp-VPC-FlowLogs-Role"
    Project = local.project
  }
}

# ------------------------------------------------------------
# IAM POLICY - CLOUDWATCH LOGS
# ------------------------------------------------------------

resource "aws_iam_role_policy" "vpc_flow_logs" {
  name = "SecureCorp-VPC-FlowLogs-Policy"
  role = aws_iam_role.vpc_flow_logs.id

  policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Sid    = "AllowWriteFlowLogs"
        Effect = "Allow"

        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams"
        ]

        Resource = [
          "${aws_cloudwatch_log_group.vpc_flow_logs.arn}:*"
        ]
      },
      {
        Sid    = "AllowDescribeLogGroups"
        Effect = "Allow"

        Action = [
          "logs:DescribeLogGroups"
        ]

        Resource = "*"
      }
    ]
  })
}

# ------------------------------------------------------------
# VPC FLOW LOGS
# ------------------------------------------------------------

resource "aws_flow_log" "securecorp" {
  vpc_id = aws_vpc.securecorp.id

  traffic_type = "ALL"

  log_destination_type = "cloud-watch-logs"
  log_destination      = aws_cloudwatch_log_group.vpc_flow_logs.arn

  iam_role_arn = aws_iam_role.vpc_flow_logs.arn

  max_aggregation_interval = 60

  depends_on = [
    aws_iam_role_policy.vpc_flow_logs
  ]

  tags = {
    Name    = "SecureCorp-VPC-FlowLogs"
    Project = local.project
    Managed = "Terraform"
  }
}

# ============================================================
# END - SECURECORP VPC FLOW LOGS
# ============================================================
