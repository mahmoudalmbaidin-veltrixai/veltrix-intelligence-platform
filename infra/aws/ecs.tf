data "aws_iam_policy_document" "ecs_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ecs_execution" {
  name               = "${local.name}-ecs-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json
}

resource "aws_iam_role_policy_attachment" "ecs_execution" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

data "aws_iam_policy_document" "ecs_secrets" {
  statement {
    actions = ["secretsmanager:GetSecretValue"]
    resources = [
      aws_secretsmanager_secret.runtime.arn,
      var.smtp_secret_arn,
    ]
  }

  statement {
    actions   = ["kms:Decrypt"]
    resources = [aws_kms_key.main.arn]
  }
}

resource "aws_iam_role_policy" "ecs_secrets" {
  role   = aws_iam_role.ecs_execution.id
  policy = data.aws_iam_policy_document.ecs_secrets.json
}

resource "aws_iam_role" "ecs_task" {
  name               = "${local.name}-ecs-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json
}

resource "aws_iam_role" "ecs_task_minimal" {
  name               = "${local.name}-ecs-task-minimal"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json
}

data "aws_iam_policy_document" "ecs_task" {
  statement {
    actions = [
      "elasticfilesystem:ClientMount",
      "elasticfilesystem:ClientWrite",
    ]
    resources = [aws_efs_file_system.artifacts.arn]
    condition {
      test     = "StringEquals"
      variable = "elasticfilesystem:AccessPointArn"
      values   = [aws_efs_access_point.artifacts.arn]
    }
  }
}

resource "aws_iam_role_policy" "ecs_task" {
  role   = aws_iam_role.ecs_task.id
  policy = data.aws_iam_policy_document.ecs_task.json
}

resource "aws_ecs_cluster" "main" {
  name = local.name

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_ecs_cluster_capacity_providers" "main" {
  cluster_name       = aws_ecs_cluster.main.name
  capacity_providers = ["FARGATE"]

  default_capacity_provider_strategy {
    capacity_provider = "FARGATE"
    weight            = 1
  }
}

