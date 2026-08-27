# Veltrix Intelligence Platform

Veltrix Intelligence Platform (VIP) is a multi-tenant data and analytics application for governed data connections, ingestion, transformation pipelines, semantic models, dashboards, exports, scheduled work, and operational oversight. This repository contains the Vue frontend, FastAPI backend, workers, database migrations, local Docker environment, automated tests, and an AWS infrastructure implementation.

## Overview

VIP provides one controlled workflow from source data to governed analytics. Organizations and workspaces isolate users and resources; role-based authorization is enforced by the API; PostgreSQL stores application and analytical metadata; Redis coordinates cache and job activity; and background workers execute pipelines, quality checks, exports, file lifecycle work, and schedule ticks.

The repository is the source of truth for application code and deployment definitions. Runtime databases, generated exports, uploaded files, credentials, local environment files, and operator workbooks are intentionally outside Git.

## Current V1 Capabilities

Verified V1 application surfaces include:

- multi-organization and workspace management;
- API-enforced tenant isolation, system/custom roles, resource access, feature flags, entitlements, quotas, and audit events;
- PostgreSQL connections with encrypted, write-only connection credentials;
- CSV and XLSX upload and ingestion;
- dataset catalog, preview, profiling, quality evaluation, versions, metadata discovery, and lineage;
- visual pipeline authoring, immutable versions, asynchronous execution, schedules, and protected artifacts;
- semantic models, dimensions, measures, metrics, glossary, validation, publishing, and bounded queries;
- dashboard authoring, versioning, publishing, viewer mode, filters, and supported visual widgets;
- asynchronous PDF, PNG, JSON, and CSV dashboard exports;
- recurring dashboard delivery and pipeline schedule ticks through the job worker;
- in-app job/file/export notifications and operational event streams;
- platform administration, session management, password recovery, secure files, health/readiness endpoints, and metrics.

Connector entries marked beta, planned, driver-required, or agent-required are not V1 general-availability claims.

## Product Status

Current release: **V1 productization and deployment preparation**.

The frontend and API package versions are `0.1.0`. Historical QA and productization reports are evidence for the exact revisions they name; they are not a substitute for testing the current checkout.

## Architecture

```text
Browser
  -> Vue 3 / TypeScript frontend
      -> FastAPI / Python API
          -> PostgreSQL
          -> Redis
          -> generic job worker (including schedule ticks)
          -> pipeline worker
          -> shared persistent filesystem
          -> SMTP provider when enabled
```

The development stack uses Docker Compose for PostgreSQL, Redis, ClamAV, the API, and workers. The production web image uses Nginx. The included AWS implementation maps the same contract to ECS, RDS PostgreSQL, ElastiCache Redis, EFS, an application load balancer, ACM, WAF, Secrets Manager, monitoring, and backups.

See [Architecture overview](docs/architecture/OVERVIEW.md) and [Deployment architecture](docs/architecture/DEPLOYMENT_ARCHITECTURE.md).

## Repository Structure

```text
veltrix-intelligence-platform/
├── src/                       # Vue application and shared frontend packages
├── public/                    # Static frontend assets
├── apps/api/                  # FastAPI app, workers, Alembic migrations, backend tests
├── infra/                     # Container definitions and AWS Terraform
├── scripts/                   # Demo and repository certification tooling
├── tests/e2e/                 # Playwright browser and accessibility suites
├── demo-data/                 # Synthetic, reproducible demo fixtures
├── resources/sample-data/     # Small public-safe ingestion samples
├── docs/                      # Architecture, deployment, operations, product, QA, and demo docs
├── .github/workflows/         # CI quality gate and controlled AWS deployment workflow
├── docker-compose.yml         # Development-only backend stack
├── Makefile                   # Common backend and certification commands
├── .env.example               # Root configuration contract and safe placeholders
└── README.md
```

The frontend remains at the repository root; this is intentional. The backend is an independent Python package under `apps/api`.

## Prerequisites

