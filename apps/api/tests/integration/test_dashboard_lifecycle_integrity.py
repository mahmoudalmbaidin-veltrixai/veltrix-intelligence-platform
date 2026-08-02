"""Dashboard lifecycle + version-integrity regression coverage.

Drives the real dashboard services (create/save/reload/publish) against vip_test
and asserts widget identity, ordering, layout, draft/published separation, and
published-version immutability — the mechanisms behind the reported (and
previously non-reproduced) wrong-card / export-mismatch concern. Uses `text`
widgets so no semantic model seeding is required; the published DashboardVersion
snapshot is exactly what the export worker reads, so version binding is asserted
at the snapshot level.
"""

from __future__ import annotations

from typing import cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select

from vip_api.auth.models import User, UserStatus
from vip_api.core.config import Settings
from vip_api.core.errors import ApplicationError
from vip_api.dashboards.models import Dashboard, DashboardVersion
from vip_api.dashboards.schemas import (
    DashboardCreate,
    EditorSave,
    GridLayout,
    PageInput,
    WidgetInput,
)
from vip_api.dashboards.services import create_dashboard, editor, publish, save_editor
from vip_api.database.session import Database
from vip_api.governance.context import AuthorizationContext
from vip_api.tenancy.models import Organization, OrganizationStatus, Workspace, WorkspaceStatus


def _context(user: UUID, org: UUID, ws: UUID) -> AuthorizationContext:
    return AuthorizationContext(
        user_id=user,
        organization_id=org,
        workspace_id=ws,
        organization_role_key="organization_admin",
        workspace_role_key="workspace_admin",
        permissions=frozenset(
            {"dashboard.read", "dashboard.create", "dashboard.update", "dashboard.publish"}
        ),
        entitlements=frozenset({"dashboard_studio"}),
        feature_flags={"dashboard_studio": True},
        quotas={},
        correlation_id="dashboard-lifecycle-test",
    )


def _text(wid: UUID | None, title: str, content: str, x: int, y: int) -> WidgetInput:
    return WidgetInput(
        id=wid,
        type="text",
        title=title,
        content=content,
        layout=GridLayout(x=x, y=y, w=6, h=4),
    )


def _ids(page: PageInput) -> list[UUID | None]:
    return [w.id for w in page.widgets]


def _titles(page: PageInput) -> list[str]:
    return [w.title for w in page.widgets]


