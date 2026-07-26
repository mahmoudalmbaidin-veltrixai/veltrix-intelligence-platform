# VIP Complete System Workflow Documentation

**Platform:** Veltrix Intelligence Platform (VIP)
**Diagram version:** 1.0
**Generated:** 2026-07-21
**Repository commit:** `33a8356da18b5d74831f2a79b727a73779900f50`
**Source diagram:** `VIP_COMPLETE_SYSTEM_WORKFLOW.drawio`

## Scope and source-of-truth statement

This package was generated before the B0-B8 backend implementation and remains a target-operating-model diagram, not a current implementation inventory. The repository now includes a FastAPI service, PostgreSQL migrations, Redis-backed queues/events, workers, governed file/artifact storage, live adapters for the B0-B8 surfaces, and automated backend/integration/browser validation. Statements below that describe the backend as absent or planned are historical diagram annotations and are superseded by the phase documentation in `docs/backend/` and `FINAL_RC_CERTIFICATION_REPORT.md`.

## Assumptions

- PostgreSQL, Redis, local/provider-backed object storage, worker services, and the FastAPI API are implemented B0-B8 components. Email and AI providers remain target-state integrations outside this certification scope.
- HTTP-only cookie sessions, refresh rotation, replay detection, and CSRF validation are implemented; external identity-provider and MFA/SSO integrations remain later-phase work.
- Organization and workspace headers are context hints; backend authorization derives and validates authoritative membership.
- All destructive tenant and lineage-impacting actions require fresh authorization, dependency checks and auditable confirmation.
- AI diagrams show safe execution traces only: context references, tool calls, policy decisions and outcome status, never private chain-of-thought.

## Status legend

| Status | Diagram style | Meaning |
|---|---|---|
| Implemented | Solid blue border | Working frontend behavior evidenced in code/tests |
| Partially implemented | Orange border | UI or adapter seam exists, but live integration/depth is incomplete |
| Planned | Dashed grey border | Target architecture or documented backend dependency |
| Missing / blocked | Red border | Required production capability lacks implementation evidence |
| Validated successful outcome | Green border | Successful terminal state |
| Requires clarification | Dashed violet border | Architecture, policy or ownership decision is unresolved |

## Connector legend

| Connector | Meaning |
|---|---|
| Solid arrow | Synchronous UX or API call |
| Dashed arrow | Asynchronous queue/job/provider interaction |
| Dotted arrow | Event, progress, log or telemetry publication |
| Red arrow | Failure or denial |
| Green arrow | Successful result |
| Double-headed arrow | True bidirectional communication only |

## Cross-page references

- Page 1 is the operating-model index; Pages 2-11 expand business modules.
- Page 12 defines target backend communication for every module.
- Page 13 defines lineage and dependency impact used by Connections, Pipelines, Datasets, Dashboards, Reports, AI and Automation.
- Page 14 is the standard exception/recovery subprocess for every page.
- Page 15 is the mandatory audit/telemetry subprocess for every protected or asynchronous action.
- Page 16 covers current frontend CI evidence and target runtime promotion.

## Page 1 - VIP End-to-End Platform Workflow

### Purpose

Complete operating model from entry through governed delivery and telemetry.

### Actors

Access & SaaS gates, Data foundation, Analytics & intelligence, Automation, delivery & control, Exception paths.

### Preconditions

An authenticated or initiating actor has an organization/workspace context where applicable; route metadata, permissions, entitlements, tenant status and quotas are evaluated before protected work. Planned backend operations also require configured providers, durable storage and worker capacity.

### Trigger

The actor opens the relevant module, invokes an API, a schedule becomes due, or a domain event is published.

### Main workflow

- **Access & SaaS gates:** User opens VIP -> Authenticate / validate session -> Select organization -> Select workspace -> Tenant active? -> Subscription / entitlement / quota check -> RBAC permission check -> Application shell loads.
- **Data foundation:** Select platform module -> Create data connection -> Validate required configuration -> Test connection -> Encrypt & vault credentials -> Ingest source data -> Design + validate pipeline -> Queue and execute run -> Transform + quality rules -> Create / update dataset.
- **Analytics & intelligence:** Configure semantic model -> Design dashboard + widgets -> Add filters / interactions -> Preview and validate bindings -> Save draft / version -> Publish dashboard -> Share / secure embed -> Generate report / export -> AI retrieves approved context -> AI insight / agent outcome.
- **Automation, delivery & control:** Trigger automation / approval -> Schedule pipeline, dashboard, report, email or AI job -> Billing / usage check -> Execute async action -> Email / notification delivery -> Audit record -> Usage metering -> Logs + metrics + traces -> Delivered / monitored.
- **Exception paths:** 401 -> Login / refresh -> 403 -> Forbidden -> Feature disabled / config required -> Quota exceeded / upgrade -> Validation failure -> correct input -> Transient failure -> retry policy -> Approval rejected / cancelled -> Repeated failure -> DLQ + admin alert.

### Alternative flows

- Mock mode uses typed in-memory/localStorage adapters for review and testing.
- Live mode routes through the centralized API client when the endpoint family is activated.
- Cross-page subprocesses use the page references listed below instead of duplicating implementation detail.

### Failure flows

Validation, authentication, authorization, configuration, quota, provider, timeout, cancellation and partial-completion failures return a safe message and correlation ID. Retryable idempotent work follows bounded retry; exhausted asynchronous work is expected to enter a failed-job/DLQ path. See Page 14.

### Services involved

Access & SaaS gates, Data foundation, Analytics & intelligence, Automation, delivery & control, Exception paths; centralized API client; relevant domain service adapters; planned orchestration/worker/provider services shown on the diagram.

### Databases involved

Current frontend localStorage-backed mock stores where implemented. Target state: PostgreSQL for transactional metadata, Redis for queue/cache/leases, and object storage for files/exports/intermediate data; these backend components are planned rather than repository-proven.

### Events generated

Domain create/update/publish/run/completion/failure events, progress updates, notification events, audit events and usage events as shown. Event infrastructure is planned unless explicitly surfaced by current mock behavior.

### Audit records generated

Actor, tenant, workspace, action, resource, outcome, timestamp and correlation ID; sensitive fields must be redacted. Current audit UI/data is mock-backed.

### Security controls

Session validation; organization/workspace scoping; RBAC; feature flags; entitlements; quota checks; safe errors; correlation IDs; secret redaction. Backend enforcement remains mandatory.

### Implementation status

Statuses represented: Implemented, Partially implemented, Missing / blocked, Planned, Validated successful outcome. Borders are evidence-based at repository commit `33a8356da18b5d74831f2a79b727a73779900f50`.

### Open gaps

Authoritative backend execution, storage, provider integration, production authorization, durable audit/usage data and operational runbooks remain incomplete unless a node is specifically blue. Clarifications are listed in the final findings page and validation report.

### Related repository files

- `ARCHITECTURE.md`
- `BACKEND_INTEGRATION.md`
- `MODULE_STATUS.md`
- `FRONTEND_BACKEND_INTEGRATION_BASELINE.md`
- `src/app/router/index.ts`
- `src/shared/lib/apiClient.ts`
- `src/shared/contracts/apiContracts.ts`
- `src/app/navigation.ts`
- `src/shared/stores/platform.ts`

## Page 2 - User Access, Authentication and SaaS Workflow

### Purpose

Identity, tenant context, feature access and session lifecycle.

### Actors

User, Frontend, Authentication service, Organization service, Workspace service, RBAC service, Billing / entitlement service, Database & audit.

### Preconditions

An authenticated or initiating actor has an organization/workspace context where applicable; route metadata, permissions, entitlements, tenant status and quotas are evaluated before protected work. Planned backend operations also require configured providers, durable storage and worker capacity.

### Trigger

The actor opens the relevant module, invokes an API, a schedule becomes due, or a domain event is published.

### Main workflow

