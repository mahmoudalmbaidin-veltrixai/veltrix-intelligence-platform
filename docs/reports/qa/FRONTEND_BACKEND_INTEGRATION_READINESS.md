# VIP Frontend Backend-Integration Readiness

Audit date: 2026-07-18  
Readiness score: **45 / 100**  
Verdict: **NOT READY FOR BACKEND INTEGRATION**

The repository now has a useful integration foundation, but it does not yet support replacing mocks endpoint by endpoint across the product. Only Authentication and Dashboards use the mock/live service factory. Tenant context is not session-authoritative, editor persistence is not tenant-scoped, and most modules import concrete mock services.

## Existing API architecture

### Confirmed strengths

- `src/shared/lib/apiClient.ts` centralizes `fetch`; no page/component-level direct `fetch` or Axios call was found.
- Base URL, API mode and timeout are environment-configured.
- Requests can attach bearer authorization, organization ID, workspace ID, locale, timezone and correlation ID.
- JSON, multipart upload and blob download methods exist.
- Requests support `AbortSignal`, timeout and bounded retry for idempotent methods.
- HTTP errors are normalized into a typed application error with status, code, message, field errors, trace ID and retryability.
- Authentication and Dashboard modules demonstrate the intended service-interface plus mock/live-adapter pattern.
- Production dependencies had no reported npm audit advisories.

### Confirmed gaps

- Only two production `defineService(...)` selections exist: Authentication and Dashboards.
- Connections, Pipelines, Datasets, Semantic, Reports, AI, Automation, Operations, Admin, Billing, Usage, Marketplace and Developer Portal remain mock implementations without equivalent live adapters.
- API client tests cover only a small subset of helpers/status behavior; request headers, 401, retry, timeout, cancellation, upload, download and response parsing are not fetch-level tested.
- There is no generated/OpenAPI client, runtime DTO validation or consumer-driven contract test.
- Pagination envelopes and metadata are not centrally modeled/extracted despite backend documentation describing pagination.
- A cancellation is normalized as a timeout; the caller cannot reliably distinguish user cancellation from network timeout.
- No refresh-token/re-authentication policy follows a 401.
- Live streams, background runs and uploads are still simulated with timers/local state.
- Development/staging-like live mode with no base URL silently reverts to mock; only production fails closed.

## Mock architecture

| Area                      | Current state                              | Replacement readiness                                                                                 |
| ------------------------- | ------------------------------------------ | ----------------------------------------------------------------------------------------------------- |
| Authentication            | Service interface with mock/live adapters  | **Partial**—session context is not applied to platform context; logout mock is not durable.           |
| Dashboards                | Service interface with mock/live adapters  | **Partial**—editor/new-resource routing and export/delivery contracts remain incomplete.              |
| Pipelines                 | Concrete mock/local-storage service        | **Not ready**—no live adapter; editor persistence and run simulation tightly define current behavior. |
| Connections               | Concrete mock service                      | **Not ready**—wizard/spec mismatch and credential/validation contracts need definition.               |
| Datasets/Semantic         | Mock services and some inline fixture data | **Not ready**—tenant-aware query/cache and DTO boundaries absent.                                     |
| Reports/Deliveries        | Local simulated service/actions            | **Not ready**—real render, export, approval and delivery contracts absent.                            |
| AI/Knowledge/Agents       | Timer/inline mock behavior                 | **Not ready**—streaming, ingestion, citations and run-event protocols undefined.                      |
| Automation                | Concrete simulation                        | **Not ready**—run, approval, retry and event models need contracts.                                   |
| Admin/Billing/Usage/Audit | Concrete mock fixtures                     | **Not ready**—authorization, audit integrity and tenant isolation must be backend-enforced.           |
| Marketplace/Developer     | Local simulated state                      | **Not ready**—installation, secret lifecycle, webhook and API-key contracts incomplete.               |

Mock data is not consistently accessed through module interfaces. `KnowledgeView` and global search contain direct fixtures, and persisted dashboard/pipeline/delivery stores are not partitioned by tenant/workspace. This prevents credible tenant-isolation tests and makes some endpoint replacements require view/state changes.

## Authentication readiness

Score: **46 / 100**

- Positive: auth bootstrap occurs before application mount; public-only/protected routes exist; login/logout/me interfaces exist; API calls can use cookies and optional authorization headers; permission and entitlement guards work for tested routes.
- Critical gap: the authenticated session's organization/workspace/user are not the authoritative source for `PlatformStore` and request-context headers.
- High gap: a 401 updates auth state but does not route away from already-rendered protected content.
- High gap: mock logout is undone by refresh because bootstrap seeds a demo session.
- Governance gap: feature flags hide navigation without protecting direct routes.
- Required rule: all permissions, tenant isolation, feature entitlements and object ownership must be enforced by backend endpoints. Frontend guards are only a UX layer.

## Error-handling readiness

Score: **58 / 100**

