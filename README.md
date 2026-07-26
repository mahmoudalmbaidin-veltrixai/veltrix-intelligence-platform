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

## Architecture and local startup

VIP is a full-stack platform. The Vue/Vite frontend is at the repository root, while the FastAPI
backend is under `apps/api`. PostgreSQL stores platform data, Redis supports caching and background
work, workers process asynchronous jobs, and file storage is configured by the backend. Docker
Compose starts the backend services locally:

```bash
docker compose up --build
```

Install and run the frontend separately with the repository's npm lock file:

```bash
npm ci
npm run dev
```

Copy the documented keys from `.env.example` into an ignored local environment file and supply
environment-specific values. Never commit local environment files or credentials.

## Netlify frontend deployment

Netlify hosts only the Vue/Vite frontend. The repository-root configuration uses Node.js 22,
`npm run build`, and publishes `dist`; its SPA redirect sends direct application routes to
`index.html`. Netlify automatically installs dependencies from `package-lock.json` with npm.

The frontend reads its API endpoint from the public browser variable `VITE_API_BASE_URL`. Configure
it only when a publicly reachable HTTPS FastAPI deployment exists, together with the existing
`VITE_API_MODE=live` and appropriate `VITE_APP_ENV` setting. Variables prefixed with `VITE_` are
visible to browsers and must never contain database, Redis, SMTP, storage, signing, encryption,
session, or other backend secrets.

Netlify does not run FastAPI, PostgreSQL, Redis, workers, or backend file storage. Authentication
and live platform data require a separate public backend deployment with HTTPS, correct CORS and
CSRF origins, secure cookies, trusted hosts, PostgreSQL, Redis, workers, file storage, and backend
secrets. Do not proxy a Netlify production deployment to localhost.
