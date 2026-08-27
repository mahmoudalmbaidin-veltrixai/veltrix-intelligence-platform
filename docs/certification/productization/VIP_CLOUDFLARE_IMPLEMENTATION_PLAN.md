# Cloudflare Implementation Plan

**Audit date:** 23 August 2026  
**Current state:** No Cloudflare (or any live DNS) configuration exists in the repository. Terraform expects Route 53 (`hosted_zone_id` in `infra/aws/terraform.tfvars.example` is a placeholder). Domain is `example.com`.  
**Classification:** DNS **MISSING**. Cloudflare **not deployed**.

---

## Verdict

**RECOMMENDED NOW** for DNS (Free plan).  
**RECOMMENDED** for TLS/WAF/DDoS if the first public URL is not yet behind AWS ALB+WAF.  
**DEFER** paid Cloudflare WAF/Bot/Image/Workers products.

VIP does **not** need Cloudflare Enterprise for customer #1.

If AWS is applied with Route 53 + ACM + ALB + AWS WAF as designed, Cloudflare is **optional** (DNS-only still helps as a registrar/DNS UX). If Mahmoud needs a public URL **this week** before AWS apply, Cloudflare is the fastest professional edge.

---

## Why Cloudflare now

| Capability | Need now? | Notes |
| --- | --- | --- |
| DNS | **YES** | There is no live zone. Someone must own `app.` / `api.` names. |
| CDN | Optional | SPA assets benefit; API must **not** be cached. |
| TLS | **YES** (somewhere) | Cloudflare Full Strict **or** ACM. One of them is mandatory. |
| WAF | Recommended | Free managed rules + rate limiting are enough for V1. AWS WAF is already in Terraform. Do not pay for both at enterprise tier. |
| DDoS | Free | Cloudflare proxy absorbs volumetric junk; AWS Shield Standard exists once ALB is live. |
| Bot protection | Defer paid | Free bot fight optional; paid bot management later. |
| Rate limiting | Recommended | Login + password-reset paths. App also rate-limits (fails **open** if Redis is down — edge limit still helps). |
| Security headers | Recommended | HSTS, once HTTPS is real. API already has production HSTS middleware. |
| Caching | SPA only | Bypass `/api/*`. |
| Origin protection | Recommended | Allowlist Cloudflare IPs on ALB/SG **if** orange-cloud proxy is on. |
| Staging lock | Recommended | Cloudflare Access (Free seats are limited) **or** IP allowlist / basic auth on `staging.` |

---

## Recommended hostname plan

```text
example.com              marketing later (or redirect to www)
www.example.com          marketing later
app.example.com          VIP Vue application
api.example.com          FastAPI
staging.example.com      staging app
api.staging.example.com  staging API
```

Email DNS (SPF/DKIM/DMARC) lives on the **sending** domain (`mail.example.com` or apex) for Resend/SES. That is not a Cloudflare “application subdomain”; it is DNS records.

Do **not** put the API on the same hostname as the SPA unless you deliberately design a reverse proxy. Current web Dockerfile substitutes `__API_ORIGIN__` into Nginx — the SPA calls the API origin via `VITE_API_BASE_URL`. Keep **split hostnames**.

---

## Minimum V1 setup (Free / low-cost)

### DNS

1. Buy the domain (registrar can be Cloudflare or elsewhere).  
2. Create a Cloudflare zone; switch nameservers.  
3. Records:  
   - `app` CNAME or A to origin (ALB or Render)  
   - `api` CNAME or A to origin  
   - staging equivalents  
   - Resend/SES TXT/CNAME as instructed  
4. Proxy status:  
   - **Orange cloud** on `app` and `api` if you want WAF/DDoS now.  
   - **Grey cloud (DNS only)** if AWS ALB+ACM+WAF is already live and you want to avoid TLS double-proxy. Both are valid.

### TLS

- If proxied: SSL/TLS mode **Full (Strict)**; origin certificate from Cloudflare **or** ACM on ALB.  
- Never **Flexible** (HTTP to origin) — cookies and CSRF will be wrong, and it is insecure.  
- `AUTH_COOKIE_SECURE=true`, `SameSite=Lax` (or `None` only if you truly cross-site).  
- Enable HSTS on Cloudflare **after** HTTPS works everywhere (including API).