- **User:** Login / signup / accept invitation -> Password reset -> MFA challenge -> Choose or create organization -> Choose or create workspace -> Switch organization / workspace -> Logout.
- **Frontend:** Validate form -> POST login / refresh -> Store session state; prefer HTTP-only cookie -> Route guard -> Load application shell -> Clear caches and scoped context.
- **Authentication service:** Verify credentials -> MFA / SSO policy -> Create session -> Refresh session -> Revoke session.
- **Organization service:** Organization membership -> Tenant status: trial / active / suspended / disabled -> Organization switch context.
- **Workspace service:** Workspace membership -> Workspace create / archive -> Workspace switch context.
- **RBAC service:** Resolve role and permissions -> Permission allowed? -> 403 Forbidden.
- **Billing / entitlement service:** Feature flag check -> Entitlement / subscription / trial check -> Suspended / expired / upgrade handling.
- **Database & audit:** Identity / membership / session records -> Tenant / workspace records -> Authentication and access audit.

### Alternative flows

- Mock mode uses typed in-memory/localStorage adapters for review and testing.
- Live mode routes through the centralized API client when the endpoint family is activated.
- Cross-page subprocesses use the page references listed below instead of duplicating implementation detail.

### Failure flows

Validation, authentication, authorization, configuration, quota, provider, timeout, cancellation and partial-completion failures return a safe message and correlation ID. Retryable idempotent work follows bounded retry; exhausted asynchronous work is expected to enter a failed-job/DLQ path. See Page 14.

### Services involved

User, Frontend, Authentication service, Organization service, Workspace service, RBAC service, Billing / entitlement service, Database & audit; centralized API client; relevant domain service adapters; planned orchestration/worker/provider services shown on the diagram.

### Databases involved

Current frontend localStorage-backed mock stores where implemented. Target state: PostgreSQL for transactional metadata, Redis for queue/cache/leases, and object storage for files/exports/intermediate data; these backend components are planned rather than repository-proven.

### Events generated

Domain create/update/publish/run/completion/failure events, progress updates, notification events, audit events and usage events as shown. Event infrastructure is planned unless explicitly surfaced by current mock behavior.

### Audit records generated

Actor, tenant, workspace, action, resource, outcome, timestamp and correlation ID; sensitive fields must be redacted. Current audit UI/data is mock-backed.

### Security controls

Session validation; organization/workspace scoping; RBAC; feature flags; entitlements; quota checks; safe errors; correlation IDs; secret redaction. Backend enforcement remains mandatory.

### Implementation status

Statuses represented: Partially implemented, Planned, Implemented. Borders are evidence-based at repository commit `33a8356da18b5d74831f2a79b727a73779900f50`.

### Open gaps

Authoritative backend execution, storage, provider integration, production authorization, durable audit/usage data and operational runbooks remain incomplete unless a node is specifically blue. Clarifications are listed in the final findings page and validation report.

### Related repository files

- `ARCHITECTURE.md`
- `BACKEND_INTEGRATION.md`
- `MODULE_STATUS.md`
- `FRONTEND_BACKEND_INTEGRATION_BASELINE.md`
- `src/app/router/index.ts`
- `src/shared/lib/apiClient.ts`
- `src/shared/contracts/apiContracts.ts`
- `src/modules/auth/LoginView.vue`
- `src/shared/services/auth/apiAuthService.ts`
- `src/shared/stores/auth.ts`
- `src/shared/permissions/roles.ts`

## Page 3 - Connection Studio Workflow

### Purpose

Connector onboarding, discovery, ingestion lifecycle and dependency-safe retirement.

### Actors

Connection Studio UI, Connector categories, Connection service, Ingestion orchestration, Governance.

### Preconditions

An authenticated or initiating actor has an organization/workspace context where applicable; route metadata, permissions, entitlements, tenant status and quotas are evaluated before protected work. Planned backend operations also require configured providers, durable storage and worker capacity.

### Trigger

The actor opens the relevant module, invokes an API, a schedule becomes due, or a domain event is published.

### Main workflow

- **Connection Studio UI:** Open Connection Studio -> Select connector category / type -> Enter connection details -> Validate required fields -> Test connection -> Save connection -> Update credentials / disable / delete.
- **Connector categories:** Relational databases -> Cloud storage & files -> APIs & SaaS applications -> Data warehouses -> Streaming sources.
- **Connection service:** Assign organization + workspace -> Configure permissions -> Encrypt credentials -> Store in secrets vault -> Discover schemas / tables / objects -> Preview source data -> Dependency impact check.
- **Ingestion orchestration:** Select source objects -> Configure refresh policy -> Configure incremental ingestion -> Create ingestion job -> Monitor ingestion -> Retry failed ingestion -> Dataset handoff.
- **Governance:** Test failure diagnostics -> Credential rotation required -> Delete blocked by dependencies -> Audit create / test / update / disable / delete.

### Alternative flows

- Mock mode uses typed in-memory/localStorage adapters for review and testing.
- Live mode routes through the centralized API client when the endpoint family is activated.
- Cross-page subprocesses use the page references listed below instead of duplicating implementation detail.

### Failure flows

Validation, authentication, authorization, configuration, quota, provider, timeout, cancellation and partial-completion failures return a safe message and correlation ID. Retryable idempotent work follows bounded retry; exhausted asynchronous work is expected to enter a failed-job/DLQ path. See Page 14.

### Services involved

Connection Studio UI, Connector categories, Connection service, Ingestion orchestration, Governance; centralized API client; relevant domain service adapters; planned orchestration/worker/provider services shown on the diagram.

### Databases involved

Current frontend localStorage-backed mock stores where implemented. Target state: PostgreSQL for transactional metadata, Redis for queue/cache/leases, and object storage for files/exports/intermediate data; these backend components are planned rather than repository-proven.

### Events generated

Domain create/update/publish/run/completion/failure events, progress updates, notification events, audit events and usage events as shown. Event infrastructure is planned unless explicitly surfaced by current mock behavior.

### Audit records generated

Actor, tenant, workspace, action, resource, outcome, timestamp and correlation ID; sensitive fields must be redacted. Current audit UI/data is mock-backed.

### Security controls

Session validation; organization/workspace scoping; RBAC; feature flags; entitlements; quota checks; safe errors; correlation IDs; secret redaction. Backend enforcement remains mandatory.

### Implementation status

Statuses represented: Implemented, Partially implemented, Planned, Missing / blocked. Borders are evidence-based at repository commit `33a8356da18b5d74831f2a79b727a73779900f50`.

### Open gaps

Authoritative backend execution, storage, provider integration, production authorization, durable audit/usage data and operational runbooks remain incomplete unless a node is specifically blue. Clarifications are listed in the final findings page and validation report.

### Related repository files

- `ARCHITECTURE.md`
- `BACKEND_INTEGRATION.md`
- `MODULE_STATUS.md`
- `FRONTEND_BACKEND_INTEGRATION_BASELINE.md`
- `src/app/router/index.ts`
- `src/shared/lib/apiClient.ts`
- `src/shared/contracts/apiContracts.ts`
- `src/modules/connections/connections.service.ts`
- `src/modules/connections/ConnectionWizardView.vue`

## Page 4 - Pipeline Studio Workflow

### Purpose

Alteryx-style visual authoring and planned distributed pipeline execution.

### Actors

Canvas frontend, Pipeline API, Orchestration service, Queue / Redis, Execution workers, Database & storage, Monitoring & events.

### Preconditions

An authenticated or initiating actor has an organization/workspace context where applicable; route metadata, permissions, entitlements, tenant status and quotas are evaluated before protected work. Planned backend operations also require configured providers, durable storage and worker capacity.

### Trigger

The actor opens the relevant module, invokes an API, a schedule becomes due, or a domain event is published.

### Main workflow