locals {
  log_groups = toset(["api", "web", "dashboard-worker", "pipeline-worker", "scheduler", "migration", "clamav"])

  common_environment = [
    { name = "APP_ENV", value = var.environment },
    { name = "APP_VERSION", value = var.application_version },
    { name = "BUILD_COMMIT_SHA", value = var.release_sha },
    { name = "BUILD_TIMESTAMP", value = var.build_timestamp },
    { name = "DEBUG", value = "false" },
    { name = "ENABLE_DOCS", value = "false" },
    { name = "LOG_LEVEL", value = "INFO" },
    { name = "CORS_ALLOWED_ORIGINS", value = "https://${local.app_hostname}" },
    { name = "CORS_ALLOW_CREDENTIALS", value = "true" },
    { name = "CSRF_TRUSTED_ORIGINS", value = "https://${local.app_hostname}" },
    { name = "TRUSTED_HOSTS", value = local.api_hostname },
    { name = "FRONTEND_URL", value = "https://${local.app_hostname}" },
    { name = "INVITATION_ACCEPT_URL", value = "https://${local.app_hostname}/invitations/accept" },
    { name = "AUTH_COOKIE_SECURE", value = "true" },
    { name = "AUTH_COOKIE_SAMESITE", value = "lax" },
    { name = "AUTH_COOKIE_DOMAIN", value = ".${var.root_domain}" },
    { name = "AUTH_LOGIN_RATE_LIMIT_PER_MINUTE", value = "10" },
    { name = "PASSWORD_RESET_RATE_LIMIT_PER_MINUTE", value = "5" },
    { name = "GOVERNANCE_FAIL_CLOSED", value = "true" },
    { name = "AUDIT_EVENTS_ENABLED", value = "true" },
    { name = "AUDIT_DENIED_ACCESS", value = "true" },
    { name = "AUDIT_RETENTION_DAYS", value = tostring(var.audit_retention_days) },
    { name = "AI_CAPABILITIES_PRODUCTION_READY", value = "false" },
    { name = "AI_DEVELOPMENT_MOCK_MODE", value = "false" },
    { name = "CONNECTION_SECRET_PROVIDER", value = "database_encrypted" },
    { name = "CONNECTION_ENCRYPTION_KEY_VERSION", value = "prod-v1" },
    { name = "CONNECTION_ALLOW_PRIVATE_NETWORKS", value = "false" },
    { name = "CONNECTION_ALLOW_HTTP", value = "false" },
    { name = "CONNECTION_BLOCK_CLOUD_METADATA", value = "true" },
    { name = "DATABASE_POOL_SIZE", value = "5" },
    { name = "DATABASE_MAX_OVERFLOW", value = "5" },
    { name = "DATABASE_POOL_TIMEOUT", value = "30" },
    { name = "DATABASE_CONNECT_TIMEOUT", value = "5" },
    { name = "REDIS_SOCKET_TIMEOUT", value = "5" },
    { name = "METRICS_ENABLED", value = "true" },
    { name = "DASHBOARD_ARTIFACT_ROOT", value = "/data/vip-artifacts" },
    { name = "PIPELINE_ARTIFACT_ROOT", value = "/data/vip-pipeline-artifacts" },
    { name = "FILE_STORAGE_PROVIDER", value = "local" },
    { name = "FILE_STORAGE_ROOT", value = "/data/vip-files" },
    { name = "FILE_MAX_UPLOAD_BYTES", value = "104857600" },
    { name = "FILE_MALWARE_SCANNER", value = "clamav" },
    { name = "CLAMAV_HOST", value = "127.0.0.1" },
    { name = "CLAMAV_PORT", value = "3310" },
    { name = "DASHBOARD_EMAIL_PROVIDER", value = "smtp" },
    { name = "DASHBOARD_EMAIL_FROM", value = "no-reply@${local.mail_domain}" },
    { name = "DASHBOARD_SMTP_HOST", value = var.smtp_host },
    { name = "DASHBOARD_SMTP_PORT", value = tostring(var.smtp_port) },
    { name = "DASHBOARD_SMTP_STARTTLS", value = "true" },
    { name = "DASHBOARD_SMTP_USE_TLS", value = "false" },
  ]

  scheduler_disabled_environment = [
    { name = "DASHBOARD_DELIVERY_SCHEDULER_ENABLED", value = "false" },
    { name = "PIPELINE_SCHEDULER_ENABLED", value = "false" },
  ]

  runtime_secret_keys = toset([
    "DATABASE_URL",
    "REDIS_URL",
    "CONNECTION_ENCRYPTION_KEY",
    "DASHBOARD_DOWNLOAD_SIGNING_KEY",
    "PIPELINE_DOWNLOAD_SIGNING_KEY",
    "FILE_DOWNLOAD_SIGNING_KEY",
    "METRICS_BEARER_TOKEN",
  ])

  common_secrets = concat(
    [for key in local.runtime_secret_keys : {
      name      = key
      valueFrom = "${aws_secretsmanager_secret.runtime.arn}:${key}::"
    }],
    [
      { name = "DASHBOARD_SMTP_USERNAME", valueFrom = "${var.smtp_secret_arn}:DASHBOARD_SMTP_USERNAME::" },
      { name = "DASHBOARD_SMTP_PASSWORD", valueFrom = "${var.smtp_secret_arn}:DASHBOARD_SMTP_PASSWORD::" },
    ]
  )

  efs_volume = {
    name = "artifacts"
    efsVolumeConfiguration = {
      fileSystemId      = aws_efs_file_system.artifacts.id
      transitEncryption = "ENABLED"
      authorizationConfig = {
        accessPointId = aws_efs_access_point.artifacts.id
        iam           = "ENABLED"
      }
    }
  }

  mount_points = [{
    sourceVolume  = "artifacts"
    containerPath = "/data"
    readOnly      = false
  }]

  awslogs = {
    logDriver = "awslogs"
    options = {
      awslogs-region        = var.aws_region
      awslogs-stream-prefix = "ecs"
    }
  }
}

