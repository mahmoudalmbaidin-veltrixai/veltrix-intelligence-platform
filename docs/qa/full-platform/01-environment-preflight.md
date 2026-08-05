# Environment Preflight

| Item | Observed |
|---|---|
| Repository | `C:\Users\MahmoudAlmbaidin\Downloads\VIP` |
| Branch | `frontend/enterprise-ui-enhancement` |
| Starting SHA | `b6c85b313c29e161f5b1c23555e00f54b2352454` |
| Starting tree | Clean |
| Environment | Local development, live API mode; not production |
| Frontend | `http://localhost:3009` |
| API / docs | `http://localhost:8000` / `http://localhost:8000/docs` |
| Health / readiness | `/health` and `/ready`, HTTP 200 |
| PostgreSQL | localhost:5432, PostgreSQL 17 container; databases include `vip` and isolated `vip_test` |
| Redis | localhost:6379; persistent volume; DB 15 used for integration tests |
| Workers | dashboard and pipeline workers healthy |
| Malware scanner | ClamAV healthy |
| Optional MySQL | healthy on localhost:3307, database `vip_demo` |
| Node / npm / pnpm | v24.18.0 / 11.16.0 / 11.12.0 |
| Python / uv | 3.14.4 / 0.11.28 |
| Alembic | one code and database head: `20260803_0019` |
| OpenAPI | 192 paths, 247 operations |
| Browsers | Chromium and Firefox installed; WebKit unavailable |

Required browser variables are `VIP_E2E_EMAIL`, `VIP_E2E_PASSWORD`, `VIP_E2E_ORGANIZATION_NAME`, optional persona passwords, and `VIP_E2E_DESTINATION_CONNECTION_NAME`. Application variables come from local `.env` files and Compose. No external real credential was used; only synthetic local PostgreSQL/MySQL credentials were supplied transiently.

Docker Desktop stopped once during a long browser attempt and was restarted without recreating volumes. That interrupted attempt is excluded from product-pass totals.
