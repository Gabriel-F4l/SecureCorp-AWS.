
# SecureCorp AWS - Terraform Outputs

output "vpc_id" {
  description = "ID da VPC SecureCorp"
  value       = aws_vpc.securecorp.id
}

output "vpc_cidr" {
  description = "CIDR da VPC"
  value       = aws_vpc.securecorp.cidr_block
}

output "public_subnet_ids" {
  description = "IDs das subnets publicas"
  value = [
    aws_subnet.public_a.id,
    aws_subnet.public_b.id
  ]
}

output "private_subnet_ids" {
  description = "IDs das subnets privadas"
  value = [
    aws_subnet.private_a.id,
    aws_subnet.private_b.id
  ]
}

output "s3_endpoint_id" {
  description = "ID do Gateway VPC Endpoint S3"
  value       = aws_vpc_endpoint.s3.id
}

output "app_security_group_id" {
  description = "ID do Security Group da aplicacao"
  value       = aws_security_group.app_server.id
}