- Docker Engine with Docker Compose v2-compatible commands;
- Node.js 22 (the production web image uses 22.22.0) and npm with `package-lock.json`;
- Python 3.12 for native backend development (the package accepts Python `>=3.12,<3.15`);
- PostgreSQL 17 and Redis 8 when running services outside Compose;
- a Chromium/Firefox/WebKit installation managed by Playwright for browser tests;
- Terraform 1.13.2 only when validating or operating the included AWS infrastructure.

Do not use the ignored `pnpm-lock.yaml` or `pnpm-workspace.yaml`; npm is authoritative.

## Quick Start

The supported local path uses Docker Compose for the backend services and npm for the frontend:

```bash
git clone https://github.com/mahmoudalmbaidin-veltrixai/veltrix-intelligence-platform.git
cd veltrix-intelligence-platform
cp .env.example .env
docker compose up --build -d
npm ci
npm run dev
```

The copied `.env` contains development placeholders only. Replace the local database password consistently before first use. Do not reuse any local value in staging or production.

The API entrypoint runs `alembic upgrade head` and deterministic governance/connector seeds before starting. Verify:

```bash
docker compose ps
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

Open `http://localhost:3009`. Account creation is an operator action; use the password-safe CLI flow documented in [Local setup](docs/deployment/LOCAL_SETUP.md).

## Local Development

Frontend:

```bash
npm ci
npm run dev
```

Backend infrastructure and a native API:

```bash
docker compose up -d postgres redis clamav
cd apps/api
python -m venv .venv
# Activate .venv for your shell, then:
python -m pip install -r requirements.lock
python -m pip install --no-deps -e .
cp .env.example .env
alembic upgrade head
uvicorn vip_api.main:app --reload --no-access-log
```

Workers, from `apps/api` with the same environment:

```bash
python -m vip_api.jobs.worker
python -m vip_api.pipelines.worker
```

The generic job worker performs dashboard-delivery and pipeline-schedule ticks. The AWS definition runs a singleton scheduler task with worker queues isolated from ordinary work. The development Compose stack does not define a separate scheduler service.

See [Development setup](docs/development/DEVELOPMENT_SETUP.md).

## Database Migrations

Alembic files under `apps/api/alembic/` are the database schema source of truth.

```bash
cd apps/api
alembic upgrade head
alembic current
alembic heads
alembic check
```

Create a migration only after reviewing the generated operations:

```bash
alembic revision --autogenerate -m "describe-change"
```

Production migrations must run once as a controlled release task before application services are promoted. See [Production deployment](docs/deployment/PRODUCTION_DEPLOYMENT.md).

## Testing

Frontend gates:

```bash
npm run lint
npm run format:check
npm run typecheck
npm run test
npm run build
```

Backend gates, from `apps/api`:

```bash
ruff check .
ruff format --check .
mypy src tests
pytest -m "not integration"
RUN_INTEGRATION_TESTS=1 pytest -m integration
python scripts/backend_quality.py
```

Browser gates require the live API, seeded test users, both workers, and Playwright browsers:

```bash
npx playwright install
npm run test:e2e
npm run test:a11y
```

Exact preparation steps and suite boundaries are in [Testing](docs/development/TESTING.md). Generated reports and traces are ignored and must be scanned before any evidence is intentionally committed.

## Demo Environment

Demo data is synthetic. The guarded scripts under `scripts/demo/` and `scripts/demo-stage4/` generate passwords at runtime and store credential material outside the repository using local operating-system protection. Never copy demo passwords into source files, documentation, spreadsheets, screenshots, or issue comments.

See [Demo environment](docs/demo/DEMO_ENVIRONMENT.md) and [Demo operator guide](docs/demo/DEMO_OPERATOR_GUIDE.md).

## Environment Configuration

[`.env.example`](.env.example) documents the root configuration contract. [`apps/api/.env.example`](apps/api/.env.example) is the native API subset. Local `.env*` files are ignored except for safe examples.

Production must supply database/Redis URLs, encryption and download-signing keys, metrics protection, SMTP credentials, trusted hosts, CORS/CSRF origins, secure-cookie settings, storage paths, and build identity through the hosting platform's secret/configuration service. See [Environment variables](docs/deployment/ENVIRONMENT_VARIABLES.md).

