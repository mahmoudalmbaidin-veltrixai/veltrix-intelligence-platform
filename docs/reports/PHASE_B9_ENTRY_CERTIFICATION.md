# Phase B9 Entry Certification

Certification date: 2026-07-28
Scope boundary: B0–B8 closure only

## Certified B0–B8 Foundation

Phase B9 may be defined on the following verified foundation:

- username/optional-email authentication, sessions and recovery controls;
- organization/workspace tenancy, membership, invitations, RBAC and platform administration;
- encrypted connections and supported source catalog;
- datasets, real fail-closed malware scanning, preview/profile/quality;
- semantic models, metrics, glossary and safe formulas;
- versioned deterministic pipelines with row rejection and resilient workers;
- versioned dashboards, mapped filters, PDF/PNG/JSON/CSV exports and scheduled delivery;
- jobs, events/SSE, notifications, audit, health/readiness/version and protected metrics;
- one linear Alembic head `20260728_0015`;
- green backend, frontend, browser, accessibility, migration, dependency and security gates.

## Approved Dependencies

| Dependency | Certified use |
| --- | --- |
| PostgreSQL 17.10 | Primary relational persistence |
| Redis 8.0.6 | Session, coordination and worker support |
| ClamAV 1.5.3 | Fail-closed upload malware scanning |
| FastAPI/SQLAlchemy/Alembic | API, persistence and migrations per lockfile |
| Vue/Vite/TypeScript | Frontend per lockfile |
| Playwright/axe | Browser and accessibility regression |

Exact container bases are digest pinned in Compose/workflow configuration. Python and JavaScript
packages remain governed by their committed lockfiles.

## Known Exclusions

- public cloud/live infrastructure and release authorization;
- production SMTP, managed object storage, KMS, monitoring and paging integrations;
- load/soak, external penetration, disaster-recovery and compliance acceptance;
- AI model/provider, agent, knowledge-base, prompt or evaluation implementation;
- Automation trigger/action/orchestrator implementation;
- production Report Builder, Marketplace and Billing domains.

## Modules Not to Treat as Complete

AI, Automation, Reports, Marketplace, Billing, portions of Insights/Explore/Developer/Settings,
and static/demo content are not promoted by this certification. Their exact frontend/backend/mock
classification is maintained in `VIP_PLATFORM_FRONTEND_BACKEND_CAPABILITY_MATRIX.md`.

## Recommended B9 Starting Architecture

Before B9 coding, define its domain boundary, threat model, tenant/RBAC permissions, persistence
ownership, event contracts, quotas, audit vocabulary, failure/retry semantics, observability,
provider abstraction, migration sequence, rollout flags, and acceptance tests. Reuse:

- current tenant context and non-disclosing authorization patterns;
- job/lease/idempotency infrastructure for asynchronous work;
- encrypted secret-provider abstraction for external credentials;
- artifact storage and one-use download patterns;
- event/SSE plus bounded polling fallback;
- audit and low-cardinality metrics conventions.

Any B9 database change must descend from `20260728_0015` and preserve a single Alembic head.
Mocks must be explicitly labelled and kept out of production code paths.

## Entry Decision

**B0–B8 CERTIFIED — READY TO DEFINE AND START PHASE B9**

This decision authorizes definition and a separately reviewed B9 implementation phase. It does not
authorize a public production launch.

## Explicit Closure Boundary

No Phase B9 code was implemented in this closure task. No AI or Automation code was added. The
work performed here is limited to B0–B8 stabilization, missing production evidence, regression
coverage, supply-chain/runtime hardening, and certification documentation.
