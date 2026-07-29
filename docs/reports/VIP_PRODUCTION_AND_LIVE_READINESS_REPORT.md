# VIP Production and Live Readiness Report

Assessment date: 2026-07-28
Scope: B0–B8 codebase and certified local runtime

## Executive Assessment

The B0–B8 codebase is ready for local development, controlled internal UAT, and pilot packaging.
It is not, by this report alone, a deployed public production system. Live readiness depends on
external infrastructure, operating procedures, credentials, capacity evidence, and organizational
controls that do not belong in the repository.

| Stage | Status | Meaning |
| --- | --- | --- |
| Local development | Ready | Compose stack, migrations, services, tests and deterministic scenarios pass |
| Internal UAT | Ready | Real auth/RBAC/AV/pipeline/dashboard paths are usable with controlled data |
| Pilot | Conditional | Provision production-like managed services, secrets, mail, storage, monitoring and backup |
| Production | Not yet authorized | Complete all live prerequisites and operational acceptance |
| Live version | Blocked pending deployment program | No live infrastructure or release approval was in scope |

## Certified Application Controls

- cookie/session authentication with refresh rotation, CSRF, lockout and revocation;
- organization/workspace isolation and role enforcement;
- encrypted, write-only connection credentials;
- fail-closed ClamAV ingestion with persisted scan evidence;
- deterministic pipeline artifacts, rejected rows, retry/cancel/lease recovery;
- tenant-scoped dashboards, one-use exports, and delivery state;
- audit, jobs, SSE/fallback events, readiness and protected metrics;
- one linear migration head and empty/populated database validation;
- dependency, secret, workflow, image, backend, frontend and browser gates.

## Required Live Infrastructure

| Requirement | Production expectation |
| --- | --- |
| PostgreSQL | Managed HA service, encrypted storage/transport, PITR, replicas as needed, tested restore |
| Redis | Managed HA, TLS/auth, persistence/eviction policy, failover test |
| Object storage | Durable encrypted bucket, versioning, lifecycle/retention, malware quarantine policy |
| ClamAV | Scaled monitored service, signature freshness alert, fail-closed network policy |
| Secrets/KMS | External secret manager and KMS/HSM rotation; no Compose defaults |
| Email | Approved SMTP/API provider, DKIM/SPF/DMARC, bounce/complaint handling |
| Networking | Private service network, TLS ingress, DNS, WAF, egress policy, rate limits |
| Compute | Orchestrated API/workers, resource requests/limits, autoscaling, graceful drains |
| Observability | Metrics backend, dashboards, logs, traces/correlation IDs, paging routes and SLOs |

## Required Configuration and Security Controls

- set `APP_ENV=production`, disable docs unless explicitly approved, and provide non-default secrets;
- require secure cookies, approved SameSite/domain, exact CORS and CSRF origins, and trusted hosts;
- rotate connection encryption, download-signing, metrics, database, Redis, email, and service keys;
- place metrics behind private networking in addition to bearer authentication;
- configure tenant quotas, retention, export expiry, upload limits, and audit retention;
- run SAST/SCA/container/secret checks in protected CI on every release;
- commission threat modeling and an external penetration test for the deployed topology;
- configure vulnerability exception governance with owners and expiry—never silent suppression.

## Data, Privacy, and Compliance

Before live use, classify accepted data, document controller/processor responsibilities, establish
data residency and subprocessor terms, define deletion/export procedures, approve retention, and
test legal-hold/audit requirements. Seed/demo data and development-file deliveries must never be
copied into production.

## Reliability and Operations

Required operational acceptance includes:

1. representative load and soak tests for API, query, export and both workers;
2. backup restore and point-in-time recovery drills with recorded RPO/RTO;
3. worker-loss, Redis failover, PostgreSQL failover, ClamAV outage, storage outage, and mail outage
   game days;
4. rolling or blue/green deployment with migration ordering and backward compatibility;
5. rollback/run-forward procedure for every migration;
6. alerts for readiness, error rate, latency, queue age, lease recovery, delivery failure, scanner
   freshness, disk/storage and database saturation;
7. incident response, on-call, escalation, status communication and security disclosure runbooks.

## Supply-Chain Assessment

Application API/dashboard/pipeline images have zero Docker Scout critical/high findings. Redis
8.0.6 is digest pinned and reports zero critical/high. The official PostgreSQL 17.10 base SBOM
retains findings for an upstream Go `gosu` helper. The VIP derivative removes that runtime binary
and replaces it with native `su-exec`; runtime privilege-drop proof passes and the derivative
introduces zero critical/high findings. The raw historical-layer finding remains visible and must
be repinned when upstream publishes a rebuilt base. ClamAV is digest pinned and reports zero
critical/high.

## Deployment Go/No-Go Checklist

- [ ] Production tenant/data owner approval
- [ ] Managed PostgreSQL/Redis/object storage provisioned and hardened
- [ ] KMS/secrets and rotation tested
- [ ] Production mail provider tested
- [ ] TLS/DNS/WAF/private networking verified
- [ ] Migrations rehearsed on a production-like copy
- [ ] Capacity/soak thresholds met
- [ ] Backup restoration and DR exercise passed
- [ ] Monitoring, SLOs and paging operational
- [ ] Security review and penetration test accepted
- [ ] Data/privacy/compliance review accepted
- [ ] Rollout and rollback approved
- [x] Hosted CI green on the certified release SHA (immutable run recorded in the final response)

## Conclusion

B0–B8 implementation readiness is green. Internal UAT may proceed, and pilot preparation may
begin. A live production go-live remains a separate controlled decision after every unchecked
deployment prerequisite above is satisfied. Local Docker success is not equated with live
production readiness.
