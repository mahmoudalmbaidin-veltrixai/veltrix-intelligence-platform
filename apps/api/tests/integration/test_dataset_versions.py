"""Dataset version list/restore + ACL coverage (post-Core P2)."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select

from vip_api.auth.models import User, UserStatus, utc_now
from vip_api.connections.models import Connection, ConnectionType
from vip_api.core.config import Settings
from vip_api.core.errors import ApplicationError
from vip_api.database.session import Database
from vip_api.datasets.models import Dataset, DatasetVersion
from vip_api.datasets.services import (
    list_dataset_versions,
    restore_dataset_version,
)
from vip_api.governance.context import AuthorizationContext
from vip_api.governance.models import Role
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
        organization_role_key="organization_admin",
        workspace_role_key="workspace_admin",
        permissions=frozenset(permissions),
        entitlements=frozenset({"dataset_studio"}),
        feature_flags={"dataset_studio": True},
        quotas={},
        correlation_id="dataset-versions-test",
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dataset_versions_list_restore_and_acl(settings: Settings) -> None:
    database = Database(settings)
    org_id = user_id = None
    try:
        async with database.session_factory() as db:
            suffix = uuid4().hex[:8]
            await seed_system_governance(db)
            roles = {r.key: r for r in (await db.scalars(select(Role))).all()}
            user = User(
                username=f"dv-{suffix}",
                normalized_username=f"dv-{suffix}",
                email=f"dv-{suffix}@vip.test",
                normalized_email=f"dv-{suffix}@vip.test",
                password_hash="unused",
                display_name="DV",
                status=UserStatus.ACTIVE,
            )
            db.add(user)
            await db.flush()
            user_id = user.id
            org = Organization(
                name="DV Org",
                slug=f"dv-org-{suffix}",
                status=OrganizationStatus.ACTIVE,
                created_by_user_id=user.id,
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
                created_by_user_id=user.id,
            )
            db.add(ws)
            await db.flush()
            db.add_all(
                (
                    OrganizationMembership(
                        organization_id=org.id,
                        user_id=user.id,
                        role_id=roles["organization_admin"].id,
                        status=MembershipStatus.ACTIVE,
                        joined_at=utc_now(),
                    ),
                    WorkspaceMembership(
                        organization_id=org.id,
                        workspace_id=ws.id,
                        user_id=user.id,
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
            dataset = Dataset(
                organization_id=org.id,
                workspace_id=ws.id,
                connection_id=conn.id,
                dataset_type="table",
                source_schema="public",
                source_name="orders",
                source_key="public.orders",
                qualified_name="public.orders",
                display_name="Orders v2",
                description="current",
                source_object_type="table",
                status="active",
                version=2,
            )
            db.add(dataset)
            await db.flush()
            dataset_id = dataset.id
            # Two immutable versions: v1 had a different display_name.
            db.add_all(
                (
                    DatasetVersion(
                        organization_id=org.id,
                        workspace_id=ws.id,
                        dataset_id=dataset_id,
                        version_number=1,
                        version_type="created",
                        snapshot={
                            "dataset": {"display_name": "Orders v1", "description": "orig"},
                            "fields": [],
                        },
                        change_summary="Dataset registered",
                        created_by_user_id=user.id,
                    ),
                    DatasetVersion(
                        organization_id=org.id,
                        workspace_id=ws.id,
                        dataset_id=dataset_id,
                        version_number=2,
                        version_type="certified",
                        snapshot={
                            "dataset": {"display_name": "Orders v2", "description": "current"},
                            "fields": [],
                        },
                        change_summary="Certified",
                        created_by_user_id=user.id,
                    ),
                )
            )
            await db.commit()

        admin = _ctx(user_id, org_id, ws.id, permissions={"dataset.read", "dataset.update"})
        viewer = _ctx(user_id, org_id, ws.id, permissions={"dataset.read"})

        async with database.session_factory() as db:
            versions = await list_dataset_versions(db, admin, dataset_id)
            assert [v.version_number for v in versions] == [2, 1]
            assert versions[0].version_type == "certified"

        # A query-only caller cannot restore (edit required) -> non-disclosing 404.
        async with database.session_factory() as db:
            with pytest.raises(ApplicationError) as denied:
                await restore_dataset_version(db, viewer, dataset_id, versions[1].id, 2)
            assert denied.value.status_code in (403, 404)

        # An editor restores v1: the live dataset reverts and a v3 "restored" appears.
        async with database.session_factory() as db:
            restored = await restore_dataset_version(db, admin, dataset_id, versions[1].id, 2)
            assert restored.display_name == "Orders v1"
        async with database.session_factory() as db:
            rows = list(
                (
                    await db.scalars(
                        select(DatasetVersion)
                        .where(DatasetVersion.dataset_id == dataset_id)
                        .order_by(DatasetVersion.version_number)
                    )
                ).all()
            )
            assert [r.version_number for r in rows] == [1, 2, 3]
            assert rows[-1].version_type == "restored"
            assert rows[-1].source_version_id == versions[1].id
            reloaded = await db.get(Dataset, dataset_id)
            assert reloaded is not None and reloaded.display_name == "Orders v1"
    finally:
        if org_id is not None and user_id is not None:
            async with database.session_factory() as db:
                await db.execute(delete(Dataset).where(Dataset.organization_id == org_id))
                await db.execute(delete(Connection).where(Connection.organization_id == org_id))
                await db.execute(delete(Organization).where(Organization.id == org_id))
                await db.execute(delete(User).where(User.id == user_id))
                await db.commit()
            await database.engine.dispose()
