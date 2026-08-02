"""Explicit-deny enforcement for non-dashboard resources (Slice C).

Proves that :func:`resource_access_service.enforce_resource_guard`, wired into the
pipeline/dataset/connection/semantic services, fails closed on explicit ACL denies
and honours level-specific denies and expiration — independently of route RBAC.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.auth.models import User, UserStatus
from vip_api.core.config import Settings
from vip_api.core.errors import ApplicationError
from vip_api.database.session import Database
from vip_api.governance import resource_access_service
from vip_api.governance.context import AuthorizationContext
from vip_api.governance.seed import seed_system_governance
from vip_api.pipelines.schemas import PipelineCreate
from vip_api.pipelines.services import create_pipeline, get_editor
from vip_api.tenancy.models import (
    MembershipStatus,
    Organization,
    OrganizationMembership,
    OrganizationStatus,
    Workspace,
    WorkspaceMembership,
    WorkspaceStatus,
)


def _ctx(user: UUID, org: UUID, ws: UUID, *, admin: bool) -> AuthorizationContext:
    perms = {"pipeline.read", "pipeline.create", "pipeline.update", "pipeline.execute"}
    if admin:
        perms |= {"resource.permissions.manage", "resource.permissions.read"}
    return AuthorizationContext(
        user_id=user,
        organization_id=org,
        workspace_id=ws,
        organization_role_key="organization_admin" if admin else "organization_member",
        workspace_role_key="workspace_admin" if admin else "developer",
        permissions=frozenset(perms),
        entitlements=frozenset({"pipeline_studio"}),
        feature_flags={"pipeline_studio": True},
        quotas={},
        correlation_id="guard-test",
    )


async def _role_id(db: AsyncSession, key: str) -> UUID:
    from vip_api.governance.services import get_role

    scope = "organization" if key.startswith("organization") else "workspace"
    role = await get_role(db, key, scope)
    return role.id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pipeline_guard_enforces_explicit_deny_and_expiration(settings: Settings) -> None:
    database = Database(settings)
    org_id: UUID | None = None
    admin_id: UUID | None = None
    member_id: UUID | None = None
    try:
        async with database.session_factory() as db:
            await seed_system_governance(db)
            suffix = uuid4().hex[:8]
            admin = User(
                username=f"guard-admin-{suffix}",
                normalized_username=f"guard-admin-{suffix}",
                email=f"guard-admin-{suffix}@vip.test",
                normalized_email=f"guard-admin-{suffix}@vip.test",
                display_name="Guard Admin",
                password_hash="unused",
                status=UserStatus.ACTIVE,
            )
            member = User(
                username=f"guard-member-{suffix}",
                normalized_username=f"guard-member-{suffix}",
                email=f"guard-member-{suffix}@vip.test",
                normalized_email=f"guard-member-{suffix}@vip.test",
                display_name="Guard Member",
                password_hash="unused",
                status=UserStatus.ACTIVE,
            )
            db.add_all((admin, member))
            await db.flush()
            admin_id, member_id = admin.id, member.id
            org = Organization(
                name="Guard Org",
                slug=f"guard-org-{suffix}",
                status=OrganizationStatus.ACTIVE,
                created_by_user_id=admin.id,
            )
            db.add(org)
            await db.flush()
            org_id = org.id
            ws = Workspace(
                organization_id=org.id,
                name="Guard WS",
                slug="guard-ws",
                status=WorkspaceStatus.ACTIVE,
                is_default=True,
                created_by_user_id=admin.id,
            )
            db.add(ws)
            await db.flush()

            org_admin_role = await _role_id(db, "organization_admin")
            org_member_role = await _role_id(db, "organization_member")
            ws_admin_role = await _role_id(db, "workspace_admin")
            db.add_all(
                (
                    OrganizationMembership(
                        organization_id=org.id,
                        user_id=admin.id,
                        role_id=org_admin_role,
                        status=MembershipStatus.ACTIVE,
                    ),
                    OrganizationMembership(
                        organization_id=org.id,
                        user_id=member.id,
                        role_id=org_member_role,
                        status=MembershipStatus.ACTIVE,
                    ),
                    WorkspaceMembership(
                        organization_id=org.id,
                        workspace_id=ws.id,
                        user_id=admin.id,
                        role_id=ws_admin_role,
                        status=MembershipStatus.ACTIVE,
                    ),
                    WorkspaceMembership(
                        organization_id=org.id,
                        workspace_id=ws.id,
                        user_id=member.id,
                        role_id=ws_admin_role,
                        status=MembershipStatus.ACTIVE,
                    ),
                )
            )
            await db.commit()

            admin_ctx = _ctx(admin.id, org.id, ws.id, admin=True)
            member_ctx = _ctx(member.id, org.id, ws.id, admin=False)

            editor = await create_pipeline(
                db, admin_ctx, PipelineCreate(name="Guarded", description="", tags=[])
            )
            pipeline_id = editor.pipeline.id

            # Baseline: member can view the pipeline (no deny yet).
            assert (await get_editor(db, member_ctx, pipeline_id)).pipeline.id == pipeline_id

            # A developer-level deny blocks edit/publish but not viewing.
            await resource_access_service.grant_resource_access(
                db,
                admin_ctx,
                resource_type="pipeline",
                resource_id=pipeline_id,
                subject_type="user",
                subject_id=member.id,
                access_level="developer",
                effect="deny",
            )
            # Viewer-level read still allowed (deny is at a higher rank).
            assert (await get_editor(db, member_ctx, pipeline_id)).pipeline.id == pipeline_id
            with pytest.raises(ApplicationError) as excinfo:
                await resource_access_service.enforce_resource_guard(
                    db,
                    resource_type="pipeline",
                    resource_id=pipeline_id,
                    action_level="developer",
                    organization_id=org.id,
                    workspace_id=ws.id,
                    user_id=member.id,
                )
            assert excinfo.value.code == "RESOURCE_ACCESS_DENIED"

            # A viewer-level deny blocks everything, including read.
            await resource_access_service.grant_resource_access(
                db,
                admin_ctx,
                resource_type="pipeline",
                resource_id=pipeline_id,
                subject_type="user",
                subject_id=member.id,
                access_level="viewer",
                effect="deny",
            )
            with pytest.raises(ApplicationError) as excinfo:
                await get_editor(db, member_ctx, pipeline_id)
            assert excinfo.value.code == "RESOURCE_ACCESS_DENIED"

            # An expired deny is ignored.
            entries = await resource_access_service.list_resource_entries(
                db, admin_ctx, resource_type="pipeline", resource_id=pipeline_id
            )
            for entry in entries:
                await resource_access_service.revoke_resource_access(
                    db,
                    admin_ctx,
                    resource_type="pipeline",
                    resource_id=pipeline_id,
                    entry_id=entry.id,
                )
            await resource_access_service.grant_resource_access(
                db,
                admin_ctx,
                resource_type="pipeline",
                resource_id=pipeline_id,
                subject_type="user",
                subject_id=member.id,
                access_level="viewer",
                effect="deny",
                expires_at=datetime.now(UTC) - timedelta(minutes=5),
            )
            # Expired deny no longer blocks the read path.
            assert (await get_editor(db, member_ctx, pipeline_id)).pipeline.id == pipeline_id
    finally:
        async with database.session_factory() as db:
            if org_id is not None:
                await db.execute(delete(Organization).where(Organization.id == org_id))
            for uid in (admin_id, member_id):
                if uid is not None:
                    await db.execute(delete(User).where(User.id == uid))
            await db.commit()
        await database.engine.dispose()
