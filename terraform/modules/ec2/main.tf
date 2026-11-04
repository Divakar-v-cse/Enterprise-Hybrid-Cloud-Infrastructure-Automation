data "aws_ami" "linux" {
  count = length([for i in values(var.instances) : i if i.os == "linux" && i.ami_id == null]) > 0 ? 1 : 0

  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = [var.linux_ami_pattern]
  }

  filter {
    name   = "architecture"
    values = ["x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

data "aws_ami" "windows" {
  count = length([for i in values(var.instances) : i if i.os == "windows" && i.ami_id == null]) > 0 ? 1 : 0

  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = [var.windows_ami_pattern]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

locals {
  resolved_ami = {
    for key, instance in var.instances :
    key => (
      instance.ami_id != null
      ? instance.ami_id
      : (instance.os == "windows" ? data.aws_ami.windows[0].id : data.aws_ami.linux[0].id)
    )
  }
}

resource "aws_instance" "this" {
  for_each = var.instances

  ami                         = local.resolved_ami[each.key]
  instance_type               = each.value.instance_type
  subnet_id                   = each.value.subnet_id
  vpc_security_group_ids      = var.security_group_ids
  iam_instance_profile        = var.iam_instance_profile_name
  key_name                    = var.key_name
  associate_public_ip_address = each.value.associate_public_ip_address
  user_data                   = each.value.user_data
  monitoring                  = var.enable_detailed_monitoring

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required" # IMDSv2 only
    http_put_response_hop_limit = 1
    instance_metadata_tags      = "enabled"
  }

  root_block_device {
    volume_type           = "gp3"
    volume_size           = each.value.root_volume_size
    encrypted             = true
    kms_key_id            = var.kms_key_arn
    delete_on_termination = true
  }

  tags = merge(
    var.tags,
    {
      Name       = "${var.name}-${each.key}"
      OS         = each.value.os == "windows" ? "Windows Server 2022" : "Linux"
      PatchGroup = each.value.patch_group
      Role       = each.value.role
      Module     = "ec2"
    }
  )

  lifecycle {
    # AMIs are rolled forward through the pipeline, never patched in place.
    ignore_changes = [ami]
  }
}

resource "aws_cloudwatch_metric_alarm" "status_check" {
  for_each = var.enable_status_alarms ? var.instances : {}

  alarm_name          = "${var.name}-${each.key}-status-check"
  alarm_description   = "Instance ${each.key} failed its EC2 status check"
  namespace           = "AWS/EC2"
  metric_name         = "StatusCheckFailed"
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 2
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    InstanceId = aws_instance.this[each.key].id
  }

  alarm_actions = var.alarm_sns_topic_arn != null ? [var.alarm_sns_topic_arn] : []

  tags = merge(var.tags, { Name = "${var.name}-${each.key}-status-check" })
}
