# Connections and secrets

Phase B4 provides tenant-owned connection metadata and write-only credentials for future platform
consumers. It does not execute ingestion or arbitrary queries.

## Security boundary

Every operation follows authentication, B2 tenant validation, B3 permission/feature/entitlement
enforcement, optional quota enforcement, a tenant-filtered repository, a secret provider, and a
persistent audit event. Connections are always scoped by organization and workspace.

Credentials must never be included in connection DTOs, logs, audit metadata, frontend stores,
client caches, or error responses. Secret resolution occurs server-side only after authentication,
tenant validation, permission enforcement, feature enforcement, and entitlement enforcement.

Safe configuration is stored in `connections.configuration`. Credential versions are separate,
immutable `connection_secrets` records. The database provider uses AES-256-GCM, a random 96-bit
nonce, and associated data containing organization, workspace, secret, provider, and credential
version. The master key comes from the server environment and is never stored in PostgreSQL.

Production startup rejects a missing key. Generate one without committing it:

```powershell
@'
import base64, secrets
print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())
'@ | python -
```

Supply `CONNECTION_ENCRYPTION_KEY` through the deployment secret manager and set
`CONNECTION_ENCRYPTION_KEY_VERSION`. `SecretProvider` and `EncryptionKeyProvider` are the future
Vault Transit, KMS, Azure Key Vault, and Google Cloud KMS integration boundaries. Provider access
must always revalidate tenant ownership.

## Catalog and schemas

```powershell
cd apps/api
python -m vip_api.cli seed-governance
python -m vip_api.cli seed-connection-types
```

PostgreSQL and REST API are enabled and securely testable. MySQL, MSSQL, Oracle, Snowflake,
BigQuery, Redshift, MongoDB, SFTP, and SMTP are deterministic disabled entries until vetted drivers
and testers are implemented. Strict Pydantic configuration and secret schemas reject unknown
fields and keep credential fields separate.

To add a connector, define its strict configuration and secret models in `catalog.py`, add a
versioned catalog definition, implement and register a restricted `ConnectionTester`, and add SSRF,
secret-disclosure, integration, and frontend tests.

## Connection testing and SSRF policy

Tests resolve credentials only after governance checks and use bounded timeouts. PostgreSQL runs
only fixed `SELECT 1`; REST sends a body-free `HEAD`. REST ignores environment proxies, verifies
TLS, limits redirects, and revalidates every redirect target.

File and unsupported schemes, loopback, link-local, multicast, unspecified, cloud metadata, and by
default private/reserved addresses are blocked. Private enterprise destinations require explicit
`CONNECTION_ALLOW_PRIVATE_NETWORKS=true`. Development HTTP requires
`CONNECTION_ALLOW_HTTP=true`. Use deployment egress controls when granting either exception.

Remote bodies, banners, raw driver errors, authorization headers, and credential-bearing URLs are
never returned or audited.

## Credential lifecycle

Create accepts safe `configuration` and write-only `credentials` separately. `PUT /credentials`
creates an encrypted version, atomically switches the active reference, revokes the old version,
resets health, and returns only configured/version state. `POST /credentials/rotate` is the explicit
rotation foundation. Transaction rollback preserves the current version if replacement fails.

Archived connections cannot be tested. Archiving does not release `connections.max` capacity in
B4, preserving conservative historical accounting until billing policy defines otherwise.

## Governance

All endpoints require the `connection_studio` feature and entitlement. Creation consumes
`connections.max` atomically. Stable permissions include `connection.read`, `connection.create`,
`connection.update`, `connection.delete`, `connection.archive`, `connection.test`,
`connection.credentials.update`, `connection.credentials.rotate`, `connection.health.read`, and
`connection.types.read`.

Admins have full access. Editors can read, create, update, and test but cannot manage credentials or
archive. Viewers can read safe metadata, health, and types. Restricted users have no connection
access. Frontend gates improve UX only; the backend remains authoritative.

## Development and troubleshooting

```powershell
docker compose up -d postgres redis
cd apps/api
alembic upgrade head
python -m vip_api.cli seed-governance
python -m vip_api.cli seed-connection-types
python scripts/backend_quality.py
```

`CONNECTION_DESTINATION_BLOCKED`, `CONNECTION_TIMEOUT`,
`CONNECTION_AUTHENTICATION_FAILED`, and `CONNECTION_HOST_UNREACHABLE` are sanitized outcomes.
For credential compromise, rotate the remote credential, submit a B4 rotation, review tenant audit
events, and revoke user sessions if account compromise is suspected.

Current limitations: no scheduled tests, discovery, preview, persistent connector pools, OAuth
ecosystem, SSH/VPN, automatic rotation, deployed Vault, customer-managed keys, or ingestion.
