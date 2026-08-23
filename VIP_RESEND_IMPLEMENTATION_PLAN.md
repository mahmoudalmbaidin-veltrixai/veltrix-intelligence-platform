# Resend Implementation Plan

**Audit date:** 23 August 2026  
**Current email state:** locally simulated (`file` outbox) or `disabled`. Production Settings require `smtp`. No Resend SDK exists. SES is designed in Terraform and **not applied**.  
**Invitation email:** not implemented.  
**Password-reset email:** composed and sent through the shared provider; locally writes `.eml`.

---

## Recommendation

| Phase | Provider | Why |
| --- | --- | --- |
| **Do now (P0/P1)** | **Resend via SMTP** | Hours, not weeks. Fits the existing `SmtpEmailProvider`. Unblocks password reset and invitations before AWS SES is live. |
| **Before production on AWS** | Keep Resend **or** switch to **AWS SES SMTP** (`eu-central-1`) as already designed in `infra/aws/email.tf` | SES is the GCC/AWS-aligned production path; Bahrain has no SES SMTP endpoint. |
| **Do not** | Rewrite the app around the Resend HTTP API as the only transport | The app already has `EmailProvider` + SMTP. Prefer SMTP first. |

**Resend is appropriate for early VIP production** if AWS SES is not yet verified. It is a US/EU processor — disclose it in the DPA/subprocessor list. For a Saudi ministry/SOE that forbids extra processors, wait for SES and get written approval for Frankfurt email.

### Resend vs AWS SES (brief)

| | Resend | AWS SES |
| --- | --- | --- |
| Time to first email | Hours (DNS + API key) | Days (account, domain, sandbox exit, IAM SMTP user) |
| Fit with current code | SMTP drop-in | SMTP drop-in (already in Terraform) |
| GCC story | Extra subprocessor | Same AWS relationship; still cross-region (`eu-central-1`) |
| Cost class | Very low | Low |
| Deliverability tooling | Excellent dashboard | Adequate; more IAM ceremony |
| V1 recommendation | **Use now** | **Target once AWS email.tf is applied** |

Build `EmailProvider -> SmtpEmailProvider` now. Optionally add `ResendHttpProvider` later. Do **not** couple business code to Resend.

---

## Current code (do not rewrite)

Shared factory: `apps/api/src/vip_api/dashboard_delivery/email.py`

- `FileEmailProvider` — local `.eml`  
- `SmtpEmailProvider` — STARTTLS/TLS SMTP  
- `get_email_provider()` — `file` | `smtp` | else 503  

Password reset: `apps/api/src/vip_api/auth/email.py` → `send_password_reset_email` (swallows transport errors so the API stays non-disclosing).

Invitations: `create_invitation` in `apps/api/src/vip_api/tenancy/services.py` **does not send email**. Raw token is returned only when `APP_ENV` is `development` or `test`. `INVITATION_ACCEPT_URL` is configured and **unread by application code**.

Frontend: `/forgot-password`, `/reset-password` exist. **No `/invitations/accept` route.** Accept API requires an **already logged-in** user whose email matches. There is **no public signup**. Operator path: `platform_admin.create_user` (default `must_change_password=true`).

---

## V1 scope (build this)

### In scope

1. Sending domain DNS: SPF, DKIM, DMARC.  
2. Secrets: `RESEND_API_KEY` or SMTP username/password in the secret store — never git.  
3. Set `DASHBOARD_EMAIL_PROVIDER=smtp` against `smtp.resend.com:587` STARTTLS.  
4. Templates (simple HTML, no marketing platform):  
   - Password reset (exists — restyle only)  
   - Password changed (new)  
   - User invitation (new — this is the real gap)  
   - Optional: account security / lockout notice  
   - Optional: critical pipeline/export failure for org admins  
5. Invitation accept **page** + decide V1 join model (see below).  
6. Idempotency: one token per invitation; one-time password-reset tokens (already).  
7. Logs: message id, provider, tenant id, template name — **no** raw tokens, **no** full recipient lists in debug.  
8. Fail closed in production if SMTP is not configured (already). Locally keep `file` for QA.

### Out of scope (do not build yet)

- Per-tenant custom From-name / white-label  
- In-app notification emails for every job event  
- Marketing / newsletters  
- Resend Audiences / Broadcasts  
- Complex webhook-driven CRM  
- Multi-provider failover  
- Localization of every template  
- “Trial expired” mail until billing exists  

