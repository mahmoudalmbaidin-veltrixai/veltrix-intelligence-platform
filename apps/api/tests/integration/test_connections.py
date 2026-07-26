"""Connection CRUD, encrypted secrets, testing, governance, and tenant isolation."""

from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.auth.models import User, UserStatus, utc_now
from vip_api.connections.crypto import TestEncryptionKeyProvider
from vip_api.connections.models import Connection, ConnectionSecret
from vip_api.connections.schemas import ConnectionCreateRequest, CredentialReplaceRequest
from vip_api.connections.secrets import DatabaseEncryptedSecretProvider, SecretProviderError
from vip_api.connections.seed import seed_connection_types
from vip_api.connections.services import (
    create_connection,
    get_connection,
    replace_credentials,
)
from vip_api.connections.services import (
    test_connection as run_connection_test,
)
from vip_api.connections.testers import ConnectionTesterRegistry, TesterResult
from vip_api.core.config import Settings
from vip_api.core.errors import ApplicationError
from vip_api.database.session import Database
from vip_api.governance.context import QuotaSnapshot
from vip_api.governance.models import AuditEvent
from vip_api.governance.seed import provision_organization_governance, seed_system_governance
from vip_api.governance.services import resolve_authorization_context
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


class SuccessfulTester:
    async def test(
        self, configuration: dict[str, object], credentials: dict[str, str]
    ) -> TesterResult:
        assert configuration["database"] == "analytics"
        assert credentials["password"] == "B4-unique-secret"
        return TesterResult(True, "healthy", 12)


class FailingStoreSecretProvider(DatabaseEncryptedSecretProvider):
    async def store_secret(
        self,
        db: AsyncSession,
        *,
        organization_id: UUID,
        workspace_id: UUID,
        connection_id: UUID,
        credential_version: int,
        credentials: dict[str, str],
        actor_user_id: UUID,
    ) -> ConnectionSecret:
        raise SecretProviderError("Simulated provider failure")


