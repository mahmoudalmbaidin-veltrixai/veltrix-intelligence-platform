resource "random_password" "connection_encryption" {
  length  = 43
  special = false
}

resource "random_password" "dashboard_signing" {
  length  = 64
  special = false
}

resource "random_password" "pipeline_signing" {
  length  = 64
  special = false
}

resource "random_password" "file_signing" {
  length  = 64
  special = false
}

resource "random_password" "metrics_token" {
  length  = 64
  special = false
}

resource "aws_secretsmanager_secret" "runtime" {
  name                    = "/${var.project}/${var.environment}/runtime"
  kms_key_id              = aws_kms_key.main.arn
  recovery_window_in_days = local.is_production ? 30 : 7
}

locals {
  rds_master = jsondecode(data.aws_secretsmanager_secret_version.rds_master.secret_string)
  # urlsafe base64 of exactly 32 bytes. The padding is required by the certified
  # application's AES-256-GCM key loader.
  connection_encryption_key = "${substr(random_password.connection_encryption.result, 0, 43)}="
}

resource "aws_secretsmanager_secret_version" "runtime" {
  secret_id = aws_secretsmanager_secret.runtime.id
  secret_string = jsonencode({
    DATABASE_URL                   = "postgresql+asyncpg://${local.rds_master.username}:${urlencode(local.rds_master.password)}@${aws_db_instance.main.address}:5432/vip?ssl=require"
    REDIS_URL                      = "rediss://:${random_password.redis_auth.result}@${aws_elasticache_replication_group.main.primary_endpoint_address}:6379/0"
    CONNECTION_ENCRYPTION_KEY      = local.connection_encryption_key
    DASHBOARD_DOWNLOAD_SIGNING_KEY = random_password.dashboard_signing.result
    PIPELINE_DOWNLOAD_SIGNING_KEY  = random_password.pipeline_signing.result
    FILE_DOWNLOAD_SIGNING_KEY      = random_password.file_signing.result
    METRICS_BEARER_TOKEN           = random_password.metrics_token.result
  })
}
