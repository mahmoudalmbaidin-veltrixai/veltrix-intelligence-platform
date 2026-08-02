"""Governance resolution, denial, quota, audit, and isolation security tests."""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from vip_api.auth.models import User, UserStatus, utc_now
from vip_api.core.config import Settings
from vip_api.core.errors import ApplicationError
from vip_api.database.session import Database
from vip_api.governance.context import AuthorizationContext
from vip_api.governance.models import (
    AuditEvent,
    Entitlement,
    FeatureFlag,
    FeatureFlagOverride,
    OrganizationEntitlement,
    OrganizationQuota,
    QuotaDefinition,
    Role,
)
from vip_api.governance.services import (
    GovernanceRequirement,
    authorize,
    consume_quota,
    resolve_authorization_context,
)
from vip_api.schemas.tenancy import WorkspaceCreate
from vip_api.tenancy.context import TenantContext
from vip_api.tenancy.models import (
    MembershipStatus,
    Organization,
    OrganizationMembership,
    OrganizationStatus,
    Workspace,
    WorkspaceMembership,
    WorkspaceStatus,
)
from vip_api.tenancy.services import create_workspace


@pytest.mark.integration
@pytest.mark.security
@pytest.mark.asyncio
async def test_governance_personas_denials_quota_and_tenant_isolation(
    settings: Settings,
) -> None:
    database = Database(settings)
    try:
        async with database.session_factory() as db:
            await db.execute(delete(Organization))
            await db.execute(delete(User))
            await db.commit()
            roles = {role.key: role for role in (await db.scalars(select(Role))).all()}
            users = {
                key: User(
                    username=f"governance-{key}",
                    normalized_username=f"governance-{key}",
                    email=f"governance-{key}@vip.test",
                    normalized_email=f"governance-{key}@vip.test",
                    password_hash="not-used",
                    display_name=key.title(),
                    status=UserStatus.ACTIVE,
                )
                for key in ("admin", "editor", "viewer", "restricted")
            }
            db.add_all(users.values())
            await db.flush()
            alpha = Organization(
                name="Governance Alpha",
                slug=f"governance-alpha-{uuid4().hex[:8]}",
                status=OrganizationStatus.ACTIVE,
                created_by_user_id=users["admin"].id,
            )
            beta = Organization(
                name="Governance Beta",
                slug=f"governance-beta-{uuid4().hex[:8]}",
                status=OrganizationStatus.ACTIVE,
                created_by_user_id=users["admin"].id,
            )
            db.add_all([alpha, beta])
            await db.flush()
            workspace = Workspace(
                organization_id=alpha.id,
                name="Alpha Workspace",
                slug="alpha-workspace",
                status=WorkspaceStatus.ACTIVE,
                is_default=True,
                created_by_user_id=users["admin"].id,
            )
            db.add(workspace)
            await db.flush()
            org_role_keys = {
                "admin": "organization_admin",
                "editor": "organization_member",
                "viewer": "organization_member",
                "restricted": "organization_member",
            }
            workspace_role_keys = {
                "admin": "workspace_admin",
                "editor": "editor",
                "viewer": "viewer",
                "restricted": "restricted_user",
            }
            memberships: dict[str, tuple[OrganizationMembership, WorkspaceMembership]] = {}
            for key in users:
                organization_membership = OrganizationMembership(
                    organization_id=alpha.id,
                    user_id=users[key].id,
                    role_id=roles[org_role_keys[key]].id,
                    status=MembershipStatus.ACTIVE,
                    joined_at=utc_now(),
                )
                workspace_membership = WorkspaceMembership(
                    organization_id=alpha.id,
                    workspace_id=workspace.id,
                    user_id=users[key].id,
                    role_id=roles[workspace_role_keys[key]].id,
                    status=MembershipStatus.ACTIVE,
                )
                db.add_all([organization_membership, workspace_membership])
                memberships[key] = (organization_membership, workspace_membership)
            await db.flush()
            pipeline_entitlement = await db.scalar(
                select(Entitlement).where(Entitlement.key == "pipeline_studio")
            )
            pipeline_flag = await db.scalar(
                select(FeatureFlag).where(FeatureFlag.key == "pipeline_studio")
            )
            pipeline_quota = await db.scalar(
                select(QuotaDefinition).where(QuotaDefinition.key == "pipelines.max")
            )
            assert pipeline_entitlement and pipeline_flag and pipeline_quota
            db.add_all(
                [
                    OrganizationEntitlement(
                        organization_id=alpha.id,
                        entitlement_id=pipeline_entitlement.id,
                        status="active",
                        source="test",
                    ),
                    OrganizationEntitlement(
                        organization_id=beta.id,
                        entitlement_id=pipeline_entitlement.id,
                        status="expired",
                        source="test",
                        ends_at=utc_now() - timedelta(days=1),
                    ),
                    FeatureFlagOverride(
                        feature_flag_id=pipeline_flag.id,
                        organization_id=alpha.id,
                        workspace_id=workspace.id,
                        enabled=False,
                    ),
                    OrganizationQuota(
                        organization_id=alpha.id,
                        quota_id=pipeline_quota.id,
                        limit_value=1,
                        source="test",
                    ),
                ]
            )
            await db.commit()

            contexts: dict[str, AuthorizationContext] = {}
            for key, (organization_membership, workspace_membership) in memberships.items():
                tenant = TenantContext(
                    user_id=users[key].id,
                    organization_id=alpha.id,
                    workspace_id=workspace.id,
                    organization_membership_id=organization_membership.id,
                    workspace_membership_id=workspace_membership.id,
                    organization_role=org_role_keys[key],
                    workspace_role=workspace_role_keys[key],
                    correlation_id=f"test-{key}",
                )
                contexts[key] = await resolve_authorization_context(db, tenant)

            assert "organization.members.update" in contexts["admin"].permissions
            assert "dashboard.create" in contexts["editor"].permissions
            assert "dashboard.create" not in contexts["viewer"].permissions
            assert contexts["restricted"].permissions == frozenset(
                {"organization.read", "workspace.read"}
            )
            with pytest.raises(ApplicationError) as viewer_denial:
                await authorize(db, contexts["viewer"], GovernanceRequirement("dashboard.create"))
            assert viewer_denial.value.code == "PERMISSION_DENIED"
            with pytest.raises(ApplicationError) as restricted_denial:
                await authorize(
                    db,
                    contexts["restricted"],
                    GovernanceRequirement("organization.members.read"),
                )
            assert restricted_denial.value.code == "PERMISSION_DENIED"
            with pytest.raises(ApplicationError) as feature_denial:
                await authorize(
                    db,
                    contexts["admin"],
                    GovernanceRequirement(
                        "pipeline.create",
                        feature="pipeline_studio",
                        entitlement="pipeline_studio",
                    ),
                )
            assert feature_denial.value.code == "FEATURE_DISABLED"
            with pytest.raises(ApplicationError) as entitlement_denial:
                await authorize(
                    db,
                    contexts["editor"],
                    GovernanceRequirement(
                        "dashboard.create",
                        feature="dashboard_studio",
                        entitlement="dashboard_studio",
                    ),
                )
            assert entitlement_denial.value.code == "ENTITLEMENT_REQUIRED"

            override = await db.scalar(
                select(FeatureFlagOverride).where(FeatureFlagOverride.organization_id == alpha.id)
            )
            assert override
            override.enabled = True
            await db.commit()
            refreshed = await resolve_authorization_context(
                db,
                TenantContext(
                    user_id=users["admin"].id,
                    organization_id=alpha.id,
                    workspace_id=workspace.id,
                    organization_membership_id=memberships["admin"][0].id,
                    workspace_membership_id=memberships["admin"][1].id,
                    organization_role="organization_admin",
                    workspace_role="workspace_admin",
                    correlation_id="quota-test",
                ),
            )
            await consume_quota(db, refreshed, "pipelines.max")
            await db.commit()
            exhausted = await resolve_authorization_context(
                db,
                TenantContext(
                    user_id=users["admin"].id,
                    organization_id=alpha.id,
                    workspace_id=workspace.id,
                    organization_membership_id=memberships["admin"][0].id,
                    workspace_membership_id=memberships["admin"][1].id,
                    organization_role="organization_admin",
                    workspace_role="workspace_admin",
                    correlation_id="quota-test-2",
                ),
            )
            with pytest.raises(ApplicationError) as quota_denial:
                await consume_quota(db, exhausted, "pipelines.max")
            assert quota_denial.value.code == "QUOTA_EXCEEDED"

            alpha_events = list(
                (
                    await db.scalars(
                        select(AuditEvent).where(AuditEvent.organization_id == alpha.id)
                    )
                ).all()
            )
            assert {event.reason_code for event in alpha_events} >= {
                "PERMISSION_DENIED",
                "FEATURE_DISABLED",
                "ENTITLEMENT_REQUIRED",
                "QUOTA_EXCEEDED",
            }
            assert not any(event.organization_id == beta.id for event in alpha_events)

            with pytest.raises(TypeError):
                await create_workspace(  # type: ignore[call-arg]
                    db,
                    alpha.id,
                    users["admin"],
                    WorkspaceCreate(name="Bypass", slug="bypass"),
                )

            expired_context = await resolve_authorization_context(
                db,
                TenantContext(
                    user_id=users["admin"].id,
                    organization_id=beta.id,
                    workspace_id=None,
                    organization_membership_id=memberships["admin"][0].id,
                    workspace_membership_id=None,
                    organization_role="organization_admin",
                    workspace_role=None,
                    correlation_id="expired-entitlement-test",
                ),
            )
            with pytest.raises(ApplicationError) as expired_denial:
                await authorize(
                    db,
                    expired_context,
                    GovernanceRequirement("organization.read", entitlement="pipeline_studio"),
                )
            assert expired_denial.value.code == "ENTITLEMENT_REQUIRED"
    finally:
        await database.dispose()
