variable "project" {
  description = "Short project identifier used in resource names."
  type        = string
  default     = "vip"
}

variable "environment" {
  description = "Deployment environment."
  type        = string

  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "environment must be staging or production."
  }
}

variable "aws_region" {
  description = "Primary AWS region. Bahrain is the default GCC deployment location."
  type        = string
  default     = "me-south-1"
}

variable "dr_region" {
  description = "Cross-region backup destination."
  type        = string
  default     = "me-central-1"
}

variable "ses_region" {
  description = "Region with an SES SMTP sending endpoint. SES SMTP is unavailable in Bahrain."
  type        = string
  default     = "eu-central-1"

  validation {
    condition     = var.ses_region != "me-south-1" && var.ses_region != "me-central-1"
    error_message = "SES SMTP sending endpoints are unavailable in Bahrain and UAE; select a supported approved region."
  }
}

variable "root_domain" {
  description = "Route 53 public hosted-zone domain, for example example.com."
  type        = string
}

variable "hosted_zone_id" {
  description = "Existing Route 53 public hosted zone ID."
  type        = string
}

variable "app_subdomain" {
  description = "Frontend label relative to root_domain."
  type        = string
  default     = "app"
}

variable "api_subdomain" {
  description = "API label relative to root_domain."
  type        = string
  default     = "api"
}

variable "release_sha" {
  description = "Immutable certified application revision."
  type        = string
  default     = "4e97591845a93037d6e54b0237bcb3208d1b2696"

  validation {
    condition     = var.release_sha == "4e97591845a93037d6e54b0237bcb3208d1b2696"
    error_message = "VIP V1 production is locked to certified SHA 4e97591845a93037d6e54b0237bcb3208d1b2696."
  }
}

variable "application_version" {
  description = "Human-readable application version returned by the version endpoint."
  type        = string
  default     = "1.0.0"
}

variable "build_timestamp" {
  description = "UTC RFC3339 image build timestamp supplied by the release pipeline."
  type        = string
}

variable "api_image" {
  description = "Immutable API ECR image reference, preferably repository@sha256:digest."
  type        = string
}

variable "web_image" {
  description = "Immutable web ECR image reference, preferably repository@sha256:digest."
  type        = string
}

variable "vpc_cidr" {
  description = "VPC IPv4 CIDR."
  type        = string
  default     = "10.42.0.0/16"
}

variable "api_desired_count" {
  type    = number
  default = 2
}

variable "web_desired_count" {
  type    = number
  default = 2
}

variable "dashboard_worker_desired_count" {
  type    = number
  default = 1
}

variable "pipeline_worker_desired_count" {
  type    = number
  default = 1
}

variable "db_instance_class" {
  type    = string
  default = "db.t4g.medium"
}

variable "db_allocated_storage_gib" {
  type    = number
  default = 100
}

variable "db_max_allocated_storage_gib" {
  type    = number
  default = 500
}

variable "redis_node_type" {
  type    = string
  default = "cache.t4g.small"
}

variable "alert_email" {
  description = "Operations mailbox that must confirm the SNS subscription."
  type        = string
}

variable "smtp_host" {
  description = "Transactional SMTP endpoint. For SES use email-smtp.<ses_region>.amazonaws.com."
  type        = string
}

variable "smtp_port" {
  type    = number
  default = 587
}

variable "smtp_secret_arn" {
  description = "Existing Secrets Manager secret containing DASHBOARD_SMTP_USERNAME and DASHBOARD_SMTP_PASSWORD JSON keys."
  type        = string
  sensitive   = true
}

variable "email_subdomain" {
  description = "Verified SES sender subdomain."
  type        = string
  default     = "mail"
}

variable "allowed_admin_cidrs" {
  description = "Optional CIDRs allowed to access the protected metrics endpoint through WAF."
  type        = list(string)
  default     = []
}

variable "log_retention_days" {
  type    = number
  default = 90
}

variable "audit_retention_days" {
  type    = number
  default = 365
}

variable "enable_deletion_protection" {
  description = "Protect stateful production resources. Keep true for production."
  type        = bool
  default     = true
}
