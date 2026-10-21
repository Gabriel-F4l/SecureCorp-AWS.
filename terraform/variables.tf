
variable "aws_region" {
  description = "Regiao AWS do ambiente SecureCorp"
  type        = string
  default     = "sa-east-1"
}

variable "project_name" {
  description = "Nome do projeto"
  type        = string
  default     = "SecureCorp-AWS"
}

variable "vpc_cidr" {
  description = "Bloco CIDR da VPC"
  type        = string
  default     = "10.20.0.0/16"
}

# ------------------------------------------------------------
# AVAILABILITY ZONES - SECURECORP AWS
# ------------------------------------------------------------

variable "availability_zone_ids" {
  description = "IDs de duas Availability Zones para arquitetura Multi-AZ"
  type        = list(string)

  validation {
    condition = (
      length(var.availability_zone_ids) == 2 &&
      length(distinct(var.availability_zone_ids)) == 2
    )

    error_message = "Informe exatamente duas Availability Zones distintas."
  }
}

