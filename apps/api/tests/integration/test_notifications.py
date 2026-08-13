"""Per-user notification read-state persistence and isolation (BUG-NOTIF-001).

Notifications are a tenant-scoped derived feed; read state is stored per user.
These tests drive the route handlers directly against PostgreSQL and assert that
read state persists across re-fetch, does not leak between users sharing a
workspace, and that mark-all clears the unread count.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete

from vip_api.auth.models import User, UserStatus
from vip_api.core.config import Settings
from vip_api.database.session import Database
from vip_api.governance.context import AuthorizationContext
from vip_api.home.models import NotificationRead
from vip_api.home.routes import (
    mark_all_notifications_read,
    mark_notification_read,
    notifications,
    unmark_notification_read,
    unread_count,
)
from vip_api.jobs.models import Job
from vip_api.tenancy.models import (
    Organization,
    OrganizationStatus,
    Workspace,
    WorkspaceStatus,
)


def _ctx(user: UUID, org: UUID, ws: UUID) -> AuthorizationContext:
    return AuthorizationContext(
        user_id=user,
        organization_id=org,
        workspace_id=ws,
        organization_role_key="organization_member",
        workspace_role_key="workspace_member",
        permissions=frozenset({"workspace.read"}),
        entitlements=frozenset(),
        feature_flags={},
        quotas={},
        correlation_id="notif-test",
    )


async def _job(db: object, *, org: UUID, ws: UUID, user: UUID, name: str, status: str) -> None:
    suffix = uuid4().hex[:8]
    db.add(  # type: ignore[attr-defined]
        Job(
            organization_id=org,
            workspace_id=ws,
            job_type="pipeline_run",
            handler="noop",
            name=name,
            status=status,
            idempotency_key=f"idem-{suffix}",
            correlation_id=f"corr-{suffix}",
            created_by_user_id=user,
        )
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_notification_read_state_persists_and_is_isolated(settings: Settings) -> None:
    database = Database(settings)
    org_id = ws_id = user_a = user_b = None
    try:
        async with database.session_factory() as db:
            suffix = uuid4().hex[:8]
            a = User(
                username=f"na-{suffix}",
                normalized_username=f"na-{suffix}",
                email=f"na-{suffix}@vip.test",
                normalized_email=f"na-{suffix}@vip.test",
                password_hash="x",
                display_name="A",
                status=UserStatus.ACTIVE,
            )
            b = User(
                username=f"nb-{suffix}",
                normalized_username=f"nb-{suffix}",
                email=f"nb-{suffix}@vip.test",
                normalized_email=f"nb-{suffix}@vip.test",
                password_hash="x",
                display_name="B",
                status=UserStatus.ACTIVE,
            )
            db.add_all((a, b))
            await db.flush()
            user_a, user_b = a.id, b.id
            org = Organization(
                name="Notif Org",
                slug=f"notif-{suffix}",
                status=OrganizationStatus.ACTIVE,
                created_by_user_id=a.id,
            )
            db.add(org)
            await db.flush()
            org_id = org.id
            ws = Workspace(
                organization_id=org.id,
                name="Default",
                slug="default",
                status=WorkspaceStatus.ACTIVE,
                is_default=True,
                created_by_user_id=a.id,
            )
            db.add(ws)
            await db.flush()
            ws_id = ws.id
            # A tenant-scoped feed of three surfaced jobs (shared by both users).
            await _job(db, org=org_id, ws=ws_id, user=a.id, name="Pipeline 1", status="succeeded")
            await _job(db, org=org_id, ws=ws_id, user=a.id, name="Pipeline 2", status="failed")
            await _job(db, org=org_id, ws=ws_id, user=a.id, name="Pipeline 3", status="running")
            await db.commit()

        ctx_a = _ctx(user_a, org_id, ws_id)
        ctx_b = _ctx(user_b, org_id, ws_id)

        # Fresh feed: everything unread for both users.
        async with database.session_factory() as db:
            feed = await notifications(ctx_a, db)
            assert len(feed) == 3
            assert all(entry.read is False for entry in feed)
            assert (await unread_count(ctx_a, db)).count == 3
            assert (await unread_count(ctx_b, db)).count == 3
            first_id = feed[0].id

        # A marks one read → A drops to 2, B is unaffected, and it PERSISTS.
        async with database.session_factory() as db:
            assert (await mark_notification_read(first_id, ctx_a, db)).count == 2
        async with database.session_factory() as db:
            assert (await unread_count(ctx_a, db)).count == 2  # persisted across sessions
            assert (await unread_count(ctx_b, db)).count == 3  # isolated per user
            feed_a = await notifications(ctx_a, db)
            assert next(e for e in feed_a if e.id == first_id).read is True

        # Marking a foreign / non-feed id is a harmless no-op.
        async with database.session_factory() as db:
            assert (await mark_notification_read("job:does-not-exist:9", ctx_a, db)).count == 2

        # A marks all read → 0, and it stays 0 on refetch; B still sees 3.
        async with database.session_factory() as db:
            assert (await mark_all_notifications_read(ctx_a, db)).count == 0
        async with database.session_factory() as db:
            assert (await unread_count(ctx_a, db)).count == 0  # survives "logout/login"
            assert (await unread_count(ctx_b, db)).count == 3

        # Un-marking a notification restores it to unread and persists.
        async with database.session_factory() as db:
            assert (await unmark_notification_read(first_id, ctx_a, db)).count == 1
        async with database.session_factory() as db:
            assert (await unread_count(ctx_a, db)).count == 1
            await mark_notification_read(first_id, ctx_a, db)  # tidy back to 0

        # A genuinely new notification becomes unread for A only.
        async with database.session_factory() as db:
            await _job(db, org=org_id, ws=ws_id, user=user_a, name="Pipeline 4", status="succeeded")
            await db.commit()
        async with database.session_factory() as db:
            assert (await unread_count(ctx_a, db)).count == 1
    finally:
        if org_id is not None:
            async with database.session_factory() as db:
                await db.execute(delete(Job).where(Job.organization_id == org_id))
                await db.execute(
                    delete(NotificationRead).where(NotificationRead.user_id.in_([user_a, user_b]))
                )
                await db.execute(delete(Workspace).where(Workspace.organization_id == org_id))
                await db.execute(delete(Organization).where(Organization.id == org_id))
                await db.execute(delete(User).where(User.id.in_([user_a, user_b])))
                await db.commit()
            await database.engine.dispose()