### WAF / DDoS / rate limit (Free)

- Enable Cloudflare managed free ruleset.  
- Rate limit:  
  - `/api/v1/auth/login` (or actual login path) ~20/min/IP  
  - password-reset request ~5/min/IP  
- Challenge obviously malicious countries only if the customer base is GCC-only **and** you accept blocking travelers — default **do not** geo-block.  
- DDoS: default automatic (Free).

### Caching

- Cache Rules: cache `app.example.com` static assets (`/assets/*`).  
- **Bypass cache** for `api.example.com` entirely.  
- Bypass cache for `/login`, `/reset-password`, authenticated HTML.

### Staging protection

- `staging.*` behind Cloudflare Access (email OTP to operators) **or** a security group allowlist.  
- Do not expose staging to the world with production customer data.

### Origin restrictions

If orange-cloud:

- ALB / origin firewall: only Cloudflare IP ranges (keep updated) **or** Authenticated Origin Pulls.  
- Do not leave origin IPs browsable on :80/:443 from the internet.

### Security headers (Cloudflare Transform or origin)

- `Strict-Transport-Security` (production)  
- `X-Content-Type-Options: nosniff`  
- `Referrer-Policy: strict-origin-when-cross-origin`  
- CSP: origin already has a policy — do not invent a second conflicting CSP at the edge without testing the SPA.

---

## Paid features that can wait

| Feature | Wait until |
| --- | --- |
| WAF Business/Enterprise | Targeted attacks or compliance questionnaire demands it |
| Bot Management | Credential stuffing beyond what rate limits stop |
| Argo / Load Balancing | Multi-origin |
| Workers / Durable Objects | Not part of VIP V1 |
| Image resizing | Not needed |
| Logpush | After 3–5 customers |
| Success rate SLO product | After a paid SLA exists |

---

## Cloudflare vs AWS-only

| Topic | Cloudflare + AWS | AWS only (Route 53 + ALB + WAF) |
| --- | --- | --- |
| Fits existing Terraform | Requires `hosted_zone_id` change or NS delegation | Matches `infra/aws` as written |
| Speed to first URL | Fast | Slow until account/apply |
| GCC story | Cloudflare is a subprocessor (disclose) | Fewer processors |
| V1 recommendation | **Cloudflare DNS now**; proxy optional | Fine once staging ALB exists |

**Do not run two competing WAFs on overlapping rules without a diagram.** Pick: (a) Cloudflare proxy + AWS SG origin lock, AWS WAF off or empty; or (b) grey-cloud DNS + AWS WAF as in Terraform.

**Recommended for first production:** Cloudflare **DNS + optional proxy on app**; API may be grey-cloud to keep cookies simple if SameSite/cross-subdomain issues appear. Test cookie `Domain` and CSRF origins explicitly.

---

## Cookie / CSRF implications

Production Settings require explicit CORS and CSRF origins. When hostnames become `https://app.example.com` and `https://api.example.com`:

- Set `CORS_ALLOWED_ORIGINS=https://app.example.com`  
- Set `CSRF_TRUSTED_ORIGINS=https://app.example.com`  
- Set `FRONTEND_URL` and `INVITATION_ACCEPT_URL` to the app origin  
- Cookie domain: parent `.example.com` **only if** you understand CSRF; default host-only cookies on `api` + CORS credentials is the current model — **keep it** unless you have a reason to share cookies with `app`. SPA uses credentialed API calls; it does not need a cookie on `app`.

---

## Acceptance tests

1. `https://app.example.com/login` loads with a valid certificate.  
2. `https://api.example.com/health` is 200; HTTP redirects to HTTPS.  
3. Login works; cookies are `Secure; HttpOnly; SameSite=Lax`.  
4. API responses are **not** served from Cloudflare cache (send a mutating POST twice).  
5. Staging is not indexed and not publicly writable.  
6. Password-reset and invite DNS (SPF/DKIM) still validate after the zone cutover.

---

## Effort

**S** for DNS + records + TLS. **M** if orange-cloud + origin lock + cookie debugging.

**Owner:** Founder / DevOps.  
**Dependency:** domain purchase.  
**Blocks:** public demo URL, Resend domain verification, production go-live.
