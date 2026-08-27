# AWS Terraform implementation

This directory maps the VIP deployment contract to AWS. It defines networking, private ECS tasks/services, RDS PostgreSQL, ElastiCache Redis, EFS-backed application storage, ECR, an ALB with ACM, WAF, Secrets Manager integration, monitoring/logging, backups, and email-related configuration.

## Prerequisites

- Terraform 1.13.2 as used in CI;
- an approved AWS account/region strategy and remote state backend;
- AWS credentials supplied through an approved operator or CI identity, never committed files;
- reviewed DNS, certificate, email, data-residency, backup, cost, and access decisions;
- immutable API/web image digests.

## Validate

```bash
terraform fmt -check -recursive
terraform init -backend=false
terraform validate
terraform test
```

Run these commands from `infra/aws` (or use `terraform -chdir=infra/aws ...` from the repository root).

## Configure and plan

Copy `backend.hcl.example` and `terraform.tfvars.example` to ignored local files, replace every placeholder, then initialize the approved remote backend. Keep state, plans, `.tfvars`, credentials, secret values, and customer-specific hostnames outside Git.

```bash
terraform init -backend-config=backend.hcl
terraform plan -out=deployment.tfplan
```

Review the plan for public exposure, IAM scope, encryption, backup retention, deletion protection, service counts, secret injection, data-region placement, and cost. This repository-preparation work does not authorize `terraform apply`.

## Deployment workflow

`.github/workflows/deploy-certified-release.yml` builds/scans immutable images, runs one migration task, promotes ECS services, and executes smoke checks. It requires GitHub environments, OIDC role variables, repository/environment configuration, provisioned infrastructure, and an approved certified SHA. Branch protection and environment approvals must not be bypassed.

## Scripts

- `scripts/deploy.sh`: migration-first service promotion with rollback tracking;
- `scripts/rollback.sh`: restore prior ECS task definitions;
- `scripts/smoke.sh`: infrastructure and application smoke checks.

Test in staging and complete a restore drill before any production use.
