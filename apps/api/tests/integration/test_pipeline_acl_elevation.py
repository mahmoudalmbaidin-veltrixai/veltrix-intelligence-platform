"""Integration: Pipeline resource-ACL grant elevation.

Proves a tenant member WITHOUT the broad ``pipeline.read`` workspace permission
can reach a specific pipeline through a resource ACL grant (elevation), cannot
reach others, is bounded by the granted level, and that collection listing is
visibility-filtered — all through the real services against vip_test.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select

from vip_api.auth.models import User, UserStatus
from vip_api.core.config import Settings
from vip_api.core.errors import ApplicationError
from vip_api.database.session import Database
from vip_api.governance.context import AuthorizationContext
from vip_api.governance.models import ResourceAccessEntry, Role
from vip_api.pipelines.models import Pipeline
from vip_api.pipelines.schemas import PipelineCreate
from vip_api.pipelines.services import create_pipeline, list_pipelines, require_pipeline_access
from vip_api.tenancy.models import (
    MembershipStatus,
    Organization,
    OrganizationMembership,
    OrganizationStatus,
    Workspace,
    WorkspaceStatus,
)


def _ctx(user: UUID, org: UUID, ws: UUID, permissions: frozenset[str]) -> AuthorizationContext:
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
        correlation_id="pipeline-acl-test",
    )


def _acl(
    org: UUID,
    ws: UUID,
    resource_id: UUID,
    subject: UUID,
    level: str,
    effect: str = "allow",
    expires_at: datetime | None = None,
) -> ResourceAccessEntry:
    return ResourceAccessEntry(
        organization_id=org,
        workspace_id=ws,
        resource_type="pipeline",
        resource_id=resource_id,
        subject_type="user",
        subject_id=subject,
        access_level=level,
        effect=effect,
        expires_at=expires_at,
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pipeline_acl_grant_elevation_and_collection_filter(settings: Settings) -> None:
    database = Database(settings)
    org_id: UUID | None = None
    user_ids: list[UUID] = []
    try:
        async with database.session_factory() as db:
            suffix = uuid4().hex[:8]
            role_id = await db.scalar(select(Role.id).where(Role.key == "organization_member"))
            assert role_id is not None

            owner = User(
                username=f"pacl-owner-{suffix}",
                normalized_username=f"pacl-owner-{suffix}",
                email=f"pacl-owner-{suffix}@vip.test",
                normalized_email=f"pacl-owner-{suffix}@vip.test",
                display_name="Owner",
                password_hash="unused",
                status=UserStatus.ACTIVE,
            )
            viewer = User(
                username=f"pacl-viewer-{suffix}",
                normalized_username=f"pacl-viewer-{suffix}",
                email=f"pacl-viewer-{suffix}@vip.test",
                normalized_email=f"pacl-viewer-{suffix}@vip.test",
                display_name="Viewer",
                password_hash="unused",
                status=UserStatus.ACTIVE,
            )
            db.add_all((owner, viewer))
            await db.flush()
            user_ids = [owner.id, viewer.id]
            org = Organization(
                name="ACL Org",
                slug=f"pacl-org-{suffix}",
                status=OrganizationStatus.ACTIVE,
                created_by_user_id=owner.id,
            )
            db.add(org)
            await db.flush()
            org_id = org.id
            ws = Workspace(
                organization_id=org.id,
                name="ACL WS",
                slug="pacl-ws",
                status=WorkspaceStatus.ACTIVE,
                is_default=True,
                created_by_user_id=owner.id,
            )
            db.add(ws)
            await db.flush()
            # Both users are active org members (required by the suspended check).
            db.add_all(
                OrganizationMembership(
                    organization_id=org.id,
                    user_id=uid,
                    role_id=role_id,
                    status=MembershipStatus.ACTIVE,
                )
                for uid in (owner.id, viewer.id)
            )
            await db.commit()

            # Owner holds the broad workspace pipeline role; creates two pipelines.
            owner_ctx = _ctx(
                owner.id,
                org.id,
                ws.id,
                frozenset({"pipeline.read", "pipeline.create", "pipeline.update"}),
            )
            shared = await create_pipeline(db, owner_ctx, PipelineCreate(name="Shared Pipeline"))
            other = await create_pipeline(db, owner_ctx, PipelineCreate(name="Other Pipeline"))
            shared_id = shared.pipeline.id
            other_id = other.pipeline.id

            # Viewer has NO pipeline.* permissions — only a Viewer ACL on `shared`.
            db.add(_acl(org.id, ws.id, shared_id, viewer.id, "viewer"))
            await db.commit()
            viewer_ctx = _ctx(viewer.id, org.id, ws.id, frozenset())

            # (a) ELEVATION: viewer can open the shared pipeline without pipeline.read.
            item = await require_pipeline_access(db, viewer_ctx, shared_id, "viewer")
            assert item.id == shared_id

            # (b) ISOLATION: viewer cannot open a pipeline they were not granted.
            with pytest.raises(ApplicationError) as exc_other:
                await require_pipeline_access(db, viewer_ctx, other_id, "viewer")
            assert exc_other.value.status_code == 404

            # (c) LEVEL BOUND: a Viewer grant does not confer developer access.
            with pytest.raises(ApplicationError) as exc_dev:
                await require_pipeline_access(db, viewer_ctx, shared_id, "developer")
            assert exc_dev.value.status_code == 404

            # (d) COLLECTION FILTER: viewer sees only the shared pipeline.
            viewer_list = await list_pipelines(db, viewer_ctx)
            assert {row.id for row in viewer_list.items} == {shared_id}

            # (e) Broad-permission owner still sees both.
            owner_list = await list_pipelines(db, owner_ctx)
            assert {shared_id, other_id} <= {row.id for row in owner_list.items}

            # (f) EXPLICIT DENY overrides the viewer allow.
            db.add(_acl(org.id, ws.id, shared_id, viewer.id, "viewer", effect="deny"))
            await db.commit()
            with pytest.raises(ApplicationError):
                await require_pipeline_access(db, viewer_ctx, shared_id, "viewer")
            filtered = await list_pipelines(db, viewer_ctx)
            assert shared_id not in {row.id for row in filtered.items}  # deny hides it

            # (g) EXPIRED allow does not grant access. Fresh pipeline + expired grant.
            expired = await create_pipeline(db, owner_ctx, PipelineCreate(name="Expired Pipeline"))
            db.add(
                _acl(
                    org.id,
                    ws.id,
                    expired.pipeline.id,
                    viewer.id,
                    "viewer",
                    expires_at=datetime.now(UTC) - timedelta(hours=1),
                )
            )
            await db.commit()
            with pytest.raises(ApplicationError):
                await require_pipeline_access(db, viewer_ctx, expired.pipeline.id, "viewer")
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
