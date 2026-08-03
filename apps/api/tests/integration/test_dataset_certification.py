"""Integration: Dataset certify/revoke are certify-gated (not edit), audited, and persistent."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select

from vip_api.auth.models import User, UserStatus
from vip_api.connections.models import Connection, ConnectionType
from vip_api.core.config import Settings
from vip_api.core.errors import ApplicationError
from vip_api.database.session import Database
from vip_api.datasets.models import Dataset
from vip_api.datasets.schemas import DatasetUpdate
from vip_api.datasets.services import (
    certify_dataset,
    revoke_dataset_certification,
    update_dataset,
)
from vip_api.governance.context import AuthorizationContext
from vip_api.governance.models import AuditEvent, ResourceAccessEntry, Role
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
        entitlements=frozenset({"dataset_studio"}),
        feature_flags={"dataset_studio": True},
        quotas={},
        correlation_id="dataset-cert-test",
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dataset_certify_requires_certify_not_edit(settings: Settings) -> None:
    database = Database(settings)
    org_id: UUID | None = None
    user_ids: list[UUID] = []
    try:
        async with database.session_factory() as db:
            suffix = uuid4().hex[:8]
            role_id = await db.scalar(select(Role.id).where(Role.key == "organization_member"))
            assert role_id is not None

            owner = User(
                username=f"dc-owner-{suffix}",
                normalized_username=f"dc-owner-{suffix}",
                email=f"dc-owner-{suffix}@vip.test",
                normalized_email=f"dc-owner-{suffix}@vip.test",
                display_name="Owner",
                password_hash="unused",
                status=UserStatus.ACTIVE,
            )
            editor = User(
                username=f"dc-editor-{suffix}",
                normalized_username=f"dc-editor-{suffix}",
                email=f"dc-editor-{suffix}@vip.test",
                normalized_email=f"dc-editor-{suffix}@vip.test",
                display_name="Editor",
                password_hash="unused",
                status=UserStatus.ACTIVE,
            )
            certifier = User(
                username=f"dc-cert-{suffix}",
                normalized_username=f"dc-cert-{suffix}",
                email=f"dc-cert-{suffix}@vip.test",
                normalized_email=f"dc-cert-{suffix}@vip.test",
                display_name="Certifier",
                password_hash="unused",
                status=UserStatus.ACTIVE,
            )
            db.add_all((owner, editor, certifier))
            await db.flush()
            user_ids = [owner.id, editor.id, certifier.id]

            org = Organization(
                name="Cert Org",
                slug=f"dc-org-{suffix}",
                status=OrganizationStatus.ACTIVE,
                created_by_user_id=owner.id,
            )
            db.add(org)
            await db.flush()
            org_id = org.id
            ws = Workspace(
                organization_id=org.id,
                name="Cert WS",
                slug="dc-ws",
                status=WorkspaceStatus.ACTIVE,
                is_default=True,
                created_by_user_id=owner.id,
            )
            db.add(ws)
            await db.flush()
            for uid in user_ids:
                db.add(
                    OrganizationMembership(
                        organization_id=org.id,
                        user_id=uid,
                        role_id=role_id,
                        status=MembershipStatus.ACTIVE,
                    )
                )
            ctype = ConnectionType(
                key=f"dc-pg-{suffix}",
                name="Postgres",
                category="database",
                configuration_schema={},
                secret_schema={},
                capabilities=["discover"],
                test_strategy="noop",
            )
            db.add(ctype)
            await db.flush()
            connection = Connection(
                organization_id=org.id,
                workspace_id=ws.id,
                connection_type_id=ctype.id,
                name="Conn",
                normalized_name="conn",
                configuration={},
                connection_type_version=1,
                status="active",
            )
            db.add(connection)
            await db.flush()
            dataset = Dataset(
                organization_id=org.id,
                workspace_id=ws.id,
                connection_id=connection.id,
                dataset_type="table",
                source_schema="public",
                source_name="orders",
                source_key="public.orders",
                qualified_name="public.orders",
                display_name="Orders",
                source_object_type="table",
                status="active",
                version=1,
                owner_user_id=owner.id,
            )
            db.add(dataset)
            await db.flush()
            db.add_all(
                (
                    ResourceAccessEntry(
                        organization_id=org.id,
                        workspace_id=ws.id,
                        resource_type="dataset",
                        resource_id=dataset.id,
                        subject_type="user",
                        subject_id=editor.id,
                        access_level="edit",
                        effect="allow",
                    ),
                    ResourceAccessEntry(
                        organization_id=org.id,
                        workspace_id=ws.id,
                        resource_type="dataset",
                        resource_id=dataset.id,
                        subject_type="user",
                        subject_id=certifier.id,
                        access_level="certify",
                        effect="allow",
                    ),
                )
            )
            await db.commit()
            dataset_id = dataset.id

            editor_ctx = _ctx(editor.id, org.id, ws.id)
            cert_ctx = _ctx(certifier.id, org.id, ws.id)

            # Edit can rename but cannot certify through update (field removed).
            updated = await update_dataset(
                db,
                editor_ctx,
                dataset_id,
                DatasetUpdate(display_name="Orders Renamed", version=1),
            )
            assert updated.display_name == "Orders Renamed"
            assert updated.certification_status == "uncertified"

            # Edit-only cannot certify.
            with pytest.raises(ApplicationError) as edit_cert_exc:
                await certify_dataset(db, editor_ctx, dataset_id, version=updated.version)
            assert edit_cert_exc.value.status_code == 404

            # Certify-capable user can certify without manage access.
            certified = await certify_dataset(
                db, cert_ctx, dataset_id, version=updated.version, note="UAT ready"
            )
            assert certified.certification_status == "certified"
            assert certified.certified_by_user_id == certifier.id
            assert certified.certified_at is not None
            assert certified.certification_note == "UAT ready"

            audit = await db.scalar(
                select(AuditEvent)
                .where(
                    AuditEvent.resource_id == dataset_id,
                    AuditEvent.event_type == "dataset.certified",
                )
                .order_by(AuditEvent.occurred_at.desc())
            )
            assert audit is not None
            assert audit.actor_user_id == certifier.id

            # Reload persistence
            row = await db.scalar(select(Dataset).where(Dataset.id == dataset_id))
            assert row is not None
            assert row.certification_status == "certified"
            assert row.certification_note == "UAT ready"

            revoked = await revoke_dataset_certification(
                db, cert_ctx, dataset_id, version=certified.version, note="Superseded"
            )
            assert revoked.certification_status == "uncertified"
            assert revoked.certified_by_user_id is None
            assert revoked.certified_at is None

            revoke_audit = await db.scalar(
                select(AuditEvent)
                .where(
                    AuditEvent.resource_id == dataset_id,
                    AuditEvent.event_type == "dataset.certification.revoked",
                )
                .order_by(AuditEvent.occurred_at.desc())
            )
            assert revoke_audit is not None
    finally:
        async with database.session_factory() as db:
            if org_id is not None:
                await db.execute(
                    delete(ResourceAccessEntry).where(ResourceAccessEntry.organization_id == org_id)
                )
                await db.execute(delete(AuditEvent).where(AuditEvent.organization_id == org_id))
                await db.execute(delete(Dataset).where(Dataset.organization_id == org_id))
                await db.execute(delete(Connection).where(Connection.organization_id == org_id))
                await db.execute(delete(Organization).where(Organization.id == org_id))
            for uid in user_ids:
                await db.execute(delete(User).where(User.id == uid))
            await db.commit()
        await database.dispose()