- **Canvas frontend:** Open / create pipeline; blank or template -> Add source; drag processing nodes -> Connect typed ports -> Configure formulas, joins, unions, filters, sorts -> Configure aggregations, calculations, cleansing, type conversion -> Validation rules + output destination -> Save draft / autosave / version / publish.
- **Pipeline API:** Persist graph and optimistic version -> Validate graph -> Circular dependency check -> Missing configuration check -> Preview sample / selected node / from node -> Run complete pipeline -> Schedule / API / event trigger.
- **Orchestration service:** Create idempotent run -> Build execution DAG -> Queue execution -> Track progress + cancellation -> Retry from failed node.
- **Queue / Redis:** Pending job -> Lease / heartbeat / retry counter -> Dead-letter failed job.
- **Execution workers:** Worker claims job -> Execute node -> Transform data -> Node-level logs + row counts -> Cancel / timeout / worker failure.
- **Database & storage:** Pipeline + version metadata -> Run state / logs -> Intermediate / output objects -> Generate dataset.
- **Monitoring & events:** WebSocket / SSE progress -> Metrics / traces -> Completion / failure event -> Notification + audit record.

### Alternative flows

- Mock mode uses typed in-memory/localStorage adapters for review and testing.
- Live mode routes through the centralized API client when the endpoint family is activated.
- Cross-page subprocesses use the page references listed below instead of duplicating implementation detail.

### Failure flows

Validation, authentication, authorization, configuration, quota, provider, timeout, cancellation and partial-completion failures return a safe message and correlation ID. Retryable idempotent work follows bounded retry; exhausted asynchronous work is expected to enter a failed-job/DLQ path. See Page 14.

### Services involved

Canvas frontend, Pipeline API, Orchestration service, Queue / Redis, Execution workers, Database & storage, Monitoring & events; centralized API client; relevant domain service adapters; planned orchestration/worker/provider services shown on the diagram.

### Databases involved

Current frontend localStorage-backed mock stores where implemented. Target state: PostgreSQL for transactional metadata, Redis for queue/cache/leases, and object storage for files/exports/intermediate data; these backend components are planned rather than repository-proven.

### Events generated

Domain create/update/publish/run/completion/failure events, progress updates, notification events, audit events and usage events as shown. Event infrastructure is planned unless explicitly surfaced by current mock behavior.

### Audit records generated

Actor, tenant, workspace, action, resource, outcome, timestamp and correlation ID; sensitive fields must be redacted. Current audit UI/data is mock-backed.

### Security controls

Session validation; organization/workspace scoping; RBAC; feature flags; entitlements; quota checks; safe errors; correlation IDs; secret redaction. Backend enforcement remains mandatory.

### Implementation status

Statuses represented: Implemented, Partially implemented, Planned. Borders are evidence-based at repository commit `33a8356da18b5d74831f2a79b727a73779900f50`.

### Open gaps

Authoritative backend execution, storage, provider integration, production authorization, durable audit/usage data and operational runbooks remain incomplete unless a node is specifically blue. Clarifications are listed in the final findings page and validation report.

### Related repository files

- `ARCHITECTURE.md`
- `BACKEND_INTEGRATION.md`
- `MODULE_STATUS.md`
- `FRONTEND_BACKEND_INTEGRATION_BASELINE.md`
- `src/app/router/index.ts`
- `src/shared/lib/apiClient.ts`
- `src/shared/contracts/apiContracts.ts`
- `src/modules/pipelines/PipelineStudioView.vue`
- `src/modules/pipelines/pipelines.service.ts`
- `src/modules/pipelines/usePipelineRunner.ts`
- `src/modules/pipelines/usePipelineEditor.ts`

## Page 5 - Dataset and Semantic Model Workflow

### Purpose

Governed dataset lifecycle and reusable business semantic layer.

### Actors

Dataset lifecycle, Data quality, Governance & lineage, Semantic authoring, Consumption.

### Preconditions

An authenticated or initiating actor has an organization/workspace context where applicable; route metadata, permissions, entitlements, tenant status and quotas are evaluated before protected work. Planned backend operations also require configured providers, durable storage and worker capacity.

### Trigger

The actor opens the relevant module, invokes an API, a schedule becomes due, or a domain event is published.

### Main workflow

- **Dataset lifecycle:** Create dataset from ingestion / pipeline -> Detect schema + profile data -> Field mapping + data type management -> Validate dataset -> Refresh + version -> Owner + permissions -> Certify / archive.
- **Data quality:** Quality rules -> Duplicate detection -> Null handling -> Quality incidents -> Pass quality gate.
- **Governance & lineage:** Column / job lineage -> Dependency graph -> Impact analysis -> Audit ownership / certification / archival.
- **Semantic authoring:** Create semantic model -> Add dimensions / measures / hierarchies -> Calculated fields + relationships -> Business names + descriptions + formatting -> Default aggregation -> Row-level security -> Validate model -> Publish model.
- **Consumption:** Dashboard query -> Report query -> AI approved-context retrieval -> Automation condition -> Usage + audit.

### Alternative flows

- Mock mode uses typed in-memory/localStorage adapters for review and testing.
- Live mode routes through the centralized API client when the endpoint family is activated.
- Cross-page subprocesses use the page references listed below instead of duplicating implementation detail.

### Failure flows

Validation, authentication, authorization, configuration, quota, provider, timeout, cancellation and partial-completion failures return a safe message and correlation ID. Retryable idempotent work follows bounded retry; exhausted asynchronous work is expected to enter a failed-job/DLQ path. See Page 14.

### Services involved

Dataset lifecycle, Data quality, Governance & lineage, Semantic authoring, Consumption; centralized API client; relevant domain service adapters; planned orchestration/worker/provider services shown on the diagram.

### Databases involved

Current frontend localStorage-backed mock stores where implemented. Target state: PostgreSQL for transactional metadata, Redis for queue/cache/leases, and object storage for files/exports/intermediate data; these backend components are planned rather than repository-proven.

### Events generated

Domain create/update/publish/run/completion/failure events, progress updates, notification events, audit events and usage events as shown. Event infrastructure is planned unless explicitly surfaced by current mock behavior.

### Audit records generated

Actor, tenant, workspace, action, resource, outcome, timestamp and correlation ID; sensitive fields must be redacted. Current audit UI/data is mock-backed.

### Security controls

Session validation; organization/workspace scoping; RBAC; feature flags; entitlements; quota checks; safe errors; correlation IDs; secret redaction. Backend enforcement remains mandatory.

### Implementation status

Statuses represented: Partially implemented, Implemented, Planned. Borders are evidence-based at repository commit `33a8356da18b5d74831f2a79b727a73779900f50`.

### Open gaps

Authoritative backend execution, storage, provider integration, production authorization, durable audit/usage data and operational runbooks remain incomplete unless a node is specifically blue. Clarifications are listed in the final findings page and validation report.

### Related repository files

- `ARCHITECTURE.md`
- `BACKEND_INTEGRATION.md`
- `MODULE_STATUS.md`
- `FRONTEND_BACKEND_INTEGRATION_BASELINE.md`
- `src/app/router/index.ts`
- `src/shared/lib/apiClient.ts`
- `src/shared/contracts/apiContracts.ts`
- `src/modules/datasets/datasets.service.ts`
- `src/modules/datasets/DataLineageView.vue`
- `src/modules/semantic/semantic.service.ts`
- `src/shared/services/semanticModels.ts`

## Page 6 - Dashboard Studio Workflow

### Purpose

Power BI-style dashboard design, publication, sharing, export and consumption.

### Actors

Home & authoring, Layout & behavior, Validation & lifecycle, Share & delivery, Error states.

### Preconditions

An authenticated or initiating actor has an organization/workspace context where applicable; route metadata, permissions, entitlements, tenant status and quotas are evaluated before protected work. Planned backend operations also require configured providers, durable storage and worker capacity.

### Trigger

The actor opens the relevant module, invokes an API, a schedule becomes due, or a domain event is published.

### Main workflow

