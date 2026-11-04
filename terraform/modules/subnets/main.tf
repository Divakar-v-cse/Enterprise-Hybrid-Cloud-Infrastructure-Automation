locals {
  public_subnets  = { for key, subnet in var.subnets : key => subnet if subnet.tier == "public" }
  private_subnets = { for key, subnet in var.subnets : key => subnet if subnet.tier == "private" }
  data_subnets    = { for key, subnet in var.subnets : key => subnet if subnet.tier == "data" }
}

resource "aws_subnet" "this" {
  for_each = var.subnets

  vpc_id                  = var.vpc_id
  cidr_block              = each.value.cidr_block
  availability_zone       = each.value.availability_zone
  map_public_ip_on_launch = each.value.map_public_ip_on_launch

  tags = merge(
    var.tags,
    {
      Name   = "${var.name}-${each.key}"
      Tier   = each.value.tier
      Module = "subnets"
    }
  )
}

# Public subnets should never auto-assign public IPs: egress is arbitrated by
# the ALB and NAT gateways, not by instance-level addressing. The environment
# layer enforces this (see `map_public_ip_on_launch = false` in each subnet).
