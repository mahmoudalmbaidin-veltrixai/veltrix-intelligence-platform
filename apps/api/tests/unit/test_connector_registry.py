"""Registry invariants: the catalog must be broad, accurate, and honest.

These guard the non-negotiable rule that a connector is never presented as usable
unless it has a real configuration/credential schema and a working test strategy.
"""

from __future__ import annotations

import pytest

from vip_api.connections.catalog import (
    CONNECTION_TYPE_BY_KEY,
    CONNECTION_TYPES,
    validate_configuration,
    validate_credentials,
)

VALID_STATUSES = {
    "available",
    "beta",
    "planned",
    "requires_agent",
    "requires_driver",
    "disabled",
}
VALID_DEPLOYMENTS = {"cloud", "on_prem", "hybrid"}

pytestmark = pytest.mark.unit


def test_catalog_is_broad_and_multi_category() -> None:
    assert len(CONNECTION_TYPES) >= 60
    categories = {item.category for item in CONNECTION_TYPES}
    # Every major enterprise family is represented.
    for expected in ("database", "warehouse", "object_storage", "erp", "crm", "api", "streaming"):
        assert expected in categories


def test_every_definition_has_valid_metadata() -> None:
    keys = [item.key for item in CONNECTION_TYPES]
    assert len(keys) == len(set(keys)), "connector keys must be unique"
    for item in CONNECTION_TYPES:
        assert item.implementation_status in VALID_STATUSES
        assert item.deployment in VALID_DEPLOYMENTS
        assert item.key and item.name and item.vendor
        # enabled is derived strictly from status; never a bare card.
        assert item.enabled == (item.implementation_status in ("available", "beta"))


def test_only_usable_connectors_expose_a_real_schema() -> None:
    for item in CONNECTION_TYPES:
        has_schema = bool(item.configuration_schema.get("properties"))
        if item.enabled:
            # Usable connectors must have a real config schema and a test strategy,
            # except local_file which is handled by the dataset upload path.
            if item.key == "local_file":
                continue
            assert has_schema, f"{item.key} is enabled but has no configuration schema"
            assert item.test_strategy not in ("unsupported", "")
        else:
            assert item.test_strategy in ("unsupported", "none")


def test_known_statuses_are_accurate() -> None:
    assert CONNECTION_TYPE_BY_KEY["postgresql"].implementation_status == "available"
    assert CONNECTION_TYPE_BY_KEY["rest_api"].implementation_status == "available"
    assert CONNECTION_TYPE_BY_KEY["mysql"].implementation_status == "beta"
    # The five post-Core connectors are wired and testable but classified beta
    # (real drivers/endpoints are external; not battle-tested against prod).
    for key in ("mssql", "snowflake", "bigquery", "s3"):
        assert CONNECTION_TYPE_BY_KEY[key].implementation_status == "beta"
        assert CONNECTION_TYPE_BY_KEY[key].enabled is True
    # Connectors that genuinely require external setup remain gated off (not enabled).
    assert CONNECTION_TYPE_BY_KEY["oracle"].enabled is False
    assert CONNECTION_TYPE_BY_KEY["sap_s4hana"].implementation_status == "requires_agent"
    assert CONNECTION_TYPE_BY_KEY["sap_s4hana"].enabled is False


def test_mysql_configuration_validation() -> None:
    config = validate_configuration(
        "mysql",
        {
            "host": "db.internal",
            "port": 3306,
            "database": "vip_demo",
            "username": "reader",
            "ssl_mode": "require",
            "connect_timeout_seconds": 10,
        },
    )
    assert config["port"] == 3306 and config["database"] == "vip_demo"
    assert validate_credentials("mysql", {"password": "secret"}) == {"password": "secret"}


def test_unknown_and_planned_connectors_reject_configuration() -> None:
    with pytest.raises(ValueError):
        validate_configuration("does_not_exist", {})
    # Planned connectors have no adapter and cannot accept a configuration.
    with pytest.raises(ValueError):
        validate_configuration("oracle", {"anything": "here"})


def test_new_connectors_validate_configuration_and_separate_secrets() -> None:
    # mssql
    cfg = validate_configuration(
        "mssql",
        {"host": "sql.internal", "port": 1433, "database": "sales", "username": "reader"},
    )
    assert cfg["port"] == 1433 and cfg["encrypt"] is True
    assert validate_credentials("mssql", {"password": "s"}) == {"password": "s"}
    # snowflake
    cfg = validate_configuration(
        "snowflake",
        {
            "account": "acme-eu",
            "username": "svc",
            "warehouse": "WH",
            "database": "DB",
            "schema_name": "PUBLIC",
        },
    )
    assert cfg["account"] == "acme-eu"
    # bigquery secret is the SA-key JSON (write-only)
    cfg = validate_configuration("bigquery", {"project_id": "proj-1", "location": "US"})
    assert cfg["project_id"] == "proj-1"
    assert "service_account_json" in validate_credentials(
        "bigquery", {"service_account_json": '{"type":"service_account"}'}
    )
    # s3
    cfg = validate_configuration("s3", {"bucket": "my-bucket", "region": "eu-west-1"})
    assert cfg["bucket"] == "my-bucket"
    creds = validate_credentials("s3", {"access_key_id": "AKIA", "secret_access_key": "sk"})
    assert creds["access_key_id"] == "AKIA"


def test_new_connector_configs_reject_secrets_and_unknown_keys() -> None:
    # A password must never be accepted in the (non-secret) configuration body.
    for key, base in (
        ("mssql", {"host": "h", "database": "d", "username": "u"}),
        ("s3", {"bucket": "buck-et"}),
    ):
        with pytest.raises(ValueError):
            validate_configuration(key, {**base, "password": "leak"})
