# Manual UAT Guide

Keep Docker Desktop and the Vite process running. Open `http://localhost:3009`; API docs are at `http://localhost:8000/docs`, health at `http://localhost:8000/health`, and readiness at `http://localhost:8000/ready`.

Use organization `QA_Enterprise_A_20260804`, Default workspace for most positive scenarios, `QA_Restricted` for restricted paths, and `QA_Enterprise_B_20260804` for cross-tenant attempts. Persona usernames are listed in `qa-users.json`.

Retrieve a password locally (never commit or paste the full output):

```powershell
& .\apps\api\scripts\show-full-platform-qa-credentials.ps1
```

Recommended workflow:

1. Sign in as `qa_platform_super_admin`; verify platform console and switch into QA A.
2. Sign in as `qa_organization_admin`; review members, roles, groups, ACLs, audit, and QA connections.
3. Test `QA_PostgreSQL_Valid` and `QA_MySQL_Valid`; confirm secrets remain masked. Test invalid/unreachable cases only locally.
4. Build a QA-prefixed CSV dataset/pipeline, validate, publish, run, inspect logs/results/profile, and retain it if needed.
5. Build a QA-prefixed dashboard; save, reload, publish, share, and compare viewer/editor/manager personas. Watch for the Firefox first-save flake.
6. Verify suspended login fails. Use cross-tenant attacker in QA B and attempt QA A UUIDs through UI and docs; expect fail-closed 403/404.
7. Exercise direct/group ACL, deny, and expired personas against the same immutable resource.
8. Do not treat placeholder modules or XLSX upload as passing features.

Known limitations are enumerated in `14-defect-register.md`. The environment is for review, not production.
