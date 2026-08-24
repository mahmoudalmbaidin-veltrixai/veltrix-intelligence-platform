"""Static safety and scenario contract for the Stage 4 demo provisioner."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SCENARIOS = ROOT / "demo-data" / "stage4" / "scenarios.json"
PROVISIONER = ROOT / "scripts" / "demo-stage4" / "provision-enterprise-demo.ps1"


def test_stage4_scenario_contract_is_exact_and_balanced() -> None:
    config = json.loads(SCENARIOS.read_text(encoding="utf-8"))
    organizations = config["organizations"]

    assert [item["slug"] for item in organizations] == [
        "northstar-retail-group",
        "crestline-telecom-services",
        "meridian-facilities-solutions",
    ]
    assert all(len(item["workspaces"]) == 3 for item in organizations)
    assert all(
        sum(bool(ws["flagship"]) for ws in item["workspaces"]) == 1 for item in organizations
    )
    assert sum(len(item["users"]) for item in organizations) == 24
    assert {ws["sourceMode"] for item in organizations for ws in item["workspaces"]} == {
        "postgresql",
        "csv",
        "xlsx",
    }
    usernames = [user["username"] for item in organizations for user in item["users"]]
    emails = [user["email"] for item in organizations for user in item["users"]]
    assert len(usernames) == len(set(usernames)) == 24
    assert len(emails) == len(set(emails)) == 24
    assert all(email.endswith("@example.com") for email in emails)


def test_stage4_provisioner_has_multiple_fail_closed_guards() -> None:
    source = PROVISIONER.read_text(encoding="utf-8")

    assert "VIP_DEMO_ENVIRONMENT" in source
    assert "VIP_STAGE4_BACKUP_VERIFIED" in source
    assert "ConfirmNonProduction" in source
    assert "development" in source and "test" in source
    assert "pg_restore --list" in source
    assert "DROP DATABASE" not in source.upper()
    assert "DROP TABLE" not in source.upper()
    assert "LIKE '%" not in source
    assert "vip_local_dev_only" not in source
    assert "VIP_STAGE4_POSTGRES_PASSWORD" in source
    assert "must_change_password=$true" in source