resource "aws_cloudwatch_log_group" "service" {
  for_each = local.log_groups

  name              = "/vip/${var.environment}/${each.key}"
  retention_in_days = var.log_retention_days
  kms_key_id        = aws_kms_key.logs.arn
}

resource "aws_ecs_task_definition" "api" {
  family                   = "${local.name}-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 2048
  memory                   = 4096
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn
  track_latest             = true

  volume {
    name = local.efs_volume.name
    efs_volume_configuration {
      file_system_id     = aws_efs_file_system.artifacts.id
      transit_encryption = "ENABLED"
      authorization_config {
        access_point_id = aws_efs_access_point.artifacts.id
        iam             = "ENABLED"
      }
    }
  }

  container_definitions = jsonencode([
    {
      name         = "api"
      image        = var.api_image
      essential    = true
      cpu          = 1024
      memory       = 2048
      stopTimeout  = 60
      portMappings = [{ containerPort = 8000, hostPort = 8000, protocol = "tcp" }]
      environment = concat(local.common_environment, local.scheduler_disabled_environment, [
        { name = "SERVICE_NAME", value = "vip-api" },
        { name = "SKIP_PLATFORM_BOOTSTRAP", value = "true" },
      ])
      secrets     = local.common_secrets
      mountPoints = local.mount_points
      dependsOn   = [{ containerName = "clamav", condition = "HEALTHY" }]
      healthCheck = {
        command     = ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 30
      }
      logConfiguration = merge(local.awslogs, { options = merge(local.awslogs.options, { awslogs-group = aws_cloudwatch_log_group.service["api"].name }) })
    },
    {
      name      = "clamav"
      image     = "clamav/clamav:stable@sha256:7f5389ccaa2368c383fa80e167ccfe44348d71e685f926fce4755eed1757673a"
      essential = true
      cpu       = 1024
      memory    = 2048
      healthCheck = {
        command     = ["CMD-SHELL", "echo PING | nc 127.0.0.1 3310 | grep -q PONG"]
        interval    = 30
        timeout     = 10
        retries     = 5
        startPeriod = 120
      }
      logConfiguration = merge(local.awslogs, { options = merge(local.awslogs.options, { awslogs-group = aws_cloudwatch_log_group.service["clamav"].name }) })
    }
  ])
}

resource "aws_ecs_task_definition" "web" {
  family                   = "${local.name}-web"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task_minimal.arn
  track_latest             = true

  container_definitions = jsonencode([{
    name         = "web"
    image        = var.web_image
    essential    = true
    portMappings = [{ containerPort = 8080, hostPort = 8080, protocol = "tcp" }]
    healthCheck = {
      command     = ["CMD-SHELL", "wget -q -O /dev/null http://127.0.0.1:8080/healthz || exit 1"]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 10
    }
    logConfiguration = merge(local.awslogs, { options = merge(local.awslogs.options, { awslogs-group = aws_cloudwatch_log_group.service["web"].name }) })
  }])
}

resource "aws_ecs_task_definition" "dashboard_worker" {
  family                   = "${local.name}-dashboard-worker"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 1024
  memory                   = 2048
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn
  track_latest             = true

  volume {
    name = "artifacts"
    efs_volume_configuration {
      file_system_id     = aws_efs_file_system.artifacts.id
      transit_encryption = "ENABLED"
      authorization_config {
        access_point_id = aws_efs_access_point.artifacts.id
        iam             = "ENABLED"
      }
    }
  }

  container_definitions = jsonencode([{
    name        = "dashboard-worker"
    image       = var.api_image
    essential   = true
    command     = ["python", "-m", "vip_api.jobs.worker"]
    stopTimeout = 120
    environment = concat(local.common_environment, local.scheduler_disabled_environment, [
      { name = "SERVICE_NAME", value = "vip-dashboard-worker" },
      { name = "SKIP_PLATFORM_BOOTSTRAP", value = "true" },
      { name = "JOB_WORKER_QUEUES", value = "default,dashboard" },
      { name = "JOB_WORKER_CONCURRENCY", value = "4" },
    ])
    secrets     = local.common_secrets
    mountPoints = local.mount_points
    healthCheck = {
      command     = ["CMD", "python", "/app/scripts/worker-health.py"]
      interval    = 30
      timeout     = 10
      retries     = 3
      startPeriod = 30
    }
    logConfiguration = merge(local.awslogs, { options = merge(local.awslogs.options, { awslogs-group = aws_cloudwatch_log_group.service["dashboard-worker"].name }) })
  }])
}

