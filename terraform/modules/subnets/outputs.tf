output "subnet_ids" {
  description = "All subnet ids keyed by short name."
  value       = { for key, subnet in aws_subnet.this : key => subnet.id }
}

output "public_subnet_ids" {
  description = "Public subnet ids keyed by short name."
  value       = { for key, subnet in local.public_subnets : key => aws_subnet.this[key].id }
}

output "private_subnet_ids" {
  description = "Private subnet ids keyed by short name."
  value       = { for key, subnet in local.private_subnets : key => aws_subnet.this[key].id }
}

output "data_subnet_ids" {
  description = "Data tier subnet ids keyed by short name."
  value       = { for key, subnet in local.data_subnets : key => aws_subnet.this[key].id }
}

output "public_subnet_ids_by_az" {
  description = "Public subnet id per availability zone."
  value       = { for key, subnet in local.public_subnets : subnet.availability_zone => aws_subnet.this[key].id }
}

output "private_subnet_ids_by_az" {
  description = "List of private subnet ids per availability zone."
  value = {
    for az in distinct([for s in values(local.private_subnets) : s.availability_zone]) :
    az => [for key, subnet in local.private_subnets : aws_subnet.this[key].id if subnet.availability_zone == az]
  }
}

output "data_subnet_ids_by_az" {
  description = "List of data subnet ids per availability zone."
  value = {
    for az in distinct([for s in values(local.data_subnets) : s.availability_zone]) :
    az => [for key, subnet in local.data_subnets : aws_subnet.this[key].id if subnet.availability_zone == az]
  }
}

output "availability_zones" {
  description = "Distinct AZs covered by the declared subnets."
  value       = sort(distinct([for subnet in values(var.subnets) : subnet.availability_zone]))
}
