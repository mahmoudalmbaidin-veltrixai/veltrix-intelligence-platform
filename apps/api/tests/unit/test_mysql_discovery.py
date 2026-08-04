"""MySQL metadata-discovery unit coverage (Phase B9.1C).

Type-normalization and object-filter logic are pure and CI-safe (no MySQL
connection). The live discovery round-trip against the real MySQL container is
exercised separately; here we lock the mapping and filtering contracts and
confirm the adapter is wired into the discovery registry.
"""

from __future__ import annotations

import pytest

from vip_api.core.config import Settings
from vip_api.datasets.discovery import (
    MetadataDiscoveryAdapterRegistry,
    MySQLDiscoveryAdapter,
    normalize_mysql_type,
)


@pytest.mark.parametrize(
    ("physical", "expected"),
    [
        ("INT", "integer"),
        ("tinyint", "integer"),
        ("bigint", "integer"),
        ("year", "integer"),
        ("decimal", "decimal"),
        ("double", "decimal"),
        ("float", "decimal"),
        ("bit", "boolean"),
        ("boolean", "boolean"),
        ("date", "date"),
        ("datetime", "datetime"),
        ("timestamp", "datetime"),
        ("time", "time"),
        ("blob", "binary"),
        ("varbinary", "binary"),
        ("json", "json"),
        ("varchar", "string"),
        ("enum", "string"),
        ("set", "string"),
        ("longtext", "string"),
        ("geometry", "unknown"),
    ],
)
def test_normalize_mysql_type_maps_known_and_unknown(physical: str, expected: str) -> None:
    assert normalize_mysql_type(physical) == expected


def test_normalize_mysql_type_is_case_insensitive() -> None:
    assert normalize_mysql_type("VarChar") == normalize_mysql_type("varchar") == "string"


def test_mysql_object_filter_respects_type_include_and_exclude() -> None:
    allowed = MySQLDiscoveryAdapter._allowed
    # A base table is kept only when "table" is requested and it passes the globs.
    assert allowed("orders", "BASE TABLE", ["table"], ["*"], []) is True
    # A view is classified as "view"; excluded when only tables are requested.
    assert allowed("orders_v", "VIEW", ["table"], ["*"], []) is False
    assert allowed("orders_v", "VIEW", ["view"], ["*"], []) is True
    # Include/exclude globs are honored.
    assert allowed("staging_orders", "BASE TABLE", ["table"], ["staging_*"], []) is True
    assert allowed("orders", "BASE TABLE", ["table"], ["staging_*"], []) is False
    assert allowed("orders", "BASE TABLE", ["table"], ["*"], ["orders"]) is False


def test_mysql_adapter_registered_in_discovery_registry(settings: Settings) -> None:
    registry = MetadataDiscoveryAdapterRegistry(settings)
    assert isinstance(registry.get("mysql"), MySQLDiscoveryAdapter)
