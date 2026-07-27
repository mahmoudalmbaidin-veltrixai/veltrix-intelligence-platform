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
    # Connectors that genuinely require external setup are not marked available.
    assert CONNECTION_TYPE_BY_KEY["snowflake"].implementation_status == "planned"
    assert CONNECTION_TYPE_BY_KEY["mssql"].implementation_status == "requires_driver"
    assert CONNECTION_TYPE_BY_KEY["sap_s4hana"].implementation_status == "requires_agent"


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
        validate_configuration("snowflake", {"anything": "here"})
