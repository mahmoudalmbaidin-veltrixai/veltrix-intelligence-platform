# Production deployment

This is a hosting-agnostic contract. It does not certify a live environment.

## Required services

- OCI-compatible container runtime;
- static frontend container and API container;
- PostgreSQL and Redis on private networks;
- generic/dashboard worker, pipeline worker, and one logical scheduler role;
- shared persistent filesystem for uploads, dashboard exports, pipeline artifacts, and file email only when used outside production;
- TLS termination, DNS, reverse proxy/load balancer, secret manager, backups, logs, metrics, and alerting;
- a malware scanner and SMTP provider for production operation.

Optional edge services include a CDN, WAF, DDoS protection, centralized SIEM, and external uptime monitoring.

## Release sequence

1. Select an immutable Git SHA that passed the repository security, frontend, backend, browser, migration, container, and infrastructure gates.
2. Build API and web images from that SHA; tag and promote by digest.
3. Provision configuration and secrets outside the images.
4. Back up the database and verify the recovery point.
5. Run exactly one migration task: `alembic upgrade head`, then verify `alembic current` equals `alembic heads`.
6. Deploy workers and the singleton scheduler with the new API image.
7. Deploy API replicas and wait for `/ready`.
8. Deploy the web image with the final public API URL.
9. Run unauthenticated health checks and authenticated tenant-scoped smoke tests.
10. Record image digests, release SHA, migration head, configuration version, test evidence, and rollback references.

Do not run migrations independently in every API replica. Do not seed demo users or demo data in production.

## Production configuration

Set `APP_ENV=production`, secure cookies, explicit trusted hosts/CORS/CSRF origins, HTTPS frontend/invitation URLs, unique encryption/signing keys, protected metrics, managed PostgreSQL/Redis URLs, SMTP delivery, and a non-noop malware scanner. Mount the same persistent roots in API and relevant workers.

## Rollback

Application containers can roll back to previous digests if the database schema remains compatible. Database rollback defaults to forward-fix. Restore a pre-deployment backup to a new database when a data-safe downgrade is not explicitly reviewed and rehearsed.

## AWS implementation

`infra/aws/` maps this contract to ECS, RDS, ElastiCache, EFS, ALB/ACM, WAF, Secrets Manager, CloudWatch, AWS Backup, and SES-related configuration. Validate, plan, review cost/security/data-residency implications, and test in staging before apply. See `infra/aws/README.md`.