- **Home & authoring:** Open Dashboard Studio / home -> Create blank canvas or template -> Select dataset / semantic model -> Drag visualization to canvas -> Assign dimensions / measures + chart type -> Add text, image, shape, KPI, table, map, filter, slicer.
- **Layout & behavior:** Resize / move / align / group / layer widgets -> Responsive 12-column layout -> Formatting -> Drill-down / drill-through -> Cross-filtering + global/page/widget filters -> Parameters + interactions -> Multiple pages / tabs.
- **Validation & lifecycle:** Preview dashboard -> Validate data bindings -> Autosave / unsaved changes -> Save draft + optimistic version -> Version conflict -> Publish dashboard.
- **Share & delivery:** Set sharing permissions -> Public or secure embed -> Export PDF / image / data -> Schedule dashboard delivery -> Send dashboard by email -> View dashboard -> Capture usage + audit.
- **Error states:** Dataset unavailable -> Dataset permission denied -> Broken field reference -> Widget query failure -> Export failure -> Email delivery failure -> Unsaved changes.

### Alternative flows

- Mock mode uses typed in-memory/localStorage adapters for review and testing.
- Live mode routes through the centralized API client when the endpoint family is activated.
- Cross-page subprocesses use the page references listed below instead of duplicating implementation detail.

### Failure flows

Validation, authentication, authorization, configuration, quota, provider, timeout, cancellation and partial-completion failures return a safe message and correlation ID. Retryable idempotent work follows bounded retry; exhausted asynchronous work is expected to enter a failed-job/DLQ path. See Page 14.

### Services involved

Home & authoring, Layout & behavior, Validation & lifecycle, Share & delivery, Error states; centralized API client; relevant domain service adapters; planned orchestration/worker/provider services shown on the diagram.

### Databases involved

Current frontend localStorage-backed mock stores where implemented. Target state: PostgreSQL for transactional metadata, Redis for queue/cache/leases, and object storage for files/exports/intermediate data; these backend components are planned rather than repository-proven.

### Events generated

Domain create/update/publish/run/completion/failure events, progress updates, notification events, audit events and usage events as shown. Event infrastructure is planned unless explicitly surfaced by current mock behavior.

### Audit records generated

Actor, tenant, workspace, action, resource, outcome, timestamp and correlation ID; sensitive fields must be redacted. Current audit UI/data is mock-backed.

### Security controls

Session validation; organization/workspace scoping; RBAC; feature flags; entitlements; quota checks; safe errors; correlation IDs; secret redaction. Backend enforcement remains mandatory.

### Implementation status

Statuses represented: Implemented, Partially implemented, Planned. Borders are evidence-based at repository commit `33a8356da18b5d74831f2a79b727a73779900f50`.

### Open gaps

Authoritative backend execution, storage, provider integration, production authorization, durable audit/usage data and operational runbooks remain incomplete unless a node is specifically blue. Clarifications are listed in the final findings page and validation report.

### Related repository files

- `ARCHITECTURE.md`
- `BACKEND_INTEGRATION.md`
- `MODULE_STATUS.md`
- `FRONTEND_BACKEND_INTEGRATION_BASELINE.md`
- `src/app/router/index.ts`
- `src/shared/lib/apiClient.ts`
- `src/shared/contracts/apiContracts.ts`
- `src/modules/dashboards/DashboardStudioView.vue`
- `src/modules/dashboards/dashboards.service.ts`
- `src/modules/dashboards/delivery.service.ts`

## Page 7 - Report and Email Delivery Workflow

### Purpose

Report composition, export generation and controlled outbound delivery.

### Actors

Report Builder, Rendering & storage, Email composition, Delivery execution, Records.

### Preconditions

An authenticated or initiating actor has an organization/workspace context where applicable; route metadata, permissions, entitlements, tenant status and quotas are evaluated before protected work. Planned backend operations also require configured providers, durable storage and worker capacity.

### Trigger

The actor opens the relevant module, invokes an API, a schedule becomes due, or a domain event is published.

### Main workflow

- **Report Builder:** Create report -> Select dashboard or dataset -> Select template -> Configure pages + parameters -> Generate preview -> Validate data.
- **Rendering & storage:** Create export job -> Generate PDF -> Generate Excel -> Generate CSV -> Store export -> Secure download link.
- **Email composition:** Create email -> Select recipients -> Subject + message -> Attach report / add secure link -> Immediate or scheduled delivery.
- **Delivery execution:** Delivery queue -> Email provider -> Delivered -> Bounce -> Provider failure / timeout -> Retry with backoff.
- **Records:** Delivery history -> Audit log -> Recipient access event.

### Alternative flows

- Mock mode uses typed in-memory/localStorage adapters for review and testing.
- Live mode routes through the centralized API client when the endpoint family is activated.
- Cross-page subprocesses use the page references listed below instead of duplicating implementation detail.

### Failure flows

Validation, authentication, authorization, configuration, quota, provider, timeout, cancellation and partial-completion failures return a safe message and correlation ID. Retryable idempotent work follows bounded retry; exhausted asynchronous work is expected to enter a failed-job/DLQ path. See Page 14.

### Services involved

Report Builder, Rendering & storage, Email composition, Delivery execution, Records; centralized API client; relevant domain service adapters; planned orchestration/worker/provider services shown on the diagram.

### Databases involved

Current frontend localStorage-backed mock stores where implemented. Target state: PostgreSQL for transactional metadata, Redis for queue/cache/leases, and object storage for files/exports/intermediate data; these backend components are planned rather than repository-proven.

### Events generated

Domain create/update/publish/run/completion/failure events, progress updates, notification events, audit events and usage events as shown. Event infrastructure is planned unless explicitly surfaced by current mock behavior.

### Audit records generated

Actor, tenant, workspace, action, resource, outcome, timestamp and correlation ID; sensitive fields must be redacted. Current audit UI/data is mock-backed.

### Security controls

Session validation; organization/workspace scoping; RBAC; feature flags; entitlements; quota checks; safe errors; correlation IDs; secret redaction. Backend enforcement remains mandatory.

### Implementation status

Statuses represented: Implemented, Partially implemented, Planned, Validated successful outcome. Borders are evidence-based at repository commit `33a8356da18b5d74831f2a79b727a73779900f50`.

### Open gaps

Authoritative backend execution, storage, provider integration, production authorization, durable audit/usage data and operational runbooks remain incomplete unless a node is specifically blue. Clarifications are listed in the final findings page and validation report.

### Related repository files

- `ARCHITECTURE.md`
- `BACKEND_INTEGRATION.md`
- `MODULE_STATUS.md`
- `FRONTEND_BACKEND_INTEGRATION_BASELINE.md`
- `src/app/router/index.ts`
- `src/shared/lib/apiClient.ts`
- `src/shared/contracts/apiContracts.ts`
- `src/modules/reports/reports.service.ts`
- `src/modules/reports/ReportBuilderView.vue`
- `src/modules/reports/DeliveriesView.vue`

## Page 8 - Scheduler and Automation Workflow

### Purpose

Time-based and event-driven orchestration across VIP actions.

### Actors

Schedule authoring, Event triggers, Scheduler / automation engine, Worker, Outcomes.

### Preconditions

An authenticated or initiating actor has an organization/workspace context where applicable; route metadata, permissions, entitlements, tenant status and quotas are evaluated before protected work. Planned backend operations also require configured providers, durable storage and worker capacity.

### Trigger

The actor opens the relevant module, invokes an API, a schedule becomes due, or a domain event is published.

### Main workflow

- **Schedule authoring:** Create schedule -> Choose pipeline / dashboard / report / email / AI / automation -> Date, time, recurrence, timezone -> Dependencies + retry policy -> Failure handling + notifications -> Save and activate schedule.
- **Event triggers:** Dataset refresh completed -> Pipeline completed / failed -> File uploaded -> API event received -> Threshold reached -> Approval completed -> User action occurred.
- **Scheduler / automation engine:** Detect due execution / evaluate event -> Check tenant, entitlement, quota, permission -> Create idempotent execution job -> Queue job -> Track progress.
- **Worker:** Claim leased job -> Execute selected action -> Complete execution -> Retry failure -> Disable after repeated failures.
- **Outcomes:** Notify owner -> Audit execution -> Usage tracking -> Run history.

### Alternative flows

- Mock mode uses typed in-memory/localStorage adapters for review and testing.
- Live mode routes through the centralized API client when the endpoint family is activated.
- Cross-page subprocesses use the page references listed below instead of duplicating implementation detail.

