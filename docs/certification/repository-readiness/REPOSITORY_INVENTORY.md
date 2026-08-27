# Repository inventory and disposition

Audit baseline: branch `feat/vip-productization-p2`, starting SHA `c5aae4b560800c947f5e45e8912f85c60aa8e3cd` on 2026-08-27. This classification covers every major repository group; file-level exceptions are called out where material.

| Category | Path | Required in Git? | Public-safe? | Action |
| --- | --- | --- | --- | --- |
| Frontend source | `src/`, `public/`, root Vue/Vite/TypeScript configs | Yes | Yes after ordinary code review | COMMIT |
| Backend/API | `apps/api/src/`, `apps/api/pyproject.toml`, lock files | Yes | Yes after secret/security scan | COMMIT |
| Workers/scheduler | `apps/api/src/vip_api/jobs/`, `pipelines/`, dashboard scheduler code | Yes | Yes | COMMIT |
| Database/migrations | `apps/api/alembic/`, `alembic.ini`, SQLAlchemy models | Yes | Yes | COMMIT |
| Local orchestration | `docker-compose.yml`, Dockerfiles | Yes | Yes when labeled development-only | COMMIT |
| Infrastructure | `infra/aws/`, `infra/containers/`, `infra/postgres/` | Yes | Review account/domain values before public release | COMMIT |
| Automation | `.github/workflows/`, `Makefile`, `scripts/` | Yes | Yes after credential/output review | COMMIT |
| Unit/integration/E2E tests | `apps/api/tests/`, `src/**/*.spec.ts`, `tests/e2e/` | Yes | Use generated/fake credentials only | COMMIT |
| Public fixtures | `resources/sample-data/`, `demo-data/` | Yes when deterministic and synthetic | Yes after PII scan | COMMIT |
| Current docs | `docs/architecture/`, `deployment/`, `development/`, `operations/`, `product/`, `demo/`, `backend/` | Yes | Yes after link/content review | COMMIT |
| Historical reports | `docs/qa/`, `docs/reports/`, `docs/validation/`, `docs/certification/` | Selectively | May expose old paths, internal findings, or superseded claims | ARCHIVE / REVIEW MANUALLY |
| Selected historical raw evidence formerly at repository root | local `artifacts/private/legacy-tracked-evidence/` | No | No public need | LOCAL ONLY; remove from current Git tree |
| Root business workbooks formerly tracked | local `artifacts/private/workbooks/` | No | Internal commercial material | LOCAL ONLY; remove from current Git tree |
| Credential/access-register workbooks | local `artifacts/private/workbooks/` | Never | No | LOCAL ONLY; ignored; do not publish |
| Presentation deck | local `artifacts/private/decks/` | No | Manual business review required | ARCHIVE / LOCAL ONLY |
| Local editor/agent config | `.claude/`, `.agents/`, `.codex-runtime/` | No | Machine/user-specific | IGNORE |
| Local environment | `.env`, `.env.*` except examples | No | May contain secrets | IGNORE / LOCAL ONLY |
| Dependencies/build/cache | `node_modules/`, `dist/`, virtualenvs, tool caches | No | Generated | IGNORE |
| Runtime data | uploads, storage, exports, backups, dumps, logs, PID/temp files | No | May contain customer data/secrets | IGNORE / LOCAL ONLY |
| Browser/test output | `playwright-report/`, `test-results/`, coverage, local evidence | No by default | May contain credentials/PII | IGNORE; sanitize before exceptional archive |
| Generated demo credentials | operating-system protected stores outside Git | Never | No | LOCAL ONLY |

## Notes

- The repository uses npm; local pnpm lock/workspace files were archived outside Git.
- Alembic migrations, source fixtures, intentional sample data, and safe `.env.example` files remain tracked.
- Removing a file from the current tree does not remove it from Git history. Public release therefore requires the separate history and business/legal review in `PUBLIC_VISIBILITY.md`.
