# VIP — Veltrix Intelligence Platform

VIP is a Vue 3 frontend with a FastAPI platform backend. The frontend remains at the repository
root; the API lives under `apps/api`. Phase B3 adds database-backed scoped roles and permissions,
feature flags, contractual entitlements, atomic quotas, persistent audit events, and a real
frontend governance bootstrap on top of B1/B2 identity and tenancy. Phase B4 adds live,
tenant-owned connections with write-only encrypted credentials and secure testing. Phase B5 adds
live dataset catalog, metadata discovery, quality, lineage, semantic models, glossary, and bounded
read-only semantic querying. B6 adds persistent Dashboard Studio, exports, delivery, and tenant-safe
caching. B7 adds persistent Pipeline Studio, immutable versions, durable asynchronous runs, and
protected results.

Phase B5 dataset catalog and semantic-layer development is documented in
[`docs/backend/DATASETS_AND_SEMANTIC_LAYER.md`](docs/backend/DATASETS_AND_SEMANTIC_LAYER.md).
Pipeline authoring, execution, security, and operations are documented in
[`docs/backend/PIPELINE_BACKEND.md`](docs/backend/PIPELINE_BACKEND.md).

Local port 3009 uses live FastAPI/PostgreSQL APIs for the completed B0-B7 platform workflows.
Product domains scheduled for later phases may still use demonstration adapters.

## Applications

- Frontend: see [ARCHITECTURE.md](ARCHITECTURE.md), run with `npm run dev` on port 3009.
- Backend: see [apps/api/README.md](apps/api/README.md), run with Docker Compose or Python 3.12.
- Governance: see [docs/backend/GOVERNANCE.md](docs/backend/GOVERNANCE.md).

Start the complete backend development stack from the repository root:

```bash
docker compose up --build
```

Operational endpoints are then available at `http://localhost:8000/health`, `/ready`, and
`/api/v1/version`.

Create a local account with `python -m vip_api.cli create-user` from `apps/api`, then run the
frontend with `npm run dev` and sign in at `http://localhost:3009/login`. See the backend README for
cookie, CSRF, tenancy, migration, testing, and environment details.
