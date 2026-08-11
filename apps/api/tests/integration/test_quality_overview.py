"""Workspace-wide Quality aggregate coverage (VIP-BUG-004 fan-out fix).

Proves the Quality workspace's rule/incident loading is BOUNDED — the SQL
statement count is identical whether the workspace has 3 datasets or 15 — and
that the aggregates enforce the same collection authorization (role, ACL allow,
explicit deny, tenant isolation) as the dataset list, so Quality can never
surface data for a dataset the caller may not see.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, event, select

from vip_api.auth.models import User, UserStatus, utc_now
from vip_api.connections.models import Connection, ConnectionType
from vip_api.core.config import Settings
from vip_api.database.session import Database
from vip_api.datasets.models import (
    Dataset,
    DatasetQualityResult,
    DatasetQualityRule,
)
from vip_api.datasets.services import (
    list_quality_incident_overview,
    list_quality_rule_overview,
)
from vip_api.governance.context import AuthorizationContext
from vip_api.governance.models import ResourceAccessEntry, Role
from vip_api.governance.seed import provision_organization_governance, seed_system_governance
from vip_api.tenancy.models import (
    MembershipStatus,
    Organization,
    OrganizationMembership,
    OrganizationStatus,
    Workspace,
    WorkspaceMembership,
    WorkspaceStatus,
)


def _ctx(user: UUID, org: UUID, ws: UUID, *, permissions: set[str]) -> AuthorizationContext:
    return AuthorizationContext(
        user_id=user,
        organization_id=org,
        workspace_id=ws,
        organization_role_key="organization_member",
        workspace_role_key="workspace_member",
        permissions=frozenset(permissions),
        entitlements=frozenset({"dataset_studio", "data_quality"}),
        feature_flags={"dataset_studio": True, "data_quality": True},
        quotas={},
        correlation_id="quality-overview-test",
    )


class _QueryCounter:
    """Count SQL statements issued on an engine within a context block."""

    def __init__(self, engine: object) -> None:
        self._sync = engine.sync_engine  # type: ignore[attr-defined]
        self.count = 0

    def _on_exec(self, *_args: object, **_kwargs: object) -> None:
        self.count += 1

    def __enter__(self) -> _QueryCounter:
        event.listen(self._sync, "before_cursor_execute", self._on_exec)
        return self

    def __exit__(self, *_exc: object) -> None:
        event.remove(self._sync, "before_cursor_execute", self._on_exec)


async def _seed_dataset_with_quality(
    db: object, *, org: UUID, ws: UUID, conn: UUID, user: UUID, name: str, failing: bool
) -> UUID:
    dataset = Dataset(
        organization_id=org,
        workspace_id=ws,
        connection_id=conn,
        dataset_type="table",
        source_schema="public",
        source_name=name,
        source_key=f"public.{name}",
        qualified_name=f"public.{name}",
        display_name=name,
        description="",
        source_object_type="table",
        status="active",
        version=1,
    )
    db.add(dataset)  # type: ignore[attr-defined]
    await db.flush()  # type: ignore[attr-defined]
    rule = DatasetQualityRule(
        organization_id=org,
        workspace_id=ws,
        dataset_id=dataset.id,
        rule_type="not_null",
        name=f"{name} not null",
        severity="error" if failing else "warning",
        status="failing" if failing else "passing",
        is_enabled=True,
        created_by_user_id=user,
    )
    db.add(rule)  # type: ignore[attr-defined]
    await db.flush()  # type: ignore[attr-defined]
    # Two results for the same rule: the OLDER is passing, the NEWER decides the
    # incident. This exercises the "latest result per rule" SQL collapse.
    older = DatasetQualityResult(
        organization_id=org,
        workspace_id=ws,
        quality_rule_id=rule.id,
        status="passing",
        observed_value="0",
        failure_count=0,
    )
    db.add(older)  # type: ignore[attr-defined]
    await db.flush()  # type: ignore[attr-defined]
    newer = DatasetQualityResult(
        organization_id=org,
        workspace_id=ws,
        quality_rule_id=rule.id,
        status="failing" if failing else "passing",
        observed_value="7" if failing else "0",
        failure_count=7 if failing else 0,
    )
    db.add(newer)  # type: ignore[attr-defined]
    await db.flush()  # type: ignore[attr-defined]
    return dataset.id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_quality_overview_is_bounded_and_authorized(settings: Settings) -> None:
    database = Database(settings)
    org_id = user_id = restricted_id = None
    try:
        async with database.session_factory() as db:
            suffix = uuid4().hex[:8]
            await seed_system_governance(db)
            roles = {r.key: r for r in (await db.scalars(select(Role))).all()}
            admin = User(
                username=f"qo-a-{suffix}",
                normalized_username=f"qo-a-{suffix}",
                email=f"qo-a-{suffix}@vip.test",
                normalized_email=f"qo-a-{suffix}@vip.test",
                password_hash="unused",
                display_name="QO Admin",
                status=UserStatus.ACTIVE,
            )
            restricted = User(
                username=f"qo-r-{suffix}",
                normalized_username=f"qo-r-{suffix}",
                email=f"qo-r-{suffix}@vip.test",
                normalized_email=f"qo-r-{suffix}@vip.test",
                password_hash="unused",
                display_name="QO Restricted",
                status=UserStatus.ACTIVE,
            )
            db.add_all((admin, restricted))
            await db.flush()
            user_id, restricted_id = admin.id, restricted.id
            org = Organization(
                name="QO Org",
                slug=f"qo-org-{suffix}",
                status=OrganizationStatus.ACTIVE,
                created_by_user_id=admin.id,
            )
            db.add(org)
            await db.flush()
            org_id = org.id
            await provision_organization_governance(db, org.id)
            ws = Workspace(
                organization_id=org.id,
                name="Default",
                slug="default",
                status=WorkspaceStatus.ACTIVE,
                is_default=True,
                created_by_user_id=admin.id,
            )
            db.add(ws)
            await db.flush()
            ws_id = ws.id
            db.add_all(
                (
                    OrganizationMembership(
                        organization_id=org.id,
                        user_id=admin.id,
                        role_id=roles["organization_admin"].id,
                        status=MembershipStatus.ACTIVE,
                        joined_at=utc_now(),
                    ),
                    WorkspaceMembership(
                        organization_id=org.id,
                        workspace_id=ws.id,
                        user_id=admin.id,
                        role_id=roles["workspace_admin"].id,
                        status=MembershipStatus.ACTIVE,
                    ),
                )
            )
            ctype = ConnectionType(
                key=f"pg-{suffix}",
                name="Postgres",
                category="database",
                configuration_schema={},
                secret_schema={},
                capabilities=["discover"],
                test_strategy="noop",
            )
            db.add(ctype)
            await db.flush()
            conn = Connection(
                organization_id=org.id,
                workspace_id=ws.id,
                connection_type_id=ctype.id,
                name="Conn",
                normalized_name="conn",
                configuration={},
                connection_type_version=1,
                status="active",
            )
            db.add(conn)
            await db.flush()

            first_ids: list[UUID] = []
            for i in range(3):
                first_ids.append(
                    await _seed_dataset_with_quality(
                        db,
                        org=org.id,
                        ws=ws.id,
                        conn=conn.id,
                        user=admin.id,
                        name=f"orders_{i:02d}",
                        failing=(i == 0),
                    )
                )
            await db.commit()

        broad = _ctx(user_id, org_id, ws_id, permissions={"dataset.read"})

        # --- Bounded query proof: measure statements at 3 datasets ---
        async with database.session_factory() as db:
            with _QueryCounter(database.engine) as counter_small:
                rules_small = await list_quality_rule_overview(
                    db, broad, page=1, page_size=50, search=None, status=None
                )
                incidents_small = await list_quality_incident_overview(
                    db, broad, page=1, page_size=50
                )
        assert rules_small.total == 3
        assert incidents_small.total == 1  # only orders_00 has a failing latest result
        assert incidents_small.items[0].dataset_name == "orders_00"
        assert incidents_small.items[0].rule_name == "orders_00 not null"

        # Grow the workspace to 15 datasets and re-measure. A bounded architecture
        # issues the SAME number of statements; an N+1 would grow with dataset count.
        async with database.session_factory() as db:
            conn2 = (
                await db.scalars(
                    select(Connection).where(Connection.organization_id == org_id)
                )
            ).first()
            assert conn2 is not None
            for i in range(3, 15):
                await _seed_dataset_with_quality(
                    db,
                    org=org_id,
                    ws=ws_id,
                    conn=conn2.id,
                    user=user_id,
                    name=f"orders_{i:02d}",
                    failing=(i % 2 == 0),
                )
            await db.commit()

        async with database.session_factory() as db:
            with _QueryCounter(database.engine) as counter_large:
                rules_large = await list_quality_rule_overview(
                    db, broad, page=1, page_size=50, search=None, status=None
                )
                incidents_large = await list_quality_incident_overview(
                    db, broad, page=1, page_size=50
                )
        assert rules_large.total == 15
        assert incidents_large.total == 7  # orders_00,02,04,06,08,10,12,14 -> failing even indexes
        # THE CORE ASSERTION: request/query count does not scale with dataset count.
        assert counter_large.count == counter_small.count

        # --- Pagination ---
        async with database.session_factory() as db:
            page1 = await list_quality_rule_overview(
                db, broad, page=1, page_size=5, search=None, status=None
            )
            page2 = await list_quality_rule_overview(
                db, broad, page=2, page_size=5, search=None, status=None
            )
        assert len(page1.items) == 5 and page1.total == 15
        assert len(page2.items) == 5
        assert {i.id for i in page1.items}.isdisjoint({i.id for i in page2.items})

        # --- Search (server-side) ---
        async with database.session_factory() as db:
            found = await list_quality_rule_overview(
                db, broad, page=1, page_size=50, search="orders_07", status=None
            )
        assert found.total == 1 and found.items[0].dataset_name == "orders_07"

        # --- Status filter ---
        async with database.session_factory() as db:
            failing_rules = await list_quality_rule_overview(
                db, broad, page=1, page_size=50, search=None, status="failing"
            )
        # Failing: orders_00 (batch 1) + orders_04,06,08,10,12,14 (batch 2 evens) = 7.
        assert failing_rules.total == 7

        # --- RBAC: restricted user with NO broad role and NO ACL grant sees nothing ---
        restricted_ctx = _ctx(restricted_id, org_id, ws_id, permissions=set())
        async with database.session_factory() as db:
            r_rules = await list_quality_rule_overview(
                db, restricted_ctx, page=1, page_size=50, search=None, status=None
            )
            r_incidents = await list_quality_incident_overview(
                db, restricted_ctx, page=1, page_size=50
            )
        assert r_rules.total == 0 and r_incidents.total == 0

        # --- ACL allow: grant the restricted user one failing dataset -> sees only it ---
        async with database.session_factory() as db:
            db.add(
                ResourceAccessEntry(
                    organization_id=org_id,
                    workspace_id=ws_id,
                    resource_type="dataset",
                    resource_id=first_ids[0],  # orders_00, failing
                    subject_type="user",
                    subject_id=restricted_id,
                    access_level="query",
                    effect="allow",
                )
            )
            await db.commit()
        async with database.session_factory() as db:
            g_rules = await list_quality_rule_overview(
                db, restricted_ctx, page=1, page_size=50, search=None, status=None
            )
            g_incidents = await list_quality_incident_overview(
                db, restricted_ctx, page=1, page_size=50
            )
        assert g_rules.total == 1 and g_rules.items[0].dataset_name == "orders_00"
        assert g_incidents.total == 1 and g_incidents.items[0].dataset_name == "orders_00"

        # --- Explicit DENY at the lowest level overrides broad role visibility ---
        lowest_level = "query"
        async with database.session_factory() as db:
            db.add(
                ResourceAccessEntry(
                    organization_id=org_id,
                    workspace_id=ws_id,
                    resource_type="dataset",
                    resource_id=first_ids[0],
                    subject_type="user",
                    subject_id=user_id,
                    access_level=lowest_level,
                    effect="deny",
                )
            )
            await db.commit()
        async with database.session_factory() as db:
            denied_rules = await list_quality_rule_overview(
                db, broad, page=1, page_size=50, search="orders_00", status=None
            )
            denied_incidents = await list_quality_incident_overview(
                db, broad, page=1, page_size=50
            )
        assert denied_rules.total == 0  # orders_00 hidden from the broad-role admin now
        assert all(i.dataset_name != "orders_00" for i in denied_incidents.items)
    finally:
        if org_id is not None:
            async with database.session_factory() as db:
                await db.execute(
                    delete(ResourceAccessEntry).where(
                        ResourceAccessEntry.organization_id == org_id
                    )
                )
                await db.execute(
                    delete(DatasetQualityResult).where(
                        DatasetQualityResult.organization_id == org_id
                    )
                )
                await db.execute(
                    delete(DatasetQualityRule).where(DatasetQualityRule.organization_id == org_id)
                )
                await db.execute(delete(Dataset).where(Dataset.organization_id == org_id))
                await db.execute(delete(Connection).where(Connection.organization_id == org_id))
                await db.execute(delete(Organization).where(Organization.id == org_id))
                for uid in (user_id, restricted_id):
                    if uid is not None:
                        await db.execute(delete(User).where(User.id == uid))
                await db.commit()
            await database.engine.dispose()