resource "aws_ecs_task_definition" "pipeline_worker" {
  family                   = "${local.name}-pipeline-worker"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 2048
  memory                   = 4096
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn
  track_latest             = true

  volume {
    name = "artifacts"
    efs_volume_configuration {
      file_system_id     = aws_efs_file_system.artifacts.id
      transit_encryption = "ENABLED"
      authorization_config {
        access_point_id = aws_efs_access_point.artifacts.id
        iam             = "ENABLED"
      }
    }
  }

  container_definitions = jsonencode([{
    name        = "pipeline-worker"
    image       = var.api_image
    essential   = true
    command     = ["python", "-m", "vip_api.pipelines.worker"]
    stopTimeout = 120
    environment = concat(local.common_environment, local.scheduler_disabled_environment, [
      { name = "SERVICE_NAME", value = "vip-pipeline-worker" },
      { name = "SKIP_PLATFORM_BOOTSTRAP", value = "true" },
    ])
    secrets     = local.common_secrets
    mountPoints = local.mount_points
    healthCheck = {
      command     = ["CMD", "python", "/app/scripts/worker-health.py"]
      interval    = 30
      timeout     = 10
      retries     = 3
      startPeriod = 30
    }
    logConfiguration = merge(local.awslogs, { options = merge(local.awslogs.options, { awslogs-group = aws_cloudwatch_log_group.service["pipeline-worker"].name }) })
  }])
}

resource "aws_ecs_task_definition" "scheduler" {
  family                   = "${local.name}-scheduler"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 512
  memory                   = 1024
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task_minimal.arn
  track_latest             = true

  container_definitions = jsonencode([{
    name        = "scheduler"
    image       = var.api_image
    essential   = true
    command     = ["python", "-m", "vip_api.jobs.worker"]
    stopTimeout = 60
    environment = concat(local.common_environment, [
      { name = "SERVICE_NAME", value = "vip-scheduler" },
      { name = "SKIP_PLATFORM_BOOTSTRAP", value = "true" },
      { name = "JOB_WORKER_QUEUES", value = "scheduler" },
      { name = "JOB_WORKER_CONCURRENCY", value = "1" },
      { name = "DASHBOARD_DELIVERY_SCHEDULER_ENABLED", value = "true" },
      { name = "PIPELINE_SCHEDULER_ENABLED", value = "true" },
    ])
    secrets = local.common_secrets
    healthCheck = {
      command     = ["CMD", "python", "/app/scripts/worker-health.py"]
      interval    = 30
      timeout     = 10
      retries     = 3
      startPeriod = 30
    }
    logConfiguration = merge(local.awslogs, { options = merge(local.awslogs.options, { awslogs-group = aws_cloudwatch_log_group.service["scheduler"].name }) })
  }])
}

resource "aws_ecs_task_definition" "migration" {
  family                   = "${local.name}-migration"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 512
  memory                   = 1024
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task_minimal.arn
  track_latest             = true

  container_definitions = jsonencode([{
    name      = "migration"
    image     = var.api_image
    essential = true
    command = [
      "/bin/sh", "-ceu",
      "alembic upgrade head && alembic current | grep -q '^20260808_0025 ' && python -m vip_api.cli seed-governance && python -m vip_api.cli seed-connection-types",
    ]
    environment = concat(local.common_environment, [
      { name = "SERVICE_NAME", value = "vip-migration" },
      { name = "SKIP_PLATFORM_BOOTSTRAP", value = "true" },
    ])
    secrets          = local.common_secrets
    logConfiguration = merge(local.awslogs, { options = merge(local.awslogs.options, { awslogs-group = aws_cloudwatch_log_group.service["migration"].name }) })
  }])
}