The client normalizes many HTTP statuses and carries a trace ID, but consumers are mostly mocks, so shared live error UX is unproven. There is no exercised global session-expiry flow, offline strategy, conflict-resolution flow, rate-limit countdown, or 422 field-error mapping across real forms. Cancellation and timeout are conflated. Current browser testing cannot validate 409/422/429/5xx behavior without live adapters or a network-mocking E2E harness.

## Environment readiness

Score: **62 / 100**

- Typed `VITE_APP_ENV`, `VITE_API_MODE`, `VITE_API_BASE_URL`, timeout and feature settings exist.
- Production live mode fails when the base URL is absent.
- Non-production live mode can silently become mock mode, which risks false-positive staging acceptance.
- No checked-in secret was identified; `demo-password` is a UI fixture, not a credential, but should never prefill in live/staging.
- Production source maps are absent; a protected observability upload strategy should be decided.

## Tenant and workspace context readiness

Score: **25 / 100**

The API client can send organization/workspace headers, and switching context invalidates query cache. However, the context originates from hardcoded/persisted `PlatformStore` defaults rather than being atomically hydrated from the authenticated session. Browser testing showed the same Home KPIs and recent resources in different organizations. Editor local-storage keys are global, not tenant/workspace-specific. Until this is fixed, integration can send requests under an inconsistent tenant context and frontend tests cannot prove isolation.

## Endpoint integration risks

1. **Cross-tenant requests:** stale hardcoded organization/workspace headers can be attached before/after auth bootstrap.
2. **Mock/live divergence:** most modules have no live adapter, so a switch to live mode does not switch the application as a whole.
3. **Unstable create routes:** newly saved Dashboards and Pipelines remain on `/new`, so backend-created IDs cannot be safely deep-linked/reloaded.
4. **Contract drift:** hand-authored types are not verified against an API schema.
5. **Unproven errors:** pages have not exercised real 401/403/409/422/429/5xx/offline flows.
6. **Simulation presented as success:** export, delivery, upload, AI streaming and runs need explicit async-job/event contracts.
7. **Cache leakage:** persisted stores and some mock caches are not tenant-scoped.
8. **Governance bypass:** feature flags are not enforced in route metadata, and backend enforcement is not available yet.

## Required improvements before endpoint integration

### Gate 1—identity and context

- Define one typed `SessionContext` as the authoritative user/organization/workspace/role/entitlement source.
- Hydrate or clear `PlatformStore` atomically during bootstrap/login/logout.
- Block protected rendering/requests until context hydration finishes.
- Implement and test 401 session-expiry navigation, 403 behavior, redirect restoration and request cancellation.
- Partition local mocks, query keys and editor persistence by tenant/workspace.

### Gate 2—adapter and contract pattern

- Require every module to export an interface and select mock/live implementations through the existing factory.
- Move inline fixtures behind those interfaces.
- Adopt an OpenAPI-generated client or schema-validated DTO boundary.
- Add fetch-level API-client tests for headers, correlation IDs, retries, timeouts, cancellation, file transfer and all required status codes.
- Fail closed in staging/CI if live mode lacks configuration.

### Gate 3—critical editor integrity

- Route newly created Dashboards/Pipelines to stable ID URLs.
- Fix Pipeline edge/node selection deletion.
- Specify async save/version conflict behavior and unsaved-change handling.
- Define export/delivery/job-event contracts without presenting `.txt` manifests or timers as production success.

### Gate 4—accessibility and release automation

- Add keyboard-authoring alternatives for both studios and repair shared primitives.
- Add Playwright route/workflow/guard tests and axe checks to CI.
- Establish a minimal live-contract test environment with two organizations/workspaces to prove isolation.

## Recommended integration order

Do **not** begin broad endpoint-by-endpoint page integration yet. Preparatory backend contract work may proceed in parallel, but frontend endpoint wiring should start only after Gates 1–2.

1. **Session bootstrap and identity context** (`login`, `logout`, `me`, refresh/session expiry).
2. **Organizations/workspaces/permissions/entitlements/feature flags**, with two-tenant isolation tests.
3. **Shared API contracts**: pagination, errors, trace IDs, uploads/downloads and async-job status.
4. **Read-only catalog/list endpoints**: Connections, Datasets and Semantic metadata.
5. **Dashboard CRUD**, only after stable create routing; then widget data, filters, versions and sharing.
6. **Pipeline CRUD**, only after editor deletion/integrity fixes; then validate/run/log/retry events.
7. **Reports/deliveries/exports** with real asynchronous render and delivery jobs.
8. **Automation and AI** after streaming/event, approval and ingestion protocols are agreed.
9. **Billing, Developer and Marketplace mutations** after authorization, idempotency and audit contracts are proven.

## Integration decision

**Backend integration may not begin as the primary implementation phase.** The central client and two example adapters are suitable for a short remediation/contract sprint. Once identity/context isolation and the universal adapter boundary are verified, limited read-only integration can begin in the order above. Dashboard/Pipeline mutations, exports, deliveries, administration, billing and AI/automation must wait for their listed gates.
