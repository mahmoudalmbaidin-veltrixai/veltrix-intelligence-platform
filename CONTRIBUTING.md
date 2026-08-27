# Contributing to VIP

VIP is currently a proprietary product repository. Contribution access does not grant a public license.

## Workflow

1. Create a short-lived branch from the team-designated integration branch. Use descriptive prefixes such as `feat/`, `fix/`, `docs/`, or `chore/`.
2. Keep changes scoped. Do not mix application behavior, infrastructure, generated evidence, and unrelated cleanup in one commit.
3. Install from `package-lock.json` and `apps/api/requirements.lock`; do not introduce a second package-manager lock.
4. Add or update tests for behavior and security boundaries.
5. Run the applicable gates in `docs/development/TESTING.md`.
6. Review `git status`, the staged diff, and the redacted repository security audit before committing.
7. Open a pull request that explains behavior, migration/deployment impact, tests, risks, and rollback.

## Code quality

- Frontend: TypeScript, ESLint, Prettier, Vue type checking, and Vitest.
- Backend: Python 3.12 compatibility, Ruff, mypy strict mode, Pytest, and Alembic checks.
- Infrastructure: formatted/validated Terraform and immutable container inputs.
- Security: preserve tenant scoping, API-side authorization, CSRF/session controls, secret redaction, and fail-closed production settings.

Never commit `.env` files, credentials, customer data, database dumps, generated exports, local access registers, or unsanitized browser/test artifacts. Use fake values under reserved example/test domains in tests and documentation.
