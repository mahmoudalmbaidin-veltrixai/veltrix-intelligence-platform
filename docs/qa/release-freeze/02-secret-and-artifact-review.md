# Secret and Artifact Review

## Scans

- The existing Playwright artifact sanitizer scanned `test-results/` and
  `playwright-report/` using all 38 locally encrypted QA persona passwords plus a
  release canary. It scanned 3 retained files, required no redactions, found no
  credential values, and passed.
- A repository-level pattern audit scanned 690 tracked and untracked source candidates.
  It found no private key, AWS key, GitHub token, generic API token, or reusable bearer
  credential.
- Fifteen review candidates were all non-production fixtures: generated/masked CI test
  credentials, a local CI PostgreSQL URL, deliberate invalid/test passwords, and the
  metrics unit-test token.

## Credential disposition

The QA seed generates passwords with a cryptographic RNG. Its credential manifest is
encrypted with Windows DPAPI and written only below ignored `artifacts/`. The recovery
helper accepts the password over standard input, revokes existing sessions, and is
restricted to the fixed QA bootstrap account. The local certification wrapper decrypts
the ignored fixture into process-scoped environment variables and does not write it to
the repository.

`vip_local_dev_only` and `vip_test` occur only in local/CI database configuration. They
are not production credentials. No value from `.env.local`, `.env.test`, the DPAPI
fixture, or the running services is included in committed reports.

## Artifact disposition

- Intentionally committed: sanitized, deterministic 20-widget CSV, JSON, PDF, PNG,
  hashes, and machine-readable QA reports under
  `docs/qa/final-certification-remediation/`.
- Excluded and ignored: `test-results/`, `playwright-report/`, raw traces, local QA
  credentials, `artifacts/`, `.env*` local files, database/storage volumes, backups,
  caches, and build output.
- The existing `.gitignore` is narrowly sufficient; no ignore rule was broadened and
  no source, test, or certification-document path is hidden.

Machine evidence is recorded in `artifact-secret-scan.json`,
`repository-secret-scan.json`, and `excluded-artifacts.json` in this directory.

