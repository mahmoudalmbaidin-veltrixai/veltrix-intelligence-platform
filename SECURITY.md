# Security policy

## Reporting a vulnerability

Do not open a public issue for a suspected vulnerability. Use the private security-reporting channel designated by the repository owner or organization administrator. No public security email address is currently published by this project.

Include the affected revision/component, reproduction conditions, impact, and a minimal proof of concept. Do not include live passwords, tokens, private keys, customer data, personal data, or destructive exploit steps. Preserve evidence privately.

This repository does not claim a formal public response SLA. Maintainers should acknowledge, triage, reproduce, contain, remediate, test, and communicate according to severity and contractual obligations.

## Repository practices

- Inject secrets at runtime from the hosting environment or a managed secret store.
- Keep local `.env` files, credential registers, dumps, exports, backups, and test artifacts out of Git.
- Use unique credentials and encryption/signing keys per environment.
- Rotate any real secret that was committed, even if it is later removed from the current tree.
- Enable GitHub secret scanning and push protection where the repository plan supports them.
- Run `python scripts/certification/repository-security-audit.py --scope all` before release and use an independent managed scanner in CI.
- Review dependency, container, and infrastructure scan findings; do not suppress them without a documented risk decision.

## Supported versions

Security fixes are applied to the current actively developed V1 branch/release line. Historical certification SHAs and archived evidence are not maintained releases unless explicitly designated by the repository owner.