@pytest.mark.integration
@pytest.mark.security
@pytest.mark.asyncio
async def test_connection_secret_safety_governance_testing_and_tenant_isolation(
    settings: Settings,
) -> None:
    database = Database(settings)
    provider = DatabaseEncryptedSecretProvider(TestEncryptionKeyProvider())
    try:
        async with database.session_factory() as db:
            await db.execute(delete(Organization))
            await db.execute(delete(User))
            await db.commit()
            await seed_system_governance(db)
            await seed_connection_types(db)
            from vip_api.governance.models import Role

            roles = {item.key: item for item in (await db.scalars(select(Role))).all()}
            admin = User(
                email="b4-admin@test.local",
                normalized_email="b4-admin@test.local",
                password_hash="unused",
                display_name="B4 Admin",
                status=UserStatus.ACTIVE,
            )
            viewer = User(
                email="b4-viewer@test.local",
                normalized_email="b4-viewer@test.local",
                password_hash="unused",
                display_name="B4 Viewer",
                status=UserStatus.ACTIVE,
            )
            db.add_all([admin, viewer])
            await db.flush()
            alpha = Organization(
                name="B4 Alpha",
                slug=f"b4-alpha-{uuid4().hex[:8]}",
                status=OrganizationStatus.ACTIVE,
                created_by_user_id=admin.id,
            )
            beta = Organization(
                name="B4 Beta",
                slug=f"b4-beta-{uuid4().hex[:8]}",
                status=OrganizationStatus.ACTIVE,
                created_by_user_id=admin.id,
            )
            db.add_all([alpha, beta])
            await db.flush()
            alpha_ws = Workspace(
                organization_id=alpha.id,
                name="Alpha",
                slug="alpha",
                status=WorkspaceStatus.ACTIVE,
                is_default=True,
                created_by_user_id=admin.id,
            )
            beta_ws = Workspace(
                organization_id=beta.id,
                name="Beta",
                slug="beta",
                status=WorkspaceStatus.ACTIVE,
                is_default=True,
                created_by_user_id=admin.id,
            )
            db.add_all([alpha_ws, beta_ws])
            await db.flush()
            admin_org = OrganizationMembership(
                organization_id=alpha.id,
                user_id=admin.id,
                role_id=roles["organization_admin"].id,
                status=MembershipStatus.ACTIVE,
                joined_at=utc_now(),
            )
            admin_ws = WorkspaceMembership(
                organization_id=alpha.id,
                workspace_id=alpha_ws.id,
                user_id=admin.id,
                role_id=roles["workspace_admin"].id,
                status=MembershipStatus.ACTIVE,
            )
            viewer_org = OrganizationMembership(
                organization_id=alpha.id,
                user_id=viewer.id,
                role_id=roles["organization_member"].id,
                status=MembershipStatus.ACTIVE,
                joined_at=utc_now(),
            )
            viewer_ws = WorkspaceMembership(
                organization_id=alpha.id,
                workspace_id=alpha_ws.id,
                user_id=viewer.id,
                role_id=roles["viewer"].id,
                status=MembershipStatus.ACTIVE,
            )
            beta_org = OrganizationMembership(
                organization_id=beta.id,
                user_id=admin.id,
                role_id=roles["organization_admin"].id,
                status=MembershipStatus.ACTIVE,
                joined_at=utc_now(),
            )
            beta_member = WorkspaceMembership(
                organization_id=beta.id,
                workspace_id=beta_ws.id,
                user_id=admin.id,
                role_id=roles["workspace_admin"].id,
                status=MembershipStatus.ACTIVE,
            )
            db.add_all([admin_org, admin_ws, viewer_org, viewer_ws, beta_org, beta_member])
            await provision_organization_governance(db, alpha.id)
            await provision_organization_governance(db, beta.id)
            await db.commit()

            def tenant(
                user: User,
                org: Organization,
                workspace: Workspace,
                org_membership: OrganizationMembership,
                ws_membership: WorkspaceMembership,
                org_role: str,
                ws_role: str,
            ) -> TenantContext:
                return TenantContext(
                    user_id=user.id,
                    organization_id=org.id,
                    workspace_id=workspace.id,
                    organization_membership_id=org_membership.id,
                    workspace_membership_id=ws_membership.id,
                    organization_role=org_role,
                    workspace_role=ws_role,
                    correlation_id="b4-security",
                )

            admin_context = await resolve_authorization_context(
                db,
                tenant(
                    admin,
                    alpha,
                    alpha_ws,
                    admin_org,
                    admin_ws,
                    "organization_admin",
                    "workspace_admin",
                ),
            )
            viewer_context = await resolve_authorization_context(
                db,
                tenant(
                    viewer, alpha, alpha_ws, viewer_org, viewer_ws, "organization_member", "viewer"
                ),
            )
            beta_context = await resolve_authorization_context(
                db,
                tenant(
                    admin,
                    beta,
                    beta_ws,
                    beta_org,
                    beta_member,
                    "organization_admin",
                    "workspace_admin",
                ),
            )
            payload = ConnectionCreateRequest(
                name="Analytics PostgreSQL",
                description="Safe test",
                connection_type="postgresql",
                configuration={
                    "host": "db.example.com",
                    "database": "analytics",
                    "username": "reader",
                },
                credentials={"password": "B4-unique-secret"},
            )
            disabled_context = replace(
                admin_context,
                feature_flags={**admin_context.feature_flags, "connection_studio": False},
            )
            with pytest.raises(ApplicationError) as feature_denial:
                await create_connection(db, disabled_context, payload, settings, provider)
            assert feature_denial.value.code == "FEATURE_DISABLED"
            unentitled_context = replace(
                admin_context,
                entitlements=admin_context.entitlements - {"connection_studio"},
            )
            with pytest.raises(ApplicationError) as entitlement_denial:
                await create_connection(db, unentitled_context, payload, settings, provider)
            assert entitlement_denial.value.code == "ENTITLEMENT_REQUIRED"
            exhausted_context = replace(
                admin_context,
                quotas={
                    **admin_context.quotas,
                    "connections.max": QuotaSnapshot(
                        limit=0, used=0, reserved=0, remaining=0, hard=True
                    ),
                },
            )
            with pytest.raises(ApplicationError) as quota_denial:
                await create_connection(db, exhausted_context, payload, settings, provider)
            assert quota_denial.value.code == "QUOTA_EXCEEDED"
            created = await create_connection(db, admin_context, payload, settings, provider)
            serialized = created.model_dump_json()
            assert "B4-unique-secret" not in serialized
            assert "ciphertext" not in serialized and "nonce" not in serialized
            row = await db.get(Connection, created.id)
            assert row is not None and "B4-unique-secret" not in str(row.configuration)
            secret = await db.get(ConnectionSecret, row.secret_id)
            assert secret is not None and b"B4-unique-secret" not in secret.ciphertext
            assert secret.nonce and secret.encryption_algorithm == "AES-256-GCM"
            with pytest.raises(ApplicationError) as viewer_denial:
                await create_connection(db, viewer_context, payload, settings, provider)
            assert viewer_denial.value.code == "PERMISSION_DENIED"
            with pytest.raises(ApplicationError) as cross_tenant:
                await get_connection(db, beta_context, created.id)
            assert cross_tenant.value.code == "CONNECTION_NOT_FOUND"
            with pytest.raises(SecretProviderError):
                await provider.read_secret(
                    db,
                    organization_id=beta.id,
                    workspace_id=beta_ws.id,
                    connection_id=created.id,
                    secret_id=secret.id,
                )
            registry = ConnectionTesterRegistry(settings)
            registry.replace("postgresql", SuccessfulTester())
            tested = await run_connection_test(db, admin_context, created.id, provider, registry)
            assert tested.status == "success" and tested.health_status == "healthy"
            alpha_id = alpha.id
            alpha_workspace_id = alpha_ws.id
            connection_id = created.id
            original_secret_id = row.secret_id
            assert original_secret_id is not None
            original_credential_version = row.credential_version
            with pytest.raises(SecretProviderError):
                await replace_credentials(
                    db,
                    admin_context,
                    created.id,
                    CredentialReplaceRequest(
                        credentials={"password": "replacement-secret"},
                        expected_version=row.version,
                    ),
                    settings,
                    FailingStoreSecretProvider(TestEncryptionKeyProvider()),
                    rotated=True,
                )
            await db.rollback()
            preserved = await db.get(Connection, connection_id)
            assert preserved is not None
            assert preserved.secret_id == original_secret_id
            assert preserved.credential_version == original_credential_version
            resolved = await provider.read_secret(
                db,
                organization_id=alpha_id,
                workspace_id=alpha_workspace_id,
                connection_id=connection_id,
                secret_id=original_secret_id,
            )
            assert resolved["password"] == "B4-unique-secret"
            audit_payload = " ".join(
                str(item.event_metadata)
                for item in (
                    await db.scalars(
                        select(AuditEvent).where(AuditEvent.organization_id == alpha_id)
                    )
                ).all()
            )
            assert "B4-unique-secret" not in audit_payload
    finally:
        await database.dispose()
