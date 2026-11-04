data "aws_iam_policy_document" "assume_role" {
  count = var.trust_policy_json == null ? 1 : 0

  statement {
    sid     = "AssumeRole"
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    dynamic "principals" {
      for_each = toset(var.assume_role_principals)

      content {
        type        = "Service"
        identifiers = [principals.value]
      }
    }
  }
}

resource "aws_iam_role" "this" {
  name                 = var.name
  description          = var.description
  assume_role_policy   = var.trust_policy_json != null ? var.trust_policy_json : data.aws_iam_policy_document.assume_role[0].json
  permissions_boundary = var.permissions_boundary_arn
  max_session_duration = var.max_session_duration

  tags = merge(var.tags, { Name = var.name, Module = "iam" })
}

resource "aws_iam_role_policy" "inline" {
  for_each = var.inline_policies

  name   = each.key
  role   = aws_iam_role.this.id
  policy = each.value
}

resource "aws_iam_role_policy_attachment" "managed" {
  for_each = toset(var.managed_policy_arns)

  role       = aws_iam_role.this.name
  policy_arn = each.value
}

resource "aws_iam_instance_profile" "this" {
  count = var.create_instance_profile ? 1 : 0

  name = var.name
  role = aws_iam_role.this.name

  tags = merge(var.tags, { Name = var.name, Module = "iam" })
}
