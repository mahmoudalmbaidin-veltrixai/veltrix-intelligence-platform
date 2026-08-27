# VIP Client Demo Checklist

## Before the meeting

- [ ] Docker/services healthy
- [ ] `/health` = 200
- [ ] `/ready` = 200
- [ ] Frontend live API mode
- [ ] Demo admin login tested
- [ ] Demo editor login tested
- [ ] Demo viewer login tested
- [ ] PostgreSQL connection tested
- [ ] CSV file ready
- [ ] Demo dataset clean
- [ ] Pipeline run tested
- [ ] Semantic model ready
- [ ] Dashboard ready
- [ ] Published dashboard ready
- [ ] PDF ready
- [ ] PNG ready
- [ ] Schedule example ready and disabled
- [ ] Notification center clean; three relevant results marked read
- [ ] Unsupported modules hidden/gated
- [ ] Connector catalog default shows PostgreSQL and Local file upload only
- [ ] Downloads folder clean
- [ ] Browser tabs prepared
- [ ] Browser zoom 100%
- [ ] No DevTools visible
- [ ] Screen-sharing notifications disabled
- [ ] Export notification warning remembered: **DO NOT CLICK — SHOW NOTIFICATION STATE ONLY**
- [ ] Credential helper used privately; passwords not visible in notes, browser tabs, clipboard history, or screen share

## Recommended browser tabs

1. Home / organization overview
2. Demo Sales PostgreSQL
3. Sales Orders — Raw CSV / Data Quality
4. Sales Revenue Quality & Curation
5. Executive Sales Semantic Model
6. Executive Sales Performance editor
7. Published Executive Sales Performance viewer
8. Monday Executive Sales Brief
9. Notifications
10. Help & Docs

## Five-minute smoke

- [ ] Login is responsive
- [ ] Curated Sales Orders preview opens
- [ ] Retained pipeline run says succeeded
- [ ] Dashboard shows SAR 659,930 revenue and 716 orders
- [ ] Western region shows SAR 229,500
- [ ] Region filter applies and clears
- [ ] Published viewer loads without editor controls
- [ ] Local backup PDF opens and is readable

## Meeting safety

- [ ] Do not open unrelated tenants or platform-wide QA data
- [ ] Do not click export-completion notifications (`STAGE1-NB-001`)
- [ ] Do not enable gated/mock modules
- [ ] Do not claim transactional email is complete
- [ ] Do not claim production hosting, AWS, Cloudflare, Resend, or KSA residency is complete
- [ ] Do not quote connector catalog size as GA support
- [ ] Do not edit the prepared dashboard or semantic model live

# Post-demo reset

1. Close all VIP sessions that may be editing demo assets.
2. From the repository root run:

   ```powershell
   .\scripts\demo\reset-vip-demo.ps1
   ```

3. Confirm the command reports:

   ```text
   connection_test=success
   raw_rows=723
   pipeline_status=succeeded
   pdf_export=completed
   png_export=completed
   ```

4. Confirm `/health` and `/ready` return 200.
5. Reopen the published dashboard and confirm Total Revenue = SAR 659,930 and Total Orders = 716.
6. Keep the regenerated IDs in ignored `artifacts/demo-stage2/environment-manifest.json`; do not hard-code old IDs in browser bookmarks.
7. Mark the regenerated three relevant notifications as read if necessary.
8. Re-prepare browser tabs and keep the export-notification deep-link warning in place.

Reset safety: the script validates and deletes only the exact organization slug `veltrix-demo-organization`, then recreates the tenant through supported APIs. It does not delete or alter unrelated QA, UAT, personal, or customer tenants. Demo credentials remain protected outside Git with Windows DPAPI.
