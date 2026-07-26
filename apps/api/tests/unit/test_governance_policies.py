"""Deterministic governance catalog and route-policy tests."""

from types import MappingProxyType
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.core.config import Settings
from vip_api.governance.context import AuthorizationContext
from vip_api.governance.policies import (
    SYSTEM_PERMISSION_KEYS,
    SYSTEM_PERMISSIONS,
    SYSTEM_ROLE_PERMISSIONS,
    SYSTEM_ROLES,
    validate_policy_catalog,
)
from vip_api.governance.route_policy import missing_governance_policies
from vip_api.governance.services import authorize_any
from vip_api.main import create_application


def test_catalog_keys_and_mappings_are_deterministic() -> None:
    validate_policy_catalog()
    assert len(SYSTEM_PERMISSION_KEYS) == len(SYSTEM_PERMISSIONS)
    assert len({role.key for role in SYSTEM_ROLES}) == len(SYSTEM_ROLES)
    assert (
        SYSTEM_ROLE_PERMISSIONS["organization_admin"]
        == SYSTEM_ROLE_PERMISSIONS["organization_owner"]
    )


def test_viewer_and_restricted_are_least_privilege() -> None:
    viewer = SYSTEM_ROLE_PERMISSIONS["viewer"]
    restricted = SYSTEM_ROLE_PERMISSIONS["restricted_user"]
    assert viewer and all(not key.endswith((".create", ".update", ".delete")) for key in viewer)
    assert restricted == frozenset({"workspace.read"})
    assert "organization.members.read" not in viewer | restricted


def test_editor_and_admin_policy() -> None:
    editor = SYSTEM_ROLE_PERMISSIONS["editor"]
    admin = SYSTEM_ROLE_PERMISSIONS["organization_admin"]
    assert {"dashboard.create", "pipeline.execute"} <= editor
    assert "organization.members.invite" not in editor
    assert {"organization.members.invite", "audit.read", "workspace.create"} <= admin


def test_every_versioned_route_declares_governance_policy(settings: Settings) -> None:
    app = create_application(settings)
    assert missing_governance_policies(app) == []


@pytest.mark.asyncio
async def test_any_permission_uses_real_or_semantics() -> None:
    context = AuthorizationContext(
        user_id=uuid4(),
        organization_id=uuid4(),
        workspace_id=uuid4(),
        organization_role_key="organization_member",
        workspace_role_key="viewer",
        permissions=frozenset({"dashboard.read"}),
        entitlements=frozenset(),
        feature_flags=MappingProxyType({}),
        quotas=MappingProxyType({}),
        correlation_id="test",
    )
    await authorize_any(
        cast(AsyncSession, object()),
        context,
        frozenset({"dashboard.read", "pipeline.read"}),
    )