def _snapshot_overview_titles(snapshot: dict[str, object]) -> list[object]:
    pages = cast("list[dict[str, object]]", snapshot["pages"])
    return [
        widget["title"]
        for page in pages
        if page["key"] == "overview"
        for widget in cast("list[dict[str, object]]", page["widgets"])
    ]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dashboard_lifecycle_widget_and_version_integrity(settings: Settings) -> None:
    database = Database(settings)
    org_id: UUID | None = None
    user_id: UUID | None = None
    try:
        async with database.session_factory() as db:
            suffix = uuid4().hex[:8]
            user = User(
                username=f"dash-{suffix}",
                normalized_username=f"dash-{suffix}",
                email=f"dash-{suffix}@vip.test",
                normalized_email=f"dash-{suffix}@vip.test",
                display_name="Dash Test",
                password_hash="unused",
                status=UserStatus.ACTIVE,
            )
            db.add(user)
            await db.flush()
            user_id = user.id
            org = Organization(
                name="Dash Org",
                slug=f"dash-org-{suffix}",
                status=OrganizationStatus.ACTIVE,
                created_by_user_id=user.id,
            )
            db.add(org)
            await db.flush()
            org_id = org.id
            ws = Workspace(
                organization_id=org.id,
                name="Dash WS",
                slug="dash-ws",
                status=WorkspaceStatus.ACTIVE,
                is_default=True,
                created_by_user_id=user.id,
            )
            db.add(ws)
            await db.commit()
            ctx = _context(user.id, org.id, ws.id)

            detail = await create_dashboard(db, ctx, DashboardCreate(name="Lifecycle Board"))
            dash_id = detail.id

            # ---- v1: two pages, widgets A,B,C on page one; D on page two ----
            save1 = EditorSave(
                expected_version=detail.row_version,
                name="Lifecycle Board",
                pages=[
                    PageInput(
                        key="overview",
                        name="Overview",
                        position=0,
                        widgets=[
                            _text(None, "Card A", "alpha", 0, 0),
                            _text(None, "Card B", "bravo", 0, 4),
                            _text(None, "Card C", "charlie", 6, 0),
                        ],
                    ),
                    PageInput(
                        key="details",
                        name="Details",
                        position=1,
                        widgets=[_text(None, "Card D", "delta", 0, 0)],
                    ),
                ],
            )
            saved1 = await save_editor(db, ctx, dash_id, save1)
            page0 = next(p for p in saved1.pages if p.key == "overview")
            id_a, id_b, id_c = (w.id for w in page0.widgets)
            id_d = next(p for p in saved1.pages if p.key == "details").widgets[0].id
            assert all(isinstance(i, UUID) for i in (id_a, id_b, id_c, id_d))

            # ---- reload: ids + order + layout stable ----
            reloaded = await editor(db, ctx, dash_id)
            r0 = next(p for p in reloaded.pages if p.key == "overview")
            assert _ids(r0) == [id_a, id_b, id_c]
            assert _titles(r0) == ["Card A", "Card B", "Card C"]
            assert next(w for w in r0.widgets if w.id == id_c).layout.x == 6

            # ---- v2: edit A, delete B, add E, duplicate C, reorder, resize, reorder pages ----
            save2 = EditorSave(
                expected_version=reloaded.version,
                name="Lifecycle Board",
                pages=[
                    PageInput(
                        key="details",  # page reorder: details first now
                        name="Details",
                        position=0,
                        widgets=[_text(id_d, "Card D", "delta", 0, 0)],
                    ),
                    PageInput(
                        key="overview",
                        name="Overview",
                        position=1,
                        widgets=[
                            _text(id_c, "Card C", "charlie", 0, 0),  # reordered first
                            _text(id_a, "Card A", "alpha-edited", 3, 2),  # edited + resized/moved
                            _text(None, "Card E", "echo", 6, 0),  # new
                            _text(
                                None, "Card C", "charlie", 6, 8
                            ),  # duplicate of C -> new identity
                        ],
                    ),
                ],
            )
            saved2 = await save_editor(db, ctx, dash_id, save2)
            ov = next(p for p in saved2.pages if p.key == "overview")
            # deleted B is gone; A/C stable; E and duplicate-C are new + unique
            assert id_b not in _ids(ov)
            assert ov.widgets[0].id == id_c and ov.widgets[1].id == id_a
            new_e, new_c2 = ov.widgets[2].id, ov.widgets[3].id
            assert new_e not in {id_a, id_b, id_c, id_d} and new_c2 not in {id_a, id_b, id_c, id_d}
            assert new_e != new_c2  # duplicate got its own identity
            assert _titles(ov) == ["Card C", "Card A", "Card E", "Card C"]
            # edited content + new layout persisted on A
            a_after = next(w for w in ov.widgets if w.id == id_a)
            assert a_after.content == "alpha-edited" and a_after.layout.x == 3
            # page reorder persisted
            assert next(p for p in saved2.pages if p.key == "details").position == 0

            # ---- publish v2 -> immutable snapshot ----
            v1 = await publish(db, ctx, dash_id, saved2.version, "first publish")
            dash_row = await db.get(Dashboard, dash_id)
            assert dash_row is not None and dash_row.published_version_id == v1.id
            version1 = await db.scalar(select(DashboardVersion).where(DashboardVersion.id == v1.id))
            assert version1 is not None
            snap1_titles = _snapshot_overview_titles(version1.snapshot)
            assert snap1_titles == ["Card C", "Card A", "Card E", "Card C"]

            # ---- edit again after publish, then confirm v1 snapshot is immutable ----
            save3 = EditorSave(
                expected_version=(await editor(db, ctx, dash_id)).version,
                name="Lifecycle Board",
                pages=[
                    PageInput(
                        key="details",
                        name="Details",
                        position=0,
                        widgets=[_text(id_d, "Card D", "delta", 0, 0)],
                    ),
                    PageInput(
                        key="overview",
                        name="Overview",
                        position=1,
                        widgets=[_text(id_a, "Card A", "alpha-v3", 0, 0)],
                    ),
                ],
            )
            await save_editor(db, ctx, dash_id, save3)
            version1_again = await db.scalar(
                select(DashboardVersion).where(DashboardVersion.id == v1.id)
            )
            assert version1_again is not None
            resnap_titles = _snapshot_overview_titles(version1_again.snapshot)
            assert resnap_titles == [
                "Card C",
                "Card A",
                "Card E",
                "Card C",
            ]  # unchanged (immutable)

            # ---- optimistic-lock conflict returns a clear error ----
            with pytest.raises(ApplicationError) as conflict:
                await save_editor(db, ctx, dash_id, save3)  # stale expected_version
            assert conflict.value.code == "DASHBOARD_VERSION_CONFLICT"
    finally:
        async with database.session_factory() as db:
            if org_id is not None:
                await db.execute(delete(Dashboard).where(Dashboard.organization_id == org_id))
                await db.execute(delete(Organization).where(Organization.id == org_id))
            if user_id is not None:
                await db.execute(delete(User).where(User.id == user_id))
            await db.commit()
        await database.dispose()
