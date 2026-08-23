mock_provider "aws" {}

mock_provider "aws" {
  alias = "dr"
}

mock_provider "aws" {
  alias = "ses"
}

mock_provider "random" {}

override_data {
  target = data.aws_iam_policy_document.backup_assume
  values = { json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}" }
}

override_data {
  target = data.aws_iam_policy_document.rds_monitoring_assume
  values = { json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}" }
}

override_data {
  target = data.aws_iam_policy_document.ecs_assume
  values = { json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}" }
}

override_data {
  target = data.aws_iam_policy_document.ecs_secrets
  values = { json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}" }
}

override_data {
  target = data.aws_iam_policy_document.ecs_task
  values = { json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}" }
}

override_data {
  target = data.aws_iam_policy_document.flow_assume
  values = { json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}" }
}

override_data {
  target = data.aws_iam_policy_document.flow
  values = { json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}" }
}

override_data {
  target = data.aws_iam_policy_document.recovery
  values = { json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}" }
}

override_data {
  target = data.aws_iam_policy_document.alb_logs
  values = { json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}" }
}

override_data {
  target = data.aws_iam_policy_document.alerts_topic
  values = { json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}" }
}

override_data {
  target = data.aws_iam_policy_document.ses_events
  values = { json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}" }
}

override_data {
  target = data.aws_iam_policy_document.ses_events_kms
  values = { json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}" }
}

override_data {
  target = data.aws_iam_policy_document.logs_kms
  values = { json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}" }
}

override_data {
  target = data.aws_iam_policy_document.alerts_kms
  values = { json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}" }
}

override_data {
  target = data.aws_caller_identity.ses
  values = { account_id = "123456789012" }
}

override_data {
  target = data.aws_caller_identity.current
  values = { account_id = "123456789012" }
}

override_data {
  target = data.aws_availability_zones.available
  values = {
    names = ["me-south-1a", "me-south-1b", "me-south-1c"]
  }
}

override_data {
  target = data.aws_elb_service_account.main
  values = {
    arn = "arn:aws:iam::127311923021:root"
  }
}

override_resource {
  target = aws_db_instance.main
  values = {
    address = "vip-production.mock.me-south-1.rds.amazonaws.com"
    arn     = "arn:aws:rds:me-south-1:123456789012:db:vip-production"
    master_user_secret = [{
      kms_key_id    = "mock-kms"
      secret_arn    = "arn:aws:secretsmanager:me-south-1:123456789012:secret:rds/mock"
      secret_status = "active"
    }]
  }
}

override_resource {
  target = aws_acm_certificate.main
  values = {
    domain_validation_options = [
      {
        domain_name           = "app.example.invalid"
        resource_record_name  = "_app.example.invalid"
        resource_record_type  = "CNAME"
        resource_record_value = "_app.acm-validations.aws"
      },
      {
        domain_name           = "api.example.invalid"
        resource_record_name  = "_api.example.invalid"
        resource_record_type  = "CNAME"
        resource_record_value = "_api.acm-validations.aws"
      },
    ]
  }
}

override_data {
  target = data.aws_secretsmanager_secret_version.rds_master
  values = {
    secret_string = "{\"username\":\"vip_admin\",\"password\":\"mock-only-password\"}"
  }
}

run "production_plan" {
  command = plan

  variables {
    environment     = "production"
    root_domain     = "example.invalid"
    hosted_zone_id  = "ZMOCK000000000000000"
    build_timestamp = "2026-08-16T00:00:00Z"
    api_image       = "123456789012.dkr.ecr.me-south-1.amazonaws.com/vip-api@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    web_image       = "123456789012.dkr.ecr.me-south-1.amazonaws.com/vip-web@sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    alert_email     = "platform-ops@example.invalid"
    smtp_host       = "email-smtp.eu-central-1.amazonaws.com"
    smtp_secret_arn = "arn:aws:secretsmanager:me-south-1:123456789012:secret:vip/production/smtp-mock"
  }

  assert {
    condition     = aws_db_instance.main.publicly_accessible == false
    error_message = "RDS must not be publicly accessible."
  }

  assert {
    condition     = aws_db_instance.main.storage_encrypted == true
    error_message = "RDS storage encryption must remain enabled."
  }

  assert {
    condition     = aws_db_instance.main.backup_retention_period == 35
    error_message = "Production RDS PITR retention must be 35 days."
  }

  assert {
    condition = one([
      for item in aws_elasticache_parameter_group.main.parameter :
      item.value if item.name == "maxmemory-policy"
    ]) == "noeviction"
    error_message = "Redis must retain noeviction for queues/security state."
  }

  assert {
    condition     = aws_ecs_service.api.network_configuration[0].assign_public_ip == false
    error_message = "API tasks must not receive public IPs."
  }

  assert {
    condition     = aws_ecs_service.scheduler.desired_count == 1
    error_message = "The logical scheduler must be a singleton."
  }

  assert {
    condition     = aws_efs_file_system.artifacts.encrypted == true
    error_message = "Artifact storage must be encrypted."
  }

  assert {
    condition     = aws_ecr_repository.api.image_tag_mutability == "IMMUTABLE" && aws_ecr_repository.web.image_tag_mutability == "IMMUTABLE"
    error_message = "Release repositories must reject mutable tags."
  }

  assert {
    condition     = aws_lb_listener.https.ssl_policy == "ELBSecurityPolicy-TLS13-1-2-2021-06"
    error_message = "The ALB must enforce TLS 1.2 or newer."
  }
}
