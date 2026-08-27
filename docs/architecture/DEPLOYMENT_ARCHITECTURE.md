# Deployment architecture

VIP can run on any platform that satisfies the service contract below. The included AWS Terraform is one implementation; it does not make the application dependent on AWS APIs.

| Dependency | Configuration contract | Production requirement | Current status |
| --- | --- | --- | --- |
| Frontend | Build-time `VITE_*`; static container on port 8080 | HTTPS origin and API URL | Production Dockerfile present |
| API | Environment variables; container port 8000 | Multiple replicas as load permits; `/ready` gate | Production-capable image present |
| PostgreSQL | `DATABASE_URL` | Managed or HA service, TLS, backups, private networking | Required and validated at startup |
| Redis | `REDIS_URL` | TLS/auth, no-eviction policy, private networking | Required and validated at startup |
| Job worker | Same DB/Redis/secrets/storage as API | At least one healthy replica | Implemented |
| Pipeline worker | Same DB/Redis/secrets/storage as API | At least one healthy replica | Implemented |
| Scheduler role | Scheduler flags and singleton deployment policy | Exactly one logical scheduler role | Implemented through generic worker ticks |
| Storage | `FILE_STORAGE_ROOT`, dashboard/pipeline artifact roots | Shared persistent filesystem, encryption, backup | Filesystem provider implemented |
| Email | `DASHBOARD_EMAIL_*` | SMTP provider, verified sender, bounce handling | Optional outside production; required by production validator |
| Malware scanning | `FILE_MALWARE_SCANNER`, ClamAV/Defender settings | Reachable fail-closed scanner | ClamAV and Defender adapters present |
| Domain and TLS | frontend/API URLs, CORS, CSRF, hosts, cookie domain | Public DNS, trusted certificate, HTTPS-only cookies | Hosting supplied |
| Secrets | environment/secret injection | Managed secret store and rotation | Contract present; values not in Git |

## Network boundaries

- Expose only the TLS load balancer/reverse proxy.
- Keep PostgreSQL, Redis, workers, scheduler, storage, and malware scanning on private networks.
- Allow the browser origin through explicit CORS and CSRF origin lists.
- Set `TRUSTED_HOSTS` explicitly and enable secure cookies in production.
- Restrict connector egress and keep private-network connection testing disabled unless an approved private-source use case requires it.

## Scaling

The frontend and API are stateless relative to PostgreSQL, Redis, and storage and can scale horizontally. Job and pipeline workers use leases and may scale horizontally. Schedule tick logic is concurrency-safe, but production should keep one logical scheduler role to simplify operations. All replicas that create or consume artifacts must mount the same persistent roots.

## Provider mapping

AWS is mapped in `infra/aws/`. Azure, GCP, Railway, Render, DigitalOcean, private cloud, and client infrastructure can host VIP if they provide equivalent containers, PostgreSQL, Redis, persistent filesystem storage, secret injection, private networking, TLS, backups, and monitoring. No provider other than the static AWS definition has been tested by this repository certification.
