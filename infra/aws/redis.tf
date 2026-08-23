resource "random_password" "redis_auth" {
  length  = 64
  special = false
}

resource "aws_elasticache_subnet_group" "main" {
  name       = local.name
  subnet_ids = aws_subnet.data[*].id
}

resource "aws_elasticache_parameter_group" "main" {
  name   = "${local.name}-redis7"
  family = "redis7"

  parameter {
    name  = "maxmemory-policy"
    value = "noeviction"
  }
}

resource "aws_elasticache_replication_group" "main" {
  replication_group_id = local.name
  description          = "VIP ${var.environment} queues, cache, locks, rate limits, and event streams"

  engine               = "redis"
  engine_version       = "7.1"
  node_type            = var.redis_node_type
  port                 = 6379
  parameter_group_name = aws_elasticache_parameter_group.main.name

  num_cache_clusters         = local.is_production ? 2 : 1
  automatic_failover_enabled = local.is_production
  multi_az_enabled           = local.is_production

  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  auth_token                 = random_password.redis_auth.result
  auth_token_update_strategy = "SET"
  kms_key_id                 = aws_kms_key.main.arn

  subnet_group_name  = aws_elasticache_subnet_group.main.name
  security_group_ids = [aws_security_group.redis.id]

  snapshot_retention_limit   = local.is_production ? 14 : 3
  snapshot_window            = "01:30-02:30"
  maintenance_window         = "sat:22:00-sat:23:00"
  auto_minor_version_upgrade = true
  apply_immediately          = false
}

