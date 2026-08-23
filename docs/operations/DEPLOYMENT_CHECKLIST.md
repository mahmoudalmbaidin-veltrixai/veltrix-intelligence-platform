# VIP V1 Production Deployment Checklist

> Superseded for the final VIP V1 handoff by `VIP_V1_DEPLOYMENT_CHECKLIST.md`; retained as supporting audit history.

Every item requires a link to evidence, an owner, and a timestamp. An unchecked P0/P1 control means NO-GO.

## Governance and release

- [ ] Customer data classification and Bahrain/GCC residency approved in writing
- [ ] Certified SHA is `4e97591845a93037d6e54b0237bcb3208d1b2696`
- [ ] Application-tree diff from certified SHA is empty
- [ ] Alembic code head is `20260808_0025`
- [ ] Infrastructure changes reviewed and Terraform plan approved
- [ ] GitHub staging/production environments, OIDC roles, reviewers, and concurrency configured
- [ ] Change, rollback, incident, and on-call owners assigned

## Environment separation

- [ ] Separate AWS accounts or strongly separated roles/stacks for staging and production
- [ ] Separate VPC, RDS, Redis, KMS, Secrets Manager, EFS, S3, SMTP configuration, and domains
- [ ] Production database is new/empty except intentional baseline seeds
- [ ] No QA organizations, users, passwords, artifacts, or test connectors present

## Edge and network

- [ ] Route 53 app/API records resolve to the intended ALB
- [ ] ACM certificate valid for both exact names and renewal monitoring enabled
- [ ] HTTP redirects to HTTPS; TLS 1.2/1.3 only
- [ ] WAF associated, managed groups enabled, rate rules sampled/tested
- [ ] Upload flow passes through WAF without body-size false positives
- [ ] ALB rejects unknown hosts and uses `/ready` for API targets
- [ ] PostgreSQL and Redis have no public address/ingress
- [ ] Security groups and VPC flow logs reviewed

## Runtime security

- [ ] All ECS image references are immutable ECR digests
- [ ] OCI revision label and `/api/v1/version` show certified SHA
- [ ] API/web run non-root; no dev server, debug, docs, mock, or deferred AI capability
- [ ] Secure/HttpOnly/SameSite cookies verified in browser
- [ ] Exact CORS/CSRF origins and trusted API host verified
- [ ] Production startup fails when each critical secret is deliberately omitted in staging
- [ ] ClamAV healthy; safe, EICAR, oversize, mismatched MIME, macro XLSX, and traversal tests recorded
- [ ] Secret scan, dependency scan, IaC scan, and API/web image scans have no open Critical/High blocker

## Data protection

- [ ] RDS PostgreSQL 17.10 is private, Multi-AZ, KMS encrypted, and forces TLS
- [ ] RDS storage auto-growth, connection alerts, maintenance and backup windows set
- [ ] PITR enabled for 35 days and latest recovery point visible
- [ ] Redis private, TLS/AUTH/KMS, Multi-AZ, `noeviction`, snapshots and alarms verified
- [ ] EFS encrypted, private, access-point permissions UID 100/GID 101, backup selected
- [ ] S3 buckets block public access, enforce TLS, encryption, versioning/lifecycle as applicable
- [ ] Primary and cross-region backup vault recovery points exist
- [ ] Completed staging DB restore drill evidence approved
- [ ] Completed EFS/artifact restore drill evidence approved

## Services

- [ ] Web service has 2 healthy tasks and SPA route refresh works
- [ ] API has 2 healthy tasks; `/health`, `/ready`, version and headers pass
- [ ] Dashboard worker heartbeat healthy; export and email pass
- [ ] Pipeline worker heartbeat healthy; pipeline run/artifact pass
- [ ] Exactly one scheduler task is running; schedule restart and duplicate-fire tests pass
- [ ] Migration task is not a long-running service and concurrent deployment is prevented
- [ ] Worker/API/scheduler restart and database/Redis transient-failure tests pass in staging

## Email

- [ ] SES/transactional provider production access approved
- [ ] Cross-region email-content processing location approved (SES SMTP is unavailable in Bahrain/UAE)
- [ ] Sender identity, DKIM, custom MAIL FROM SPF, and DMARC validate publicly
- [ ] SMTP credentials exist only in Secrets Manager and have an owner/rotation date
- [ ] Tagged scheduled-delivery test accepted and received
- [ ] Bounce/complaint/failure visibility and alarms tested

## Observability and operations

- [ ] CloudWatch log groups receive structured JSON from every service
- [ ] ALB access logs and VPC flow logs arrive and retention is correct
- [ ] No secrets/cookies/full sensitive payloads appear in sampled logs
- [ ] API availability, 5xx, p95 latency, CPU/memory, DB, Redis, worker and scheduler alarms tested
- [ ] SNS subscription confirmed by on-call mailbox and a test alarm received
- [ ] Uptime checks pass for app and API
- [ ] Queue/export/pipeline/scheduler failure dashboard or protected metric collection available
- [ ] Error triage has correlation/request IDs and stack traces are not customer-visible

## Staging smoke

- [ ] Login
- [ ] Organization/workspace
- [ ] Connection
- [ ] CSV upload and dataset
- [ ] XLSX upload and dataset
- [ ] Pipeline execution and artifact
- [ ] Dashboard create/publish/viewer
- [ ] PDF export
- [ ] PNG export
- [ ] Schedule executes once in configured timezone
- [ ] Email delivery
- [ ] Notification preference persistence
- [ ] Audit events retain correct tenant/timestamps

## Final change window

- [ ] Pre-deploy RDS snapshot available
- [ ] Migration task exit 0 and current head `20260808_0025`
- [ ] ECS services stable and prior task definitions recorded
- [ ] Infrastructure smoke PASS and authenticated production-safe smoke PASS
- [ ] Deployment manifest retained
- [ ] 24-hour enhanced observation owner assigned
- [ ] P0 infrastructure defects = 0
- [ ] P1 infrastructure defects = 0
- [ ] Final GO approved by Platform, Security, Product, and Operations owners
