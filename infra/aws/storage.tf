resource "aws_efs_file_system" "artifacts" {
  encrypted        = true
  kms_key_id       = aws_kms_key.main.arn
  performance_mode = "generalPurpose"
  throughput_mode  = "elastic"

  lifecycle_policy {
    transition_to_ia = "AFTER_30_DAYS"
  }

  lifecycle_policy {
    transition_to_primary_storage_class = "AFTER_1_ACCESS"
  }

  protection {
    replication_overwrite = "ENABLED"
  }

  tags = { Name = "${local.name}-artifacts" }
}

resource "aws_efs_mount_target" "artifacts" {
  count = local.az_count

  file_system_id  = aws_efs_file_system.artifacts.id
  subnet_id       = aws_subnet.data[count.index].id
  security_groups = [aws_security_group.efs.id]
}

resource "aws_efs_access_point" "artifacts" {
  file_system_id = aws_efs_file_system.artifacts.id

  posix_user {
    uid = 100
    gid = 101
  }

  root_directory {
    path = "/${var.environment}"
    creation_info {
      owner_uid   = 100
      owner_gid   = 101
      permissions = "0750"
    }
  }

  tags = { Name = "${local.name}-artifacts" }
}

resource "aws_s3_bucket" "recovery" {
  bucket_prefix = "${local.name}-recovery-"
  force_destroy = false
}

resource "aws_s3_bucket_public_access_block" "recovery" {
  bucket = aws_s3_bucket.recovery.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "recovery" {
  bucket = aws_s3_bucket.recovery.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.main.arn
      sse_algorithm     = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_versioning" "recovery" {
  bucket = aws_s3_bucket.recovery.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_lifecycle_configuration" "recovery" {
  bucket = aws_s3_bucket.recovery.id

  rule {
    id     = "recovery-retention"
    status = "Enabled"

    filter {}

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 90
      storage_class = "GLACIER"
    }

    expiration { days = 365 }
    noncurrent_version_expiration { noncurrent_days = 90 }
  }
}

data "aws_iam_policy_document" "recovery" {
  statement {
    sid     = "DenyInsecureTransport"
    effect  = "Deny"
    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.recovery.arn,
      "${aws_s3_bucket.recovery.arn}/*",
    ]

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "recovery" {
  bucket = aws_s3_bucket.recovery.id
  policy = data.aws_iam_policy_document.recovery.json
}
