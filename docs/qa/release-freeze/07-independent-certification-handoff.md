# Independent Certification Handoff

## Candidate identity

- Repository: `C:\Users\MahmoudAlmbaidin\Downloads\VIP`
- Branch: `frontend/enterprise-ui-enhancement`
- Freeze base: `b6c85b313c29e161f5b1c23555e00f54b2352454`
- Candidate SHA: resolve the commit containing this file with `git rev-parse HEAD`;
  the exact immutable value is included in the final release-manager response.
- Push status: not pushed
- Pull request: not created

## Prerequisites

- Docker Desktop with the repository Compose services.
- Node.js 24, pnpm 11, Python 3.14, and installed Playwright browsers.
- API virtual environment from `apps/api/requirements.lock` / `uv.lock`.
- The documented idempotent QA seed or resume step.
- Process-scoped browser persona variables loaded by
  `tests/e2e/run-local-certification.ps1`; no secret value is stored here.
- Local integration `DATABASE_URL` and `REDIS_URL`; production secrets are not needed.

Exact gate commands, first-failure history, final totals, the final commit list, and the
clean-tree confirmation are added after the committed-state release gates finish.

