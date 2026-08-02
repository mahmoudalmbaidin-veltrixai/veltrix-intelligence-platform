"""Unit coverage for the resource-access engine's pure helpers."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from vip_api.core.errors import ApplicationError
from vip_api.governance.context import AuthorizationContext
from vip_api.governance.resource_access import LEVEL_ORDERS
from vip_api.governance.resource_access_service import (
    RESOURCE_SPECS,
    ResourceMeta,
    can_manage_resource,
    levels_for,
    resource_types,
    role_level,
    spec_for,
    validate_level,
)


def _context(permissions: set[str], user_id: UUID | None = None) -> AuthorizationContext:
    return AuthorizationContext(
        user_id=user_id or uuid4(),
        organization_id=uuid4(),
        workspace_id=uuid4(),
        organization_role_key="organization_member",
        workspace_role_key="viewer",
        permissions=frozenset(permissions),
        entitlements=frozenset(),
        feature_flags={},
        quotas={},
        correlation_id="unit-test",
    )


def test_resource_types_cover_all_specs() -> None:
    assert set(resource_types()) == set(RESOURCE_SPECS)
    for resource_type in resource_types():
        assert resource_type in LEVEL_ORDERS


def test_levels_for_matches_ladder() -> None:
    assert levels_for("dashboard") == ("view", "interact", "edit", "manage")
    assert levels_for("pipeline") == ("viewer", "operator", "developer", "owner")


def test_validate_level_rejects_unknown() -> None:
    validate_level("dashboard", "edit")
    with pytest.raises(ApplicationError):
        validate_level("dashboard", "owner")


def test_spec_for_unknown_raises() -> None:
    with pytest.raises(ApplicationError):
        spec_for("unknown_type")


@pytest.mark.parametrize(
    ("resource_type", "permissions", "expected"),
    [
        ("dashboard", {"dashboard.read"}, "view"),
        ("dashboard", {"dashboard.read", "dashboard.update"}, "edit"),
        ("dashboard", {"dashboard.share"}, "manage"),
        ("pipeline", {"pipeline.read"}, "viewer"),
        ("pipeline", {"pipeline.read", "pipeline.execute"}, "operator"),
        ("connection", {"connection.read"}, "use"),
        ("connection", {"connection.delete"}, "manage"),
        ("dashboard", set(), None),
    ],
)
def test_role_level(resource_type: str, permissions: set[str], expected: str | None) -> None:
    assert role_level(resource_type, frozenset(permissions)) == expected


def _meta(owner: UUID) -> ResourceMeta:
    return ResourceMeta(
        exists=True, owner_user_id=owner, workspace_id=None, workspace_archived=False
    )


def test_can_manage_resource_owner() -> None:
    owner = uuid4()
    context = _context(set(), user_id=owner)
    assert can_manage_resource(context, RESOURCE_SPECS["dashboard"], _meta(owner))


def test_can_manage_resource_permission() -> None:
    context = _context({"dashboard.share"})
    assert can_manage_resource(context, RESOURCE_SPECS["dashboard"], _meta(uuid4()))


def test_can_manage_resource_denied() -> None:
    context = _context({"dashboard.read"})
    meta = _meta(uuid4())
    assert not can_manage_resource(context, RESOURCE_SPECS["dashboard"], meta)
    assert can_manage_resource(context, RESOURCE_SPECS["dashboard"], meta, is_platform_admin=True)
