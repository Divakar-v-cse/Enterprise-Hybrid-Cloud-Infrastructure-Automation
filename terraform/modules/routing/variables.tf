variable "name" {
  description = "Name prefix for route tables and NAT gateways."
  type        = string
}

variable "vpc_id" {
  description = "VPC the route tables belong to."
  type        = string
}

variable "internet_gateway_id" {
  description = "Internet gateway used by the public route table."
  type        = string
}

variable "public_subnet_ids" {
  description = "Public subnet ids keyed by short name."
  type        = map(string)
}

variable "public_subnet_ids_by_az" {
  description = "Public subnet id per AZ (NAT gateways are placed here)."
  type        = map(string)
}

variable "private_subnet_ids_by_az" {
  description = "Private subnet ids per AZ."
  type        = map(list(string))
}

variable "data_subnet_ids" {
  description = "Data tier subnet ids keyed by short name (no internet egress)."
  type        = map(string)
  default     = {}
}

variable "enable_nat_gateway" {
  description = "Create NAT gateways so private subnets can reach the internet."
  type        = bool
  default     = true
}

variable "single_nat_gateway" {
  description = "Use one NAT gateway for all AZs (cheaper, non-HA - dev only)."
  type        = bool
  default     = false
}

variable "tags" {
  description = "Additional tags merged onto every resource."
  type        = map(string)
  default     = {}
}