---

## V1 invitation join model (required product decision)

**Problem:** Accept requires a logged-in user with the same email. New customers cannot join from a link alone.

**Recommended V1 (lowest complexity):**

1. Platform operator **or** org admin creates the invitation.  
2. Email contains a link to `/invitations/accept?token=...`.  
3. If the user has no account: the accept page collects **password + display name**, creates the user **only** for that exact invited email, then accepts the invitation in one transaction.  
4. If the user exists: require login, then accept.

Do **not** open global public registration.

**Until that ships:** founder creates the user in Platform Admin, sets a temporary password with `must_change_password`, and sends credentials out of band. That is **pilot-acceptable** and **not** production-SaaS-acceptable.

---

## DNS / identities

Recommended:

```text
app.example.com          application
api.example.com          API
www.example.com          marketing (later)
notify.example.com       optional; not required if using the apex sending domain
mail.example.com         not required for Resend
```

Resend sending domain: `example.com` or `mail.example.com`.

Sender identities for V1:

| From | Use |
| --- | --- |
| `no-reply@mail.example.com` | password reset, invites, security |
| `alerts@mail.example.com` | optional operational failure (can wait) |

Do not use `vip.local`. Do not send from a personal Gmail.

Records (Resend dashboard will give exact values):

- SPF: `v=spf1 include:_spf.resend.com ~all` (or Resend’s current include)  
- DKIM: CNAME records Resend provides  
- DMARC: `v=DMARC1; p=quarantine; rua=mailto:dmarc@example.com` (start with `p=none` for a week, then quarantine)

---

## Send path: sync vs worker

| Mail | Recommendation |
| --- | --- |
| Password reset | **Synchronous from API** is acceptable (already). Keep timeout bounded. Do **not** put the token in the API JSON. |
| Invitation | Prefer **enqueue a job** so invite API stays fast; V1 may send sync if volume is tiny. |
| Dashboard delivery | **Already worker/scheduler** — keep it. |
| Password changed | Sync or job; V1 sync is fine. |

Do not introduce a second queue product. Use the existing Redis job worker.

---

## Webhooks, bounces, retries

**V1 minimum:**

- Resend dashboard watched by the operator.  
- Application retries: SMTP provider already raises `DASHBOARD_EMAIL_FAILED`; dashboard delivery already has max attempts. Password-reset swallows errors (correct for anti-enumeration) — **log a metric/warning** (already).  
- Bounce handling: **manual** in week 1.  

**Before production:**

- Resend webhook → API endpoint verifying Svix/Resend signature → store delivery status on invitation/reset attempts.  
- Do not auto-delete users on bounce.  
- Idempotency key: `delivery_id` UUID (already passed into `send`).

---

## Tenant branding policy (V1)

All mail is **Veltrix / VIP** branded. No customer logo, no custom SMTP, no “send as customer domain”. Revisit after 3–5 customers.

---

## Secrets

| Secret | Store |
| --- | --- |
| Resend API key / SMTP password | AWS Secrets Manager or platform env — **never** `.env` in git |
| From address | config, not secret |

Production Settings already require SMTP host + paired username/password.

---

## Acceptance tests

1. Request password reset for a real mailbox → mail arrives < 2 minutes → link works once → second use fails → all sessions revoked.  
2. Invite a **new** email → mail arrives → accept page creates account → user lands in the correct org/workspace with the assigned role.  
3. Invite an existing user → login + accept works; wrong account gets 403.  
4. Cross-tenant cannot accept another org’s token.  
5. `APP_ENV=production` with `DASHBOARD_EMAIL_PROVIDER=file` **refuses to start**.  
6. Resend dashboard shows delivered, not only “accepted” API 202.  
7. Token never appears in API logs or JSON in production.

---

## Effort

| Work | Effort | Owner |
| --- | --- | --- |
| DNS + Resend domain | S | Founder / DevOps |
| SMTP env against Resend | XS | DevOps |
| Invitation email send | S | Backend |
| Accept page + optional user create | M | Frontend + backend |
| Password-changed mail | S | Backend |
| Webhooks | S | Backend |
| Templates polish | S | Product |

**Dependency:** domain owned. Invitation accept UI is a **pilot blocker** for self-serve; operator provisioning can cover a single paid pilot.
