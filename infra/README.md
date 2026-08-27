# Infrastructure

Infrastructure code is separated from application source:

- `containers/web/` builds and configures the production static frontend image;
- `postgres/` contains the hardened PostgreSQL image used by local Compose;
- `aws/` contains the existing Terraform implementation and deployment/rollback/smoke scripts.

The provider-neutral service contract is documented in `docs/deployment/PRODUCTION_DEPLOYMENT.md`. Do not create parallel infrastructure stacks without first deciding which implementation is authoritative.

Local `docker-compose.yml` is a development environment, not a production deployment definition.