### Failure flows

Validation, authentication, authorization, configuration, quota, provider, timeout, cancellation and partial-completion failures return a safe message and correlation ID. Retryable idempotent work follows bounded retry; exhausted asynchronous work is expected to enter a failed-job/DLQ path. See Page 14.

### Services involved

Schedule authoring, Event triggers, Scheduler / automation engine, Worker, Outcomes; centralized API client; relevant domain service adapters; planned orchestration/worker/provider services shown on the diagram.

### Databases involved

Current frontend localStorage-backed mock stores where implemented. Target state: PostgreSQL for transactional metadata, Redis for queue/cache/leases, and object storage for files/exports/intermediate data; these backend components are planned rather than repository-proven.

### Events generated

Domain create/update/publish/run/completion/failure events, progress updates, notification events, audit events and usage events as shown. Event infrastructure is planned unless explicitly surfaced by current mock behavior.

### Audit records generated

Actor, tenant, workspace, action, resource, outcome, timestamp and correlation ID; sensitive fields must be redacted. Current audit UI/data is mock-backed.

### Security controls

Session validation; organization/workspace scoping; RBAC; feature flags; entitlements; quota checks; safe errors; correlation IDs; secret redaction. Backend enforcement remains mandatory.

### Implementation status

Statuses represented: Partially implemented, Planned. Borders are evidence-based at repository commit `33a8356da18b5d74831f2a79b727a73779900f50`.

### Open gaps

Authoritative backend execution, storage, provider integration, production authorization, durable audit/usage data and operational runbooks remain incomplete unless a node is specifically blue. Clarifications are listed in the final findings page and validation report.

### Related repository files

- `ARCHITECTURE.md`
- `BACKEND_INTEGRATION.md`
- `MODULE_STATUS.md`
- `FRONTEND_BACKEND_INTEGRATION_BASELINE.md`
- `src/app/router/index.ts`
- `src/shared/lib/apiClient.ts`
- `src/shared/contracts/apiContracts.ts`
- `src/modules/automation/automation.service.ts`
- `src/modules/automation/AutomationBuilderView.vue`
- `src/modules/dashboards/delivery.service.ts`

## Page 9 - AI Studio and AI Agent Workflow

### Purpose

Permission-safe AI configuration, invocation, tool use and auditable outcomes without exposing chain-of-thought.

### Actors

AI Studio authoring, Invocation, Retrieval & execution, Safe trace & records, Failure controls.

### Preconditions

An authenticated or initiating actor has an organization/workspace context where applicable; route metadata, permissions, entitlements, tenant status and quotas are evaluated before protected work. Planned backend operations also require configured providers, durable storage and worker capacity.

### Trigger

The actor opens the relevant module, invokes an API, a schedule becomes due, or a domain event is published.

### Main workflow

- **AI Studio authoring:** Open AI Studio; create assistant / agent -> Select AI model -> Prompt + system instructions -> Approved datasets / semantic models / knowledge base -> Tools + APIs + workflow + memory -> Guardrails + permissions -> Test and validate output -> Publish agent.
- **Invocation:** Invoke from chat -> Invoke from dashboard -> Invoke from automation -> Invoke from API -> Check tenant / RBAC / AI quota.
- **Retrieval & execution:** Retrieve approved context references -> Safety / policy check -> Model request -> Execute approved tools -> Validate / ground outcome -> Produce answer.
- **Safe trace & records:** Safe execution trace: context refs, tool calls, decisions, status -> Store conversation -> Usage + token / cost metrics -> Audit event.
- **Failure controls:** Model timeout / provider unavailable -> Unavailable data -> Permission denial -> Unsafe request blocked -> Tool execution failure -> No private chain-of-thought retained or displayed.

### Alternative flows

- Mock mode uses typed in-memory/localStorage adapters for review and testing.
- Live mode routes through the centralized API client when the endpoint family is activated.
- Cross-page subprocesses use the page references listed below instead of duplicating implementation detail.

### Failure flows

Validation, authentication, authorization, configuration, quota, provider, timeout, cancellation and partial-completion failures return a safe message and correlation ID. Retryable idempotent work follows bounded retry; exhausted asynchronous work is expected to enter a failed-job/DLQ path. See Page 14.

### Services involved

AI Studio authoring, Invocation, Retrieval & execution, Safe trace & records, Failure controls; centralized API client; relevant domain service adapters; planned orchestration/worker/provider services shown on the diagram.

### Databases involved

Current frontend localStorage-backed mock stores where implemented. Target state: PostgreSQL for transactional metadata, Redis for queue/cache/leases, and object storage for files/exports/intermediate data; these backend components are planned rather than repository-proven.

### Events generated

Domain create/update/publish/run/completion/failure events, progress updates, notification events, audit events and usage events as shown. Event infrastructure is planned unless explicitly surfaced by current mock behavior.

### Audit records generated

Actor, tenant, workspace, action, resource, outcome, timestamp and correlation ID; sensitive fields must be redacted. Current audit UI/data is mock-backed.

### Security controls

Session validation; organization/workspace scoping; RBAC; feature flags; entitlements; quota checks; safe errors; correlation IDs; secret redaction. Backend enforcement remains mandatory.

### Implementation status

Statuses represented: Implemented, Partially implemented, Planned. Borders are evidence-based at repository commit `33a8356da18b5d74831f2a79b727a73779900f50`.

### Open gaps

Authoritative backend execution, storage, provider integration, production authorization, durable audit/usage data and operational runbooks remain incomplete unless a node is specifically blue. Clarifications are listed in the final findings page and validation report.

### Related repository files

- `ARCHITECTURE.md`
- `BACKEND_INTEGRATION.md`
- `MODULE_STATUS.md`
- `FRONTEND_BACKEND_INTEGRATION_BASELINE.md`
- `src/app/router/index.ts`
- `src/shared/lib/apiClient.ts`
- `src/shared/contracts/apiContracts.ts`
- `src/modules/ai/ai.service.ts`
- `src/modules/ai/AiStudioView.vue`
- `src/modules/ai/AgentRunsView.vue`

## Page 10 - Notifications and Activity Center Workflow

### Purpose

Rule-driven notification creation, channel delivery and user lifecycle.

### Actors

Event sources, Notification service, Channels, User lifecycle, Activity & audit.

### Preconditions

An authenticated or initiating actor has an organization/workspace context where applicable; route metadata, permissions, entitlements, tenant status and quotas are evaluated before protected work. Planned backend operations also require configured providers, durable storage and worker capacity.

### Trigger

The actor opens the relevant module, invokes an API, a schedule becomes due, or a domain event is published.

### Main workflow

- **Event sources:** Platform event generated -> Audit / security / job / delivery event.
- **Notification service:** Evaluate notification rules -> Resolve recipients -> Check user preferences -> Aggregate / deduplicate -> Create notification.
- **Channels:** In-app notification -> Email notification -> Push notification placeholder -> Retry failed delivery.
- **User lifecycle:** Unread / read state -> Mark as read -> Open related resource -> Archive -> Delete.
- **Activity & audit:** Activity feed -> Audit timeline -> Delivery outcome record.

### Alternative flows

- Mock mode uses typed in-memory/localStorage adapters for review and testing.
- Live mode routes through the centralized API client when the endpoint family is activated.
- Cross-page subprocesses use the page references listed below instead of duplicating implementation detail.

### Failure flows

Validation, authentication, authorization, configuration, quota, provider, timeout, cancellation and partial-completion failures return a safe message and correlation ID. Retryable idempotent work follows bounded retry; exhausted asynchronous work is expected to enter a failed-job/DLQ path. See Page 14.

### Services involved

Event sources, Notification service, Channels, User lifecycle, Activity & audit; centralized API client; relevant domain service adapters; planned orchestration/worker/provider services shown on the diagram.

### Databases involved

Current frontend localStorage-backed mock stores where implemented. Target state: PostgreSQL for transactional metadata, Redis for queue/cache/leases, and object storage for files/exports/intermediate data; these backend components are planned rather than repository-proven.

