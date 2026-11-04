output "public_route_table_id" {
  description = "Route table shared by the public subnets."
  value       = aws_route_table.public.id
}

output "private_route_table_ids" {
  description = "Private route table ids keyed by AZ."
  value       = { for az, table in aws_route_table.private : az => table.id }
}

output "data_route_table_id" {
  description = "Data tier route table (null when no data subnets exist)."
  value       = length(aws_route_table.data) > 0 ? aws_route_table.data[0].id : null
}

output "nat_gateway_ids" {
  description = "NAT gateway ids keyed by AZ."
  value       = { for az, nat in aws_nat_gateway.this : az => nat.id }
}

output "nat_public_ips" {
  description = "Elastic IPs allocated to the NAT gateways."
  value       = { for az, eip in aws_eip.nat : az => eip.public_ip }
}
