
provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "SecureCorp-AWS"
      Environment = "dev"
      ManagedBy   = "Terraform"
    }
  }
}
