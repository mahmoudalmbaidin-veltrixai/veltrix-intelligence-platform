output "application_url" {
  value = "https://${local.app_hostname}"
}

output "api_url" {
  value = "https://${local.api_hostname}"
}

output "release_sha" {
  value = var.release_sha
}

output "alembic_head" {
  value = "20260808_0025"
}

output "ecr_api_repository" {
  value = aws_ecr_repository.api.repository_url
}

output "ecr_web_repository" {
  value = aws_ecr_repository.web.repository_url
}

output "ecs_cluster" {
  value = aws_ecs_cluster.main.name
}

output "private_subnet_ids" {
  value = aws_subnet.application[*].id
}

output "ecs_security_group_id" {
  value = aws_security_group.ecs.id
}

output "migration_task_family" {
  value = aws_ecs_task_definition.migration.family
}

output "runtime_secret_arn" {
  value     = aws_secretsmanager_secret.runtime.arn
  sensitive = true
}

output "rds_endpoint" {
  value = aws_db_instance.main.endpoint
}

output "redis_primary_endpoint" {
  value = aws_elasticache_replication_group.main.primary_endpoint_address
}

output "recovery_bucket" {
  value = aws_s3_bucket.recovery.id
}

output "backup_vault" {
  value = aws_backup_vault.primary.name
}

output "alert_topic_arn" {
  value = aws_sns_topic.alerts.arn
}
