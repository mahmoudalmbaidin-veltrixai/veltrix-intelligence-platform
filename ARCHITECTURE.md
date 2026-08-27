# VIP architecture

The current full-stack architecture is documented in:

- [Architecture overview](docs/architecture/OVERVIEW.md)
- [Deployment architecture](docs/architecture/DEPLOYMENT_ARCHITECTURE.md)
- [Repository guide](docs/architecture/VIP_REPOSITORY_GUIDE.md)
- [System workflow](docs/architecture/system-workflow/VIP_WORKFLOW_DOCUMENTATION.md)
- [Backend domain documents](docs/backend/)

The frontend is a Vue 3/TypeScript application under `src/`; the FastAPI/Python backend, Alembic migrations, generic job worker, pipeline worker, and backend tests are under `apps/api/`. PostgreSQL, Redis, shared persistent filesystem storage, malware scanning, and optional SMTP delivery are runtime dependencies.

Historical architecture and certification reports apply only to the revisions they name. Use the documents above and the current code/configuration when making deployment decisions.