### Events generated

Domain create/update/publish/run/completion/failure events, progress updates, notification events, audit events and usage events as shown. Event infrastructure is planned unless explicitly surfaced by current mock behavior.

### Audit records generated

Actor, tenant, workspace, action, resource, outcome, timestamp and correlation ID; sensitive fields must be redacted. Current audit UI/data is mock-backed.

### Security controls

Session validation; organization/workspace scoping; RBAC; feature flags; entitlements; quota checks; safe errors; correlation IDs; secret redaction. Backend enforcement remains mandatory.

### Implementation status

Statuses represented: Partially implemented, Planned, Implemented. Borders are evidence-based at repository commit `33a8356da18b5d74831f2a79b727a73779900f50`.

### Open gaps

Authoritative backend execution, storage, provider integration, production authorization, durable audit/usage data and operational runbooks remain incomplete unless a node is specifically blue. Clarifications are listed in the final findings page and validation report.

### Related repository files

- `ARCHITECTURE.md`
- `BACKEND_INTEGRATION.md`
- `MODULE_STATUS.md`
- `FRONTEND_BACKEND_INTEGRATION_BASELINE.md`
- `src/app/router/index.ts`
- `src/shared/lib/apiClient.ts`
- `src/shared/contracts/apiContracts.ts`
- `src/modules/operations/operations.service.ts`
- `src/app/shell/NotificationDrawer.vue`

## Page 11 - Administration, Billing and Governance Workflow

### Purpose

Tenant administration, commercial lifecycle, quota governance and controlled deletion.

### Actors

Administrators, Identity & settings, Billing lifecycle, Governance, Support operations.

### Preconditions

An authenticated or initiating actor has an organization/workspace context where applicable; route metadata, permissions, entitlements, tenant status and quotas are evaluated before protected work. Planned backend operations also require configured providers, durable storage and worker capacity.

### Trigger

The actor opens the relevant module, invokes an API, a schedule becomes due, or a domain event is published.

### Main workflow

- **Administrators:** Platform administrator -> Tenant / organization administrator -> Workspace administrator -> Permission check.
- **Identity & settings:** Organization settings -> Workspace settings -> User + invitation management -> Role + permission management -> Security + compliance settings -> Feature flags.
- **Billing lifecycle:** Plans / trial / billing status -> Entitlements -> Usage, storage, execution, AI quotas -> Upgrade / downgrade -> Payment failure -> Grace period -> Suspend / reactivate.
- **Governance:** Audit log review -> Data retention policy -> Data export -> Tenant deletion request -> Approval / cooling period / dependency checks -> Purge confirmation.
- **Support operations:** Governed support access / impersonation -> Case actions + correlation ID -> Immutable audit record.

### Alternative flows

- Mock mode uses typed in-memory/localStorage adapters for review and testing.
- Live mode routes through the centralized API client when the endpoint family is activated.
- Cross-page subprocesses use the page references listed below instead of duplicating implementation detail.

### Failure flows

Validation, authentication, authorization, configuration, quota, provider, timeout, cancellation and partial-completion failures return a safe message and correlation ID. Retryable idempotent work follows bounded retry; exhausted asynchronous work is expected to enter a failed-job/DLQ path. See Page 14.

### Services involved

Administrators, Identity & settings, Billing lifecycle, Governance, Support operations; centralized API client; relevant domain service adapters; planned orchestration/worker/provider services shown on the diagram.

### Databases involved

Current frontend localStorage-backed mock stores where implemented. Target state: PostgreSQL for transactional metadata, Redis for queue/cache/leases, and object storage for files/exports/intermediate data; these backend components are planned rather than repository-proven.

### Events generated

Domain create/update/publish/run/completion/failure events, progress updates, notification events, audit events and usage events as shown. Event infrastructure is planned unless explicitly surfaced by current mock behavior.

### Audit records generated

Actor, tenant, workspace, action, resource, outcome, timestamp and correlation ID; sensitive fields must be redacted. Current audit UI/data is mock-backed.

### Security controls

Session validation; organization/workspace scoping; RBAC; feature flags; entitlements; quota checks; safe errors; correlation IDs; secret redaction. Backend enforcement remains mandatory.

### Implementation status

Statuses represented: Implemented, Partially implemented, Planned, Missing / blocked. Borders are evidence-based at repository commit `33a8356da18b5d74831f2a79b727a73779900f50`.

### Open gaps

Authoritative backend execution, storage, provider integration, production authorization, durable audit/usage data and operational runbooks remain incomplete unless a node is specifically blue. Clarifications are listed in the final findings page and validation report.

### Related repository files

- `ARCHITECTURE.md`
- `BACKEND_INTEGRATION.md`
- `MODULE_STATUS.md`
- `FRONTEND_BACKEND_INTEGRATION_BASELINE.md`
- `src/app/router/index.ts`
- `src/shared/lib/apiClient.ts`
- `src/shared/contracts/apiContracts.ts`
- `src/modules/admin/admin.service.ts`
- `src/modules/billing/billing.service.ts`
- `src/modules/admin/GovernanceView.vue`

## Page 12 - Backend Service Interaction Workflow

### Purpose

Expected target service interactions; not evidence of an implemented backend.

### Actors

Client & edge, Core services, Data services, Execution services, Infrastructure, External systems, Cross-cutting interaction semantics.

### Preconditions

An authenticated or initiating actor has an organization/workspace context where applicable; route metadata, permissions, entitlements, tenant status and quotas are evaluated before protected work. Planned backend operations also require configured providers, durable storage and worker capacity.

### Trigger

The actor opens the relevant module, invokes an API, a schedule becomes due, or a domain event is published.

### Main workflow

- **Client & edge:** Vue web frontend -> API gateway / FastAPI application -> Correlation ID + idempotency key -> WebSocket / SSE channel.
- **Core services:** Authentication service -> Organization + workspace service -> RBAC / entitlement / billing service -> Audit service.
- **Data services:** Connection service -> Pipeline service -> Dataset service -> Semantic model service -> Dashboard + report service.
- **Execution services:** Scheduler + automation service -> AI service -> Notification service -> Worker services.
- **Infrastructure:** PostgreSQL -> Redis queue / cache -> Object storage -> Storage service.
- **External systems:** External data sources -> Email provider -> AI model providers -> Observability stack.
- **Cross-cutting interaction semantics:** Synchronous REST request -> Asynchronous queue job -> Domain event publication -> Database / object write -> Retry + DLQ -> Audit event with tenant + actor + correlation ID.

### Alternative flows

- Mock mode uses typed in-memory/localStorage adapters for review and testing.
- Live mode routes through the centralized API client when the endpoint family is activated.
- Cross-page subprocesses use the page references listed below instead of duplicating implementation detail.

### Failure flows

Validation, authentication, authorization, configuration, quota, provider, timeout, cancellation and partial-completion failures return a safe message and correlation ID. Retryable idempotent work follows bounded retry; exhausted asynchronous work is expected to enter a failed-job/DLQ path. See Page 14.

### Services involved

Client & edge, Core services, Data services, Execution services, Infrastructure, External systems, Cross-cutting interaction semantics; centralized API client; relevant domain service adapters; planned orchestration/worker/provider services shown on the diagram.

### Databases involved

Current frontend localStorage-backed mock stores where implemented. Target state: PostgreSQL for transactional metadata, Redis for queue/cache/leases, and object storage for files/exports/intermediate data; these backend components are planned rather than repository-proven.

### Events generated

Domain create/update/publish/run/completion/failure events, progress updates, notification events, audit events and usage events as shown. Event infrastructure is planned unless explicitly surfaced by current mock behavior.

### Audit records generated

Actor, tenant, workspace, action, resource, outcome, timestamp and correlation ID; sensitive fields must be redacted. Current audit UI/data is mock-backed.

### Security controls

Session validation; organization/workspace scoping; RBAC; feature flags; entitlements; quota checks; safe errors; correlation IDs; secret redaction. Backend enforcement remains mandatory.

