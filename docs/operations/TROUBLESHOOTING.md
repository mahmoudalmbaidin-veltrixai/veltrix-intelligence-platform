# Troubleshooting

## API is not ready

Check `docker compose ps`, API logs, `DATABASE_URL`, `REDIS_URL`, and dependency health. Confirm migrations reached the single Alembic head. Readiness errors should identify the failed dependency without exposing its connection value.

## Browser cannot authenticate

Confirm the frontend uses `VITE_API_MODE=live`, the API base URL is reachable, CORS/CSRF origins exactly match the browser origin, trusted hosts include the API host, and secure-cookie/domain/SameSite settings match HTTPS topology. Do not work around a cookie or CSRF error by enabling wildcards.

## Worker is stale

Confirm database/Redis connectivity, queue configuration, heartbeat timing, and whether a live lease owns long work. Restart only after determining duplicate-execution risk. Expired leases are recovered by supported worker logic.

## Pipeline or export remains queued

Verify the correct worker queue is enabled, storage is writable/shared, artifact limits are not exceeded, and the worker heartbeat is current. Inspect safe error codes and correlation IDs, then retry through the supported UI/API.

## Upload fails

Check size, extension/MIME allowlists, malware-scanner reachability, storage capacity/permissions, and tenant scope. Production must fail closed when scanning is unavailable.

## Email is not delivered

`disabled` sends nothing and `file` writes local `.eml` evidence. Real delivery requires `smtp`, a reachable provider, sender verification, correct TLS settings, and credentials supplied outside Git.

## Clean install differs from an existing laptop

Use a clean checkout, copy only `.env.example`, install from lock files, and start fresh volumes. If behavior depends on ignored files, local databases, generated credentials, or uncommitted fixtures, treat it as a reproducibility defect.