resource "aws_ecs_service" "api" {
  name                               = "api"
  cluster                            = aws_ecs_cluster.main.id
  task_definition                    = aws_ecs_task_definition.api.arn
  desired_count                      = var.api_desired_count
  launch_type                        = "FARGATE"
  platform_version                   = "LATEST"
  health_check_grace_period_seconds  = 180
  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200
  enable_execute_command             = false

  network_configuration {
    subnets = aws_subnet.application[*].id
    security_groups = [
      aws_security_group.ecs.id,
      aws_security_group.connector_egress.id,
      aws_security_group.smtp_egress.id,
    ]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = 8000
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  depends_on = [aws_lb_listener_rule.api]
  lifecycle { ignore_changes = [task_definition] }
}

resource "aws_ecs_service" "web" {
  name                               = "web"
  cluster                            = aws_ecs_cluster.main.id
  task_definition                    = aws_ecs_task_definition.web.arn
  desired_count                      = var.web_desired_count
  launch_type                        = "FARGATE"
  platform_version                   = "LATEST"
  health_check_grace_period_seconds  = 60
  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200
  enable_execute_command             = false

  network_configuration {
    subnets          = aws_subnet.application[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.web.arn
    container_name   = "web"
    container_port   = 8080
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  depends_on = [aws_lb_listener_rule.web]
  lifecycle { ignore_changes = [task_definition] }
}

resource "aws_ecs_service" "dashboard_worker" {
  name                               = "dashboard-worker"
  cluster                            = aws_ecs_cluster.main.id
  task_definition                    = aws_ecs_task_definition.dashboard_worker.arn
  desired_count                      = var.dashboard_worker_desired_count
  launch_type                        = "FARGATE"
  platform_version                   = "LATEST"
  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200
  enable_execute_command             = false

  network_configuration {
    subnets = aws_subnet.application[*].id
    security_groups = [
      aws_security_group.ecs.id,
      aws_security_group.connector_egress.id,
      aws_security_group.smtp_egress.id,
    ]
    assign_public_ip = false
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
  lifecycle { ignore_changes = [task_definition] }
}

resource "aws_ecs_service" "pipeline_worker" {
  name                               = "pipeline-worker"
  cluster                            = aws_ecs_cluster.main.id
  task_definition                    = aws_ecs_task_definition.pipeline_worker.arn
  desired_count                      = var.pipeline_worker_desired_count
  launch_type                        = "FARGATE"
  platform_version                   = "LATEST"
  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200
  enable_execute_command             = false

  network_configuration {
    subnets = aws_subnet.application[*].id
    security_groups = [
      aws_security_group.ecs.id,
      aws_security_group.connector_egress.id,
    ]
    assign_public_ip = false
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
  lifecycle { ignore_changes = [task_definition] }
}

resource "aws_ecs_service" "scheduler" {
  name                               = "scheduler"
  cluster                            = aws_ecs_cluster.main.id
  task_definition                    = aws_ecs_task_definition.scheduler.arn
  desired_count                      = 1
  launch_type                        = "FARGATE"
  platform_version                   = "LATEST"
  deployment_minimum_healthy_percent = 0
  deployment_maximum_percent         = 100
  enable_execute_command             = false

  network_configuration {
    subnets          = aws_subnet.application[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
  lifecycle { ignore_changes = [task_definition, desired_count] }
}

resource "aws_appautoscaling_target" "api" {
  max_capacity       = 8
  min_capacity       = 2
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.api.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "api_cpu" {
  name               = "${local.name}-api-cpu"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.api.resource_id
  scalable_dimension = aws_appautoscaling_target.api.scalable_dimension
  service_namespace  = aws_appautoscaling_target.api.service_namespace

  target_tracking_scaling_policy_configuration {
    target_value       = 60
    scale_in_cooldown  = 300
    scale_out_cooldown = 60
    predefined_metric_specification { predefined_metric_type = "ECSServiceAverageCPUUtilization" }
  }
}
