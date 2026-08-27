# VIP First Customer Go-Live Checklist

**Purpose:** Testable evidence required before putting a **paying** customer on a **production** VIP environment.  
**This is not a demo checklist.**  
**Audit SHA (application tree):** `dfb74af3ea4e44491fbee946a44e0e5e0e984bbf`  
**Status as of 23 August 2026:** **NOT COMPLETE.** Docker was not running. No live AWS environment was verified. Email is file/disabled. Legal pack is absent.

Every item needs **owner, date, evidence link**. Unchecked = not proven.

---

## Domain

- [ ] Production domain registered and owned by the company (not a personal unused domain)
- [ ] `app.<domain>` and `api.<domain>` documented
- [ ] `staging.` hostnames documented
- [ ] Sending domain documented (`mail.<domain>` or apex)
- [ ] No `localhost` or `*.local` in customer-facing URLs

**Test:** `nslookup app.<domain>` returns the intended nameservers.

## DNS

- [ ] Cloudflare (or Route 53) is authoritative
- [ ] SPF / DKIM / DMARC published for the sending domain
- [ ] TTL and cutover notes stored
- [ ] Staging records exist and do not collide with production

**Test:** `dig TXT <sending-domain>` shows SPF; DKIM CNAMEs resolve.

## TLS

- [ ] HTTPS on app and API
- [ ] HTTP redirects to HTTPS
- [ ] TLS 1.2+ only
- [ ] Mode is Full Strict if Cloudflare-proxied (never Flexible)
- [ ] Production `AUTH_COOKIE_SECURE=true` (Settings already fail-closed)

**Test:** Browser padlock; `curl -I http://api.<domain>/health` redirects.

## Application

- [ ] Build is a **tagged SHA**, not a dirty laptop tree
- [ ] `/api/v1/version` reports that SHA (not `null`) and a commercial version (not `0.1.0`)
- [ ] `VITE_API_MODE=live`, `VITE_ENABLE_DEVTOOLS=false`
- [ ] Gated modules 404 in production (Reports/AI/Automation/Billing/Marketplace)
- [ ] Favorites and dashboard templates not in nav
- [ ] Login does not advertise unimplemented AI/Automation (current HEAD splash is honest — re-check)
- [ ] Alembic head applied; single head
- [ ] Feature flags match the signed capability schedule

**Test:** Authenticated smoke: login → org/workspace → CSV upload → dataset → pipeline run → semantic query → dashboard publish → PDF → PNG → logout.

## Database

- [ ] Managed PostgreSQL (RDS), private subnet, TLS
- [ ] Encryption at rest
- [ ] Automated backups + PITR enabled
- [ ] Connection limits and pooling documented
- [ ] Migrations run as a one-off task, not by a random API replica
- [ ] Restore tested on a **throwaway** instance (local Docker dump is **not** enough)

**Test:** Restore snapshot/PITR into a new instance; API `/ready` 200 against it.

## Redis

- [ ] Managed Redis with TLS + AUTH
- [ ] Persistence/eviction policy documented (jobs vs cache)
- [ ] Failover owner named
- [ ] Login rate-limit behavior if Redis is down **documented and accepted** (today: fail-open — fix before prod)

**Test:** Stop Redis in staging: API degrades **predictably**; no silent auth bypass.

## Workers

- [ ] Dashboard-worker and pipeline-worker running
- [ ] Healthchecks passing
- [ ] `FILE_MALWARE_SCANNER` is **not** `noop`
- [ ] Concurrency sized for 1–5 customers
- [ ] Failed jobs visible in UI/logs

**Test:** Kill a worker; job retries or surfaces failure; alert fires.

## Scheduler

- [ ] Singleton (`desired_count = 1`) or proven SKIP LOCKED with no duplicate fires
- [ ] Timezone case (e.g. Asia/Riyadh) proven
- [ ] Disable schedule works
- [ ] Restart does not double-send

**Test:** 24h staging soak; one scheduled delivery; count = 1.

## Storage

- [ ] Durable volume (EFS) or equivalent — not a disposable container FS
- [ ] Uploads, exports, pipeline artifacts survive task replacement
- [ ] Retention/cleanup jobs understood (`DASHBOARD_EXPORT_RETENTION_HOURS`, pipeline artifact TTL)
- [ ] Backup includes the volume

