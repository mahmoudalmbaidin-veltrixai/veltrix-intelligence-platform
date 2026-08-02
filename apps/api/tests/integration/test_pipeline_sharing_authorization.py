"""Integration: Pipeline sharing-management authorization.

Sharing a pipeline (granting/revoking resource access) must require the resource
Owner OR an authorized tenant admin (holder of the ``pipeline.update`` manage
permission). A Developer/Operator/Viewer whose access comes purely from a
resource ACL grant must NOT be able to re-share — elevation grants the capability
band, never the right to administer sharing. Exercised against the real
``resource_access_service`` and ``vip_test``.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select

from vip_api.auth.models import User, UserStatus
from vip_api.core.config import Settings
from vip_api.core.errors import ApplicationError
from vip_api.database.session import Database
from vip_api.governance import resource_access_service
from vip_api.governance.context import AuthorizationContext
from vip_api.governance.models import ResourceAccessEntry, Role
from vip_api.pipelines.models import Pipeline
from vip_api.pipelines.schemas import PipelineCreate
from vip_api.pipelines.services import create_pipeline
from vip_api.tenancy.models import (
    MembershipStatus,
    Organization,
    OrganizationMembership,
    OrganizationStatus,
    Workspace,
    WorkspaceStatus,
)


def _ctx(
    user: UUID, org: UUID, ws: UUID, permissions: frozenset[str] = frozenset()
) -> AuthorizationContext:
    return AuthorizationContext(
        user_id=user,
        organization_id=org,
        workspace_id=ws,
        organization_role_key="organization_member",
        workspace_role_key="workspace_member",
        permissions=permissions,
        entitlements=frozenset({"pipeline_studio"}),
        feature_flags={"pipeline_studio": True},
        quotas={},
        correlation_id="pipeline-sharing-test",
    )


def _user(suffix: str, tag: str) -> User:
    return User(
        username=f"psh-{tag}-{suffix}",
        normalized_username=f"psh-{tag}-{suffix}",
        email=f"psh-{tag}-{suffix}@vip.test",
        normalized_email=f"psh-{tag}-{suffix}@vip.test",
        display_name=tag.title(),
        password_hash="unused",
        status=UserStatus.ACTIVE,
    )


async def _grant(
    db: object,
    ctx: AuthorizationContext,
    resource_id: UUID,
    subject_id: UUID,
    level: str,
) -> object:
    return await resource_access_service.grant_resource_access(
        db,  # type: ignore[arg-type]
        ctx,
        resource_type="pipeline",
        resource_id=resource_id,
        subject_type="user",
        subject_id=subject_id,
        access_level=level,
        effect="allow",
        expires_at=None,
        is_platform_admin=False,
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pipeline_sharing_requires_owner_or_admin(settings: Settings) -> None:
    database = Database(settings)
    org_id: UUID | None = None
    user_ids: list[UUID] = []
    try:
        async with database.session_factory() as db:
            suffix = uuid4().hex[:8]
            role_id = await db.scalar(select(Role.id).where(Role.key == "organization_member"))
            assert role_id is not None

            owner = _user(suffix, "owner")
            admin = _user(suffix, "admin")
            developer = _user(suffix, "dev")
            viewer = _user(suffix, "viewer")
            target = _user(suffix, "target")
            everyone = [owner, admin, developer, viewer, target]
            db.add_all(everyone)
            await db.flush()
            user_ids = [u.id for u in everyone]

            org = Organization(
                name="Share Org",
                slug=f"psh-org-{suffix}",
                status=OrganizationStatus.ACTIVE,
                created_by_user_id=owner.id,
            )
            db.add(org)
            await db.flush()
            org_id = org.id
            ws = Workspace(
                organization_id=org.id,
                name="Share WS",
                slug="psh-ws",
                status=WorkspaceStatus.ACTIVE,
                is_default=True,
                created_by_user_id=owner.id,
            )
            db.add(ws)
            await db.flush()
            db.add_all(
                OrganizationMembership(
                    organization_id=org.id,
                    user_id=uid,
                    role_id=role_id,
                    status=MembershipStatus.ACTIVE,
                )
                for uid in user_ids
            )
            await db.commit()

            owner_ctx = _ctx(
                owner.id, org.id, ws.id, frozenset({"pipeline.read", "pipeline.create"})
            )
            pipeline = await create_pipeline(db, owner_ctx, PipelineCreate(name="Shared"))
            pid = pipeline.pipeline.id

            # A Developer and a Viewer receive resource ACL grants (band elevation).
            db.add_all(
                (
                    ResourceAccessEntry(
                        organization_id=org.id,
                        workspace_id=ws.id,
                        resource_type="pipeline",
                        resource_id=pid,
                        subject_type="user",
                        subject_id=developer.id,
                        access_level="developer",
                        effect="allow",
                    ),
                    ResourceAccessEntry(
                        organization_id=org.id,
                        workspace_id=ws.id,
                        resource_type="pipeline",
                        resource_id=pid,
                        subject_type="user",
                        subject_id=viewer.id,
                        access_level="viewer",
                        effect="allow",
                    ),
                )
            )
            await db.commit()

            # (a) The actual OWNER may share.
            entry = await _grant(db, owner_ctx, pid, target.id, "viewer")
            assert entry is not None

            # (b) A tenant ADMIN (holds the pipeline.update manage permission) may share.
            admin_ctx = _ctx(admin.id, org.id, ws.id, frozenset({"pipeline.update"}))
            entry2 = await _grant(db, admin_ctx, pid, target.id, "operator")
            assert entry2 is not None

            # (c) A DEVELOPER whose access is only a resource ACL grant may NOT share.
            developer_ctx = _ctx(developer.id, org.id, ws.id)  # no workspace permissions
            with pytest.raises(ApplicationError) as dev_exc:
                await _grant(db, developer_ctx, pid, target.id, "viewer")
            assert dev_exc.value.status_code == 403
            assert dev_exc.value.code == "RESOURCE_MANAGE_DENIED"

            # (d) A VIEWER ACL grantee may NOT share.
            viewer_ctx = _ctx(viewer.id, org.id, ws.id)
            with pytest.raises(ApplicationError) as viewer_exc:
                await _grant(db, viewer_ctx, pid, target.id, "viewer")
            assert viewer_exc.value.status_code == 403
            assert viewer_exc.value.code == "RESOURCE_MANAGE_DENIED"
    finally:
        async with database.session_factory() as db:
            if org_id is not None:
                await db.execute(
                    delete(ResourceAccessEntry).where(ResourceAccessEntry.organization_id == org_id)
                )
                await db.execute(delete(Pipeline).where(Pipeline.organization_id == org_id))
                await db.execute(delete(Organization).where(Organization.id == org_id))
            for uid in user_ids:
                await db.execute(delete(User).where(User.id == uid))
            await db.commit()
        await database.dispose()