### Implementation status

Statuses represented: Implemented, Planned, Partially implemented. Borders are evidence-based at repository commit `33a8356da18b5d74831f2a79b727a73779900f50`.

### Open gaps

Authoritative backend execution, storage, provider integration, production authorization, durable audit/usage data and operational runbooks remain incomplete unless a node is specifically blue. Clarifications are listed in the final findings page and validation report.

### Related repository files

- `ARCHITECTURE.md`
- `BACKEND_INTEGRATION.md`
- `MODULE_STATUS.md`
- `FRONTEND_BACKEND_INTEGRATION_BASELINE.md`
- `src/app/router/index.ts`
- `src/shared/lib/apiClient.ts`
- `src/shared/contracts/apiContracts.ts`
- `src/shared/services/serviceFactory.ts`
- `.env.example`

## Page 13 - Data Lineage Workflow

### Purpose

End-to-end asset lineage, break detection and impact response.

### Actors

Lineage chain, Change signals, Impact analysis.

### Preconditions

An authenticated or initiating actor has an organization/workspace context where applicable; route metadata, permissions, entitlements, tenant status and quotas are evaluated before protected work. Planned backend operations also require configured providers, durable storage and worker capacity.

### Trigger

The actor opens the relevant module, invokes an API, a schedule becomes due, or a domain event is published.

### Main workflow

- **Lineage chain:** Source system -> Connection -> Ingestion job -> Pipeline -> Pipeline nodes / fields -> Dataset / columns -> Semantic model / measures -> Dashboard -> Visualization -> Report -> Email delivery -> AI agent -> Automation.
- **Change signals:** Source schema changes -> Connection delete request -> Pipeline field changes -> Dataset column removed -> Semantic measure changes -> Dashboard dependency breaks -> Scheduled report fails.
- **Impact analysis:** Traverse upstream + downstream graph -> Identify owners / schedules / consumers -> Block destructive change or require approval -> Notify impacted owners -> Repair mapping / republish / rerun -> Record lineage + audit outcome.

### Alternative flows

- Mock mode uses typed in-memory/localStorage adapters for review and testing.
- Live mode routes through the centralized API client when the endpoint family is activated.
- Cross-page subprocesses use the page references listed below instead of duplicating implementation detail.

### Failure flows

Validation, authentication, authorization, configuration, quota, provider, timeout, cancellation and partial-completion failures return a safe message and correlation ID. Retryable idempotent work follows bounded retry; exhausted asynchronous work is expected to enter a failed-job/DLQ path. See Page 14.

### Services involved

Lineage chain, Change signals, Impact analysis; centralized API client; relevant domain service adapters; planned orchestration/worker/provider services shown on the diagram.

### Databases involved

Current frontend localStorage-backed mock stores where implemented. Target state: PostgreSQL for transactional metadata, Redis for queue/cache/leases, and object storage for files/exports/intermediate data; these backend components are planned rather than repository-proven.

### Events generated

Domain create/update/publish/run/completion/failure events, progress updates, notification events, audit events and usage events as shown. Event infrastructure is planned unless explicitly surfaced by current mock behavior.

### Audit records generated

Actor, tenant, workspace, action, resource, outcome, timestamp and correlation ID; sensitive fields must be redacted. Current audit UI/data is mock-backed.

### Security controls

Session validation; organization/workspace scoping; RBAC; feature flags; entitlements; quota checks; safe errors; correlation IDs; secret redaction. Backend enforcement remains mandatory.

### Implementation status

Statuses represented: Planned, Partially implemented, Implemented. Borders are evidence-based at repository commit `33a8356da18b5d74831f2a79b727a73779900f50`.

### Open gaps

Authoritative backend execution, storage, provider integration, production authorization, durable audit/usage data and operational runbooks remain incomplete unless a node is specifically blue. Clarifications are listed in the final findings page and validation report.

### Related repository files

- `ARCHITECTURE.md`
- `BACKEND_INTEGRATION.md`
- `MODULE_STATUS.md`
- `FRONTEND_BACKEND_INTEGRATION_BASELINE.md`
- `src/app/router/index.ts`
- `src/shared/lib/apiClient.ts`
- `src/shared/contracts/apiContracts.ts`
- `src/modules/datasets/DataLineageView.vue`
- `src/modules/datasets/datasets.service.ts`

## Page 14 - Error Handling and Recovery Workflow

### Purpose

Standardized error normalization, retry, failed-job handling and recovery.

### Actors

Error sources, API boundary, Decision, Failed-job path, Recovery.

### Preconditions

An authenticated or initiating actor has an organization/workspace context where applicable; route metadata, permissions, entitlements, tenant status and quotas are evaluated before protected work. Planned backend operations also require configured providers, durable storage and worker capacity.

### Trigger

The actor opens the relevant module, invokes an API, a schedule becomes due, or a domain event is published.

### Main workflow

- **Error sources:** Validation / authentication / authorization / not found -> Conflict / rate limit / quota / subscription restriction -> Connector / pipeline node / worker / queue failure -> Database / storage failure -> AI / email provider / export failure -> Timeout / cancellation / partial completion.
- **API boundary:** Normalize error category -> Attach / echo correlation ID -> Safe error response -> User-facing actionable message -> Technical structured log.
- **Decision:** Retryable and idempotent? -> Retry with exponential backoff + jitter -> Resume from checkpoint / failed node -> Do not retry; request correction / authorization.
- **Failed-job path:** Retry budget exhausted -> Dead-letter / failed-job store -> Administrator / owner notification -> Audit error + recovery action.
- **Recovery:** Dependency restored / configuration fixed -> Revalidate current permission + quota -> Replay / resume execution -> Recovered outcome.

### Alternative flows

- Mock mode uses typed in-memory/localStorage adapters for review and testing.
- Live mode routes through the centralized API client when the endpoint family is activated.
- Cross-page subprocesses use the page references listed below instead of duplicating implementation detail.

### Failure flows

Validation, authentication, authorization, configuration, quota, provider, timeout, cancellation and partial-completion failures return a safe message and correlation ID. Retryable idempotent work follows bounded retry; exhausted asynchronous work is expected to enter a failed-job/DLQ path. See Page 14.

### Services involved

Error sources, API boundary, Decision, Failed-job path, Recovery; centralized API client; relevant domain service adapters; planned orchestration/worker/provider services shown on the diagram.

### Databases involved

Current frontend localStorage-backed mock stores where implemented. Target state: PostgreSQL for transactional metadata, Redis for queue/cache/leases, and object storage for files/exports/intermediate data; these backend components are planned rather than repository-proven.

### Events generated

Domain create/update/publish/run/completion/failure events, progress updates, notification events, audit events and usage events as shown. Event infrastructure is planned unless explicitly surfaced by current mock behavior.

### Audit records generated

Actor, tenant, workspace, action, resource, outcome, timestamp and correlation ID; sensitive fields must be redacted. Current audit UI/data is mock-backed.

### Security controls

Session validation; organization/workspace scoping; RBAC; feature flags; entitlements; quota checks; safe errors; correlation IDs; secret redaction. Backend enforcement remains mandatory.

### Implementation status

Statuses represented: Implemented, Partially implemented, Planned, Validated successful outcome. Borders are evidence-based at repository commit `33a8356da18b5d74831f2a79b727a73779900f50`.

### Open gaps

Authoritative backend execution, storage, provider integration, production authorization, durable audit/usage data and operational runbooks remain incomplete unless a node is specifically blue. Clarifications are listed in the final findings page and validation report.

### Related repository files

- `ARCHITECTURE.md`
- `BACKEND_INTEGRATION.md`
- `MODULE_STATUS.md`
- `FRONTEND_BACKEND_INTEGRATION_BASELINE.md`
- `src/app/router/index.ts`
- `src/shared/lib/apiClient.ts`
- `src/shared/contracts/apiContracts.ts`
- `src/shared/types/api.ts`
- `src/shared/lib/apiClient.contract.spec.ts`

## Page 15 - Audit, Monitoring and Observability Workflow

### Purpose