**Test:** Upload CSV, replace API task, preview still works.

## Email

- [ ] `DASHBOARD_EMAIL_PROVIDER=smtp` (production validator)
- [ ] Resend or SES SMTP credentials in Secrets Manager
- [ ] Password reset received in an **external** mailbox
- [ ] Password changed notification received
- [ ] Invitation received and accepted
- [ ] Dashboard email delivery received (if sold)
- [ ] Bounce/complaint handling owner named
- [ ] From address on a verified domain (not `@vip.local`)

**Test:** Three real mailboxes (Gmail, Outlook, customer domain).

## Secrets

- [ ] No Compose dummy `CONNECTION_ENCRYPTION_KEY` / signing keys
- [ ] JWT/session secrets rotated from examples
- [ ] SMTP secret in SM
- [ ] `.env` not on the server disk in plaintext beyond platform injection
- [ ] Git history scan clean on the **release tree**

**Test:** `gitleaks` / Trivy secret scan on tag; task definition has no plaintext passwords.

## Monitoring

- [ ] Uptime probe on `/health` and `/login`
- [ ] Sentry (or equivalent) for API + frontend
- [ ] CloudWatch (or host) log groups
- [ ] Alerts: 5xx, RDS storage, Redis, worker restarts, certificate expiry
- [ ] On-call: **named human** with phone

**Test:** Force 500; alert within 5 minutes.

## Backups

- [ ] RDS backup window set
- [ ] EFS/object backup set
- [ ] Retention ≥ 7 days (recommend 14–35)
- [ ] Encryption documented
- [ ] Restore test dated in last 30 days
- [ ] RPO/RTO **targets** written internally (do not print as SLA until tested)

**Test:** Restore drill ticket with screenshots/logs.

## Security

- [ ] CORS allowlist = production app origin only
- [ ] CSRF trusted origins match
- [ ] `TRUSTED_HOSTS` explicit
- [ ] WAF attached (AWS WAF and/or Cloudflare)
- [ ] Rate limits on login and password reset
- [ ] Cross-tenant test on **staging**: org A cannot read org B IDs (expect 404)
- [ ] Viewer cannot publish/edit/admin
- [ ] Platform admin boundary tested
- [ ] ClamAV (or approved scanner) on uploads
- [ ] Security headers on HTTPS responses

**Test:** Scripted IDOR suite + one viewer session.

## Customer onboarding

- [ ] Contract/SOW signed with V1 limitations
- [ ] Organization created
- [ ] Admin user invited **or** operator-provisioned with forced password change
- [ ] Workspace created
- [ ] First connection tested
- [ ] Sample dataset validated by customer
- [ ] UAT sign-off email stored
- [ ] Support contact exchanged

**Test:** Customer admin completes login without a screenshare **or** documented assisted onboarding.

## Documentation

- [ ] Runbook: restart workers, scheduler, email, restore
- [ ] Env var inventory matches runtime
- [ ] Architecture diagram matches **deployed** (not only Terraform)
- [ ] Known limitations page given to customer

**Test:** A second engineer follows the runbook to restart the worker.

## Support

- [ ] Inbox/phone
- [ ] Severity definitions
- [ ] Hours of coverage (founders: 5×8 is honest; 24×7 is not, unless staffed)
- [ ] Language (AR/EN) stated

**Test:** Send a dummy P2; response within promised window.

## Commercial

- [ ] Invoice / PO path
- [ ] Pilot vs production conversion terms
- [ ] Data processing addendum
- [ ] Subprocessors listed
- [ ] No 99.9% SLA unless ops can keep it

## Compliance

- [ ] Residency (Bahrain vs KSA) accepted in writing
- [ ] PDPL/privacy counsel review **or** explicit “legal pending — pilot only”
- [ ] Deletion/export procedure exists
- [ ] Incident notification contact

---

## Demo-only conditions (not go-live)

These may be true for a **scripted demo** and still **fail** go-live:

- Local Compose with `DASHBOARD_EMAIL_PROVIDER=file`
- `AUTH_COOKIE_SECURE=false`
- Dummy encryption keys
- Operator-created users, no invitation email
- Docker on a founder laptop
- Version `0.1.0`

Do not confuse a good demo with production.
