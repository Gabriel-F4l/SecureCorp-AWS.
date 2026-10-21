
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