Evidence, telemetry and operational investigation across user and job activity.

### Actors

Sources, Context propagation, Records, Operations, Governance.

### Preconditions

An authenticated or initiating actor has an organization/workspace context where applicable; route metadata, permissions, entitlements, tenant status and quotas are evaluated before protected work. Planned backend operations also require configured providers, durable storage and worker capacity.

### Trigger

The actor opens the relevant module, invokes an API, a schedule becomes due, or a domain event is published.

### Main workflow

- **Sources:** User action -> API request -> Background / scheduled job -> Security event -> AI execution.
- **Context propagation:** Generate / accept correlation ID -> Tenant + workspace + actor context -> Trace / span context.
- **Records:** Structured application log -> Audit log -> Metrics -> Distributed traces -> Job + pipeline node logs -> Safe AI execution logs -> Usage + billing event.
- **Operations:** Alert rules -> Operations dashboard -> Incident notification -> Incident investigation -> Root cause analysis -> Remediation / runbook.
- **Governance:** Redaction / no secrets -> Access-controlled audit search -> Retention / archive / deletion policy.

### Alternative flows

- Mock mode uses typed in-memory/localStorage adapters for review and testing.
- Live mode routes through the centralized API client when the endpoint family is activated.
- Cross-page subprocesses use the page references listed below instead of duplicating implementation detail.

### Failure flows

Validation, authentication, authorization, configuration, quota, provider, timeout, cancellation and partial-completion failures return a safe message and correlation ID. Retryable idempotent work follows bounded retry; exhausted asynchronous work is expected to enter a failed-job/DLQ path. See Page 14.

### Services involved

Sources, Context propagation, Records, Operations, Governance; centralized API client; relevant domain service adapters; planned orchestration/worker/provider services shown on the diagram.

### Databases involved

Current frontend localStorage-backed mock stores where implemented. Target state: PostgreSQL for transactional metadata, Redis for queue/cache/leases, and object storage for files/exports/intermediate data; these backend components are planned rather than repository-proven.

### Events generated

Domain create/update/publish/run/completion/failure events, progress updates, notification events, audit events and usage events as shown. Event infrastructure is planned unless explicitly surfaced by current mock behavior.

### Audit records generated

Actor, tenant, workspace, action, resource, outcome, timestamp and correlation ID; sensitive fields must be redacted. Current audit UI/data is mock-backed.

### Security controls

Session validation; organization/workspace scoping; RBAC; feature flags; entitlements; quota checks; safe errors; correlation IDs; secret redaction. Backend enforcement remains mandatory.

### Implementation status

Statuses represented: Implemented, Partially implemented, Planned. Borders are evidence-based at repository commit `33a8356da18b5d74831f2a79b727a73779900f50`.

### Open gaps

Authoritative backend execution, storage, provider integration, production authorization, durable audit/usage data and operational runbooks remain incomplete unless a node is specifically blue. Clarifications are listed in the final findings page and validation report.

### Related repository files

- `ARCHITECTURE.md`
- `BACKEND_INTEGRATION.md`
- `MODULE_STATUS.md`
- `FRONTEND_BACKEND_INTEGRATION_BASELINE.md`
- `src/app/router/index.ts`
- `src/shared/lib/apiClient.ts`
- `src/shared/contracts/apiContracts.ts`
- `src/modules/operations/AuditCenterView.vue`
- `src/modules/operations/UsageView.vue`
- `src/modules/operations/operations.service.ts`

## Page 16 - Deployment and Runtime Workflow

### Purpose

Current frontend CI and target multi-environment deployment lifecycle.

### Actors

Local development, Pull request / CI, Build artifacts, Test environment, Staging, Production.

### Preconditions

An authenticated or initiating actor has an organization/workspace context where applicable; route metadata, permissions, entitlements, tenant status and quotas are evaluated before protected work. Planned backend operations also require configured providers, durable storage and worker capacity.

### Trigger

The actor opens the relevant module, invokes an API, a schedule becomes due, or a domain event is published.

### Main workflow

- **Local development:** Developer commit -> Vite local development / explicit mock mode -> Local typecheck, lint, test, build.
- **Pull request / CI:** Pull request -> npm ci -> Type checking + lint + format check -> Unit + contract tests -> Playwright + accessibility tests -> Dependency security audit -> Production frontend build.
- **Build artifacts:** Static frontend assets -> Container image -> Artifact / image registry.
- **Test environment:** Deploy test -> Integration tests against backend contracts -> Smoke test.
- **Staging:** Deploy staging -> Database migration -> Readiness + health checks -> End-to-end acceptance.
- **Production:** Progressive rollout -> Smoke / synthetic checks -> Monitor SLOs -> Rollback decision -> Rollback -> Stable release -> Incident handling.

### Alternative flows

- Mock mode uses typed in-memory/localStorage adapters for review and testing.
- Live mode routes through the centralized API client when the endpoint family is activated.
- Cross-page subprocesses use the page references listed below instead of duplicating implementation detail.

### Failure flows

Validation, authentication, authorization, configuration, quota, provider, timeout, cancellation and partial-completion failures return a safe message and correlation ID. Retryable idempotent work follows bounded retry; exhausted asynchronous work is expected to enter a failed-job/DLQ path. See Page 14.

### Services involved

Local development, Pull request / CI, Build artifacts, Test environment, Staging, Production; centralized API client; relevant domain service adapters; planned orchestration/worker/provider services shown on the diagram.

### Databases involved

Current frontend localStorage-backed mock stores where implemented. Target state: PostgreSQL for transactional metadata, Redis for queue/cache/leases, and object storage for files/exports/intermediate data; these backend components are planned rather than repository-proven.

### Events generated

Domain create/update/publish/run/completion/failure events, progress updates, notification events, audit events and usage events as shown. Event infrastructure is planned unless explicitly surfaced by current mock behavior.

### Audit records generated

Actor, tenant, workspace, action, resource, outcome, timestamp and correlation ID; sensitive fields must be redacted. Current audit UI/data is mock-backed.

### Security controls

Session validation; organization/workspace scoping; RBAC; feature flags; entitlements; quota checks; safe errors; correlation IDs; secret redaction. Backend enforcement remains mandatory.

### Implementation status

Statuses represented: Implemented, Planned, Validated successful outcome. Borders are evidence-based at repository commit `33a8356da18b5d74831f2a79b727a73779900f50`.

### Open gaps

Authoritative backend execution, storage, provider integration, production authorization, durable audit/usage data and operational runbooks remain incomplete unless a node is specifically blue. Clarifications are listed in the final findings page and validation report.

### Related repository files

- `ARCHITECTURE.md`
- `BACKEND_INTEGRATION.md`
- `MODULE_STATUS.md`
- `FRONTEND_BACKEND_INTEGRATION_BASELINE.md`
- `src/app/router/index.ts`
- `src/shared/lib/apiClient.ts`
- `src/shared/contracts/apiContracts.ts`
- `.github/workflows/quality-gate.yml`
- `package.json`
- `vite.config.ts`
- `playwright.config.ts`

## Glossary

| Term | Definition |
|---|---|
| API gateway | Edge entry point applying request context, routing and cross-cutting controls |
| Correlation ID | Identifier propagated through API, job, log, audit and provider interactions |
| Dataset | Governed tabular/data asset produced by ingestion or pipelines |
| DLQ | Dead-letter queue or failed-job store for exhausted asynchronous work |
| ELT / ETL | Load-then-transform / transform-then-load data processing patterns |
| Entitlement | Subscription-derived right to use a feature, possibly with a limit |
| Idempotency | Guarantee that replaying a request/job does not duplicate its effect |
| Lineage | Directed dependency graph from source fields through consumers and deliveries |
| RLS | Row-level security applied during data/semantic query execution |
| Semantic model | Business layer of dimensions, measures, relationships and policies |
| Tenant | VIP organization boundary |
| Workspace | Scoped collaboration and resource boundary within an organization |
| Safe execution trace | Auditable AI context/tool/policy/outcome metadata excluding private chain-of-thought |