## Deployment

VIP is hosting-agnostic at the service-contract level. A deployment needs:

- a containerized static frontend;
- a containerized API;
- PostgreSQL;
- Redis;
- a generic/dashboard worker;
- a pipeline worker;
- one logical scheduler role;
- shared persistent filesystem storage for uploads and generated artifacts;
- TLS termination and reverse proxy/load balancing;
- external secret management.

SMTP, CDN, WAF, and external monitoring are activated according to the target environment. AWS Terraform is included as one implementation, not as a claim that other providers have been certified. See [Production deployment](docs/deployment/PRODUCTION_DEPLOYMENT.md).

## Production Requirements

Production requires externally managed PostgreSQL and Redis, durable encrypted backups, shared persistent storage, unique secrets, HTTPS, explicit CORS/CSRF/trusted-host configuration, secure cookies, malware scanning, monitored workers and scheduler, log/metric collection, and an SMTP provider when email delivery is enabled. Object-storage adapters are extension points; the verified V1 application provider is filesystem-based.

## Docker

- `docker-compose.yml` is for development only.
- `apps/api/Dockerfile` builds the non-root API/worker image and includes migrations.
- `infra/containers/web/Dockerfile` builds the Vue application and serves it as non-root Nginx on port 8080.
- `infra/postgres/Dockerfile` hardens the local PostgreSQL image's privilege-drop helper.
- `.dockerignore` and `apps/api/.dockerignore` keep credentials, dependencies, docs, reports, and runtime artifacts out of image contexts.

There is no production Compose file. Use the deployment contract or the reviewed Terraform implementation rather than promoting development defaults.

## Infrastructure

`infra/aws/` contains the existing Terraform implementation. It is separated from application code and includes networking, load balancing/TLS, ECS services/tasks, RDS, Redis, storage, Secrets Manager integration, backups, WAF, monitoring, email configuration, and deployment/rollback/smoke scripts. It has not been applied or live-certified by this repository-preparation task.

See [Infrastructure overview](infra/README.md) and [AWS implementation](infra/aws/README.md).

## CI/CD

`.github/workflows/quality-gate.yml` runs repository scanning, Terraform validation, frontend static/unit/build checks, browser tests, backend static/unit/integration checks, Alembic checks, and backend image scanning. `.github/workflows/deploy-certified-release.yml` is a manually dispatched AWS promotion workflow and requires GitHub environments, OIDC, repository/environment variables, a certified release SHA, and provisioned infrastructure.

No workflow result should be treated as a production approval without the manual gates described in the operations documentation.

## Security

VIP uses API-side authorization, tenant-qualified data access, HttpOnly sessions, CSRF protection, encrypted connector credentials, protected download tokens, audit events, and production configuration validation. Secrets belong in environment-specific secret managers, never Git.

Report suspected vulnerabilities privately using [SECURITY.md](SECURITY.md). Do not include live credentials, customer data, or exploit data in a public issue.

## V1 Limitations

- PostgreSQL plus CSV/XLSX ingestion are the primary verified V1 source paths; other connectors have explicit beta/planned/driver/agent statuses.
- Anonymous dashboard sharing is not implemented.
- SMTP must be configured for real email; local file outbox delivery is development evidence only.
- SSO and MFA are not currently available.
- AI, Reports, Automation, Billing, Marketplace, and Developer surfaces are gated or incomplete and are not V1 GA capabilities.
- The included AWS infrastructure is defined and statically tested but still requires account-specific planning, apply, smoke testing, and operational approval.

See [Known limitations](docs/product/KNOWN_LIMITATIONS.md).

## Documentation

Start with the [documentation index](docs/README.md). It links architecture, setup, deployment, environment, operations, product scope, demo, development, and historical certification material without treating historical reports as current release claims.

## License

No public license is currently defined. Copyright © Veltrix AI. All rights reserved. Public visibility does not grant permission to use, copy, modify, or distribute this code.

## Support / Contact

No public support address is defined in this repository. Use the private project communication channel designated by the repository owner.
