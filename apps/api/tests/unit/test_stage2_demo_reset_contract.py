"""Fail-closed contract checks for the Stage 2 sales-demo reset entrypoint."""

import json
from pathlib import Path

ROOT = Path(__file__).parents[4]
RESET = ROOT / "scripts" / "demo" / "reset-demo-environment.ps1"
ALLOWLIST = ROOT / "demo-data" / "stage2" / "cleanup-allowlist.json"


def test_stage2_reset_requires_independent_non_production_signals() -> None:
    source = RESET.read_text(encoding="utf-8")
    for guard in (
        "APP_ENV",
        "ALLOW_DEMO_RESET",
        "ConfirmNonProduction",
        "VerifiedBackupPath",
        "pg_restore --list",
        "/api/v1/version",
        "development",
        "test",
        "localhost",
        "alembic current",
        "alembic heads",
    ):
        assert guard in source
    assert "DROP DATABASE" not in source.upper()
    assert "TRUNCATE" not in source.upper()
    assert "organizations WHERE slug IN" in source


def test_stage2_cleanup_allowlist_retains_only_three_fictional_tenants() -> None:
    configuration = json.loads(ALLOWLIST.read_text(encoding="utf-8"))
    assert configuration["retainedOrganizationSlugs"] == [
        "northstar-retail-group",
        "crestline-telecom-services",
        "meridian-facilities-solutions",
    ]
    assert configuration["retainedUsernames"] == ["vip.demo.platform.admin"]
    assert len(configuration["approvedOrganizationSlugs"]) == len(
        set(configuration["approvedOrganizationSlugs"])
    )
    assert all("*" not in slug for slug in configuration["approvedOrganizationSlugs"])
    assert all("*" not in username for username in configuration["approvedUsernames"])
