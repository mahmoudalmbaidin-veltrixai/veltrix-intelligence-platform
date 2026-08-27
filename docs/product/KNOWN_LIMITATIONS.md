# Known limitations

- PostgreSQL and CSV/XLSX are the primary verified V1 source/ingestion paths. Other connector entries carry beta/planned/driver/agent status and are not GA claims.
- Anonymous/public dashboard sharing is not implemented.
- Real email requires an external SMTP provider. Development file-outbox output is not delivery.
- SSO and MFA are not available.
- AI, Reports, Automation, Billing, Marketplace, and Developer surfaces are gated or incomplete in live V1.
- Application files and generated artifacts use a filesystem provider. Shared persistent storage is required for multi-replica deployment; object-storage adapters are not included.
- The development Compose stack embeds schedule ticks in the generic worker and has no dedicated scheduler service.
- AWS Terraform is an implementation definition with static tests; account-specific plan/apply, data residency, cost, staging, restore, and production smoke tests remain operator responsibilities.
- Historical certification reports apply only to their named SHA and environment.
