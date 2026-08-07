"""Integration coverage for the post-Core beta connectors (Part A).

Proves a newly-enabled beta connector (s3) can be created, tested (via an
injected tester), and read back with secrets masked, all under tenant scope;
and that a still-planned connector remains create-blocked.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select

from vip_api.auth.models import User, UserStatus, utc_now
from vip_api.connections.crypto import TestEncryptionKeyProvider
from vip_api.connections.schemas import ConnectionCreateRequest
from vip_api.connections.secrets import DatabaseEncryptedSecretProvider
from vip_api.connections.seed import seed_connection_types
from vip_api.connections.services import create_connection, get_connection
from vip_api.connections.services import test_connection as run_connection_test
from vip_api.connections.testers import ConnectionTesterRegistry, TesterResult
from vip_api.core.config import Settings
from vip_api.core.errors import ApplicationError
from vip_api.database.session import Database
from vip_api.governance.models import Role
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

_SECRET = "s3-secret-key-value-unique"


class _S3Ok:
    async def test(
        self, configuration: dict[str, object], credentials: dict[str, str]
    ) -> TesterResult:
        assert configuration["bucket"] == "analytics-lake"
        assert credentials["secret_access_key"] == _SECRET
        return TesterResult(True, "healthy", 9)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_new_connector_create_test_and_secret_safety(settings: Settings) -> None:
    database = Database(settings)
    provider = DatabaseEncryptedSecretProvider(TestEncryptionKeyProvider())
    try:
        async with database.session_factory() as db:
            await seed_system_governance(db)
            await seed_connection_types(db)
            roles = {r.key: r for r in (await db.scalars(select(Role))).all()}
            admin = User(
                username=f"conn-{uuid4().hex[:8]}",
                normalized_username=f"conn-{uuid4().hex[:8]}",
                email=f"conn-{uuid4().hex[:8]}@vip.test",
                normalized_email=f"conn-{uuid4().hex[:8]}@vip.test",
                password_hash="unused",
                display_name="Conn Admin",
                status=UserStatus.ACTIVE,
            )
            db.add(admin)
            await db.flush()
            org = Organization(
                name="ConnOrg",
                slug=f"conn-org-{uuid4().hex[:8]}",
                status=OrganizationStatus.ACTIVE,
                created_by_user_id=admin.id,
            )
            db.add(org)
            await db.flush()
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
            org_m = OrganizationMembership(
                organization_id=org.id,
                user_id=admin.id,
                role_id=roles["organization_admin"].id,
                status=MembershipStatus.ACTIVE,
                joined_at=utc_now(),
            )
            ws_m = WorkspaceMembership(
                organization_id=org.id,
                workspace_id=ws.id,
                user_id=admin.id,
                role_id=roles["workspace_admin"].id,
                status=MembershipStatus.ACTIVE,
            )
            db.add_all([org_m, ws_m])
            await db.commit()

            context = await resolve_authorization_context(
                db,
                TenantContext(
                    user_id=admin.id,
                    organization_id=org.id,
                    workspace_id=ws.id,
                    organization_membership_id=org_m.id,
                    workspace_membership_id=ws_m.id,
                    organization_role="organization_admin",
                    workspace_role="workspace_admin",
                    correlation_id="new-connector-test",
                ),
            )

            # A newly-enabled beta connector (s3) is creatable.
            created = await create_connection(
                db,
                context,
                ConnectionCreateRequest(
                    name="Lake",
                    connection_type="s3",
                    configuration={"bucket": "analytics-lake", "region": "eu-west-1"},
                    credentials={"access_key_id": "AKIAEXAMPLE", "secret_access_key": _SECRET},
                ),
                settings,
                provider,
            )
            serialized = created.model_dump_json()
            assert _SECRET not in serialized and "AKIAEXAMPLE" not in serialized

            # It can be tested (tester injected — no real AWS needed).
            registry = ConnectionTesterRegistry(settings)
            registry.replace("s3", _S3Ok())
            tested = await run_connection_test(db, context, created.id, provider, registry)
            assert tested.status == "success" and tested.health_status == "healthy"

            # Read-back never exposes the secret.
            fetched = await get_connection(db, context, created.id)
            assert _SECRET not in fetched.model_dump_json()

            # A still-planned connector cannot be created (fail-closed gate intact).
            with pytest.raises(ApplicationError) as blocked:
                await create_connection(
                    db,
                    context,
                    ConnectionCreateRequest(
                        name="Nope",
                        connection_type="oracle",
                        configuration={"host": "h", "database": "d", "username": "u"},
                        credentials={"password": "x"},
                    ),
                    settings,
                    provider,
                )
            assert blocked.value.code in {"CONNECTION_TYPE_DISABLED", "VALIDATION_ERROR"}
    finally:
        await database.engine.dispose()
