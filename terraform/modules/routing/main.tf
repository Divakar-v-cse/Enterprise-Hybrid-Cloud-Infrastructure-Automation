locals {
  private_azs = keys(var.private_subnet_ids_by_az)
  nat_azs     = var.enable_nat_gateway ? (var.single_nat_gateway ? [local.private_azs[0]] : local.private_azs) : []
  nat_owner   = { for az in local.private_azs : az => (var.single_nat_gateway ? local.nat_azs[0] : az) }

  tags = merge(var.tags, { Module = "routing" })
}

# ---------------------------------------------------------------------------
# Public routing: 0.0.0.0/0 -> internet gateway
# ---------------------------------------------------------------------------
resource "aws_route_table" "public" {
  vpc_id = var.vpc_id

  tags = merge(local.tags, { Name = "${var.name}-public", Tier = "public" })
}

resource "aws_route" "public_internet" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = var.internet_gateway_id
}

resource "aws_route_table_association" "public" {
  for_each = var.public_subnet_ids

  subnet_id      = each.value
  route_table_id = aws_route_table.public.id
}

# ---------------------------------------------------------------------------
# NAT gateways: one per AZ unless single_nat_gateway is enabled
# ---------------------------------------------------------------------------
resource "aws_eip" "nat" {
  for_each = toset(local.nat_azs)

  domain = "vpc"

  tags = merge(local.tags, { Name = "${var.name}-nat-${each.key}" })
}

resource "aws_nat_gateway" "this" {
  for_each = toset(local.nat_azs)

  allocation_id = aws_eip.nat[each.key].id
  subnet_id     = var.public_subnet_ids_by_az[each.key]

  depends_on = [aws_eip.nat]

  tags = merge(local.tags, { Name = "${var.name}-nat-${each.key}" })
}

# ---------------------------------------------------------------------------
# Private routing: one table per AZ, default route to the AZ-local NAT
# ---------------------------------------------------------------------------
resource "aws_route_table" "private" {
  for_each = var.private_subnet_ids_by_az

  vpc_id = var.vpc_id

  tags = merge(local.tags, { Name = "${var.name}-private-${each.key}", Tier = "private" })
}

resource "aws_route" "private_nat" {
  for_each = var.enable_nat_gateway ? var.private_subnet_ids_by_az : {}

  route_table_id         = aws_route_table.private[each.key].id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.this[local.nat_owner[each.key]].id
}

resource "aws_route_table_association" "private" {
  for_each = merge([
    for az, subnet_ids in var.private_subnet_ids_by_az : {
      for subnet_id in subnet_ids : subnet_id => { az = az, subnet_id = subnet_id }
    }
  ]...)

  subnet_id      = each.value.subnet_id
  route_table_id = aws_route_table.private[each.value.az].id
}

# ---------------------------------------------------------------------------
# Data tier routing: no default route at all (isolated by design)
# ---------------------------------------------------------------------------
resource "aws_route_table" "data" {
  count = length(var.data_subnet_ids) > 0 ? 1 : 0

  vpc_id = var.vpc_id

  tags = merge(local.tags, { Name = "${var.name}-data", Tier = "data" })
}

resource "aws_route_table_association" "data" {
  for_each = var.data_subnet_ids

  subnet_id      = each.value
  route_table_id = aws_route_table.data[0].id
}
