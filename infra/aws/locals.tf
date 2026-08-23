locals {
  name = "${var.project}-${var.environment}"

  app_hostname = "${var.app_subdomain}${var.environment == "production" ? "" : ".${var.environment}"}.${var.root_domain}"
  api_hostname = "${var.api_subdomain}${var.environment == "production" ? "" : ".${var.environment}"}.${var.root_domain}"
  mail_domain  = "${var.email_subdomain}.${var.root_domain}"

  is_production = var.environment == "production"
  az_count      = 2
  nat_count     = local.is_production ? local.az_count : 1

  tags = {
    Application = "Veltrix Intelligence Platform"
    Environment = var.environment
    ManagedBy   = "Terraform"
    ReleaseSHA  = var.release_sha
    DataClass   = "Confidential"
  }
}
