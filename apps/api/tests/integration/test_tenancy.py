"""Two-tenant authorization, membership, invitation, and repository security tests."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from dataclasses import dataclass
from uuid import UUID

import pytest
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from starlette.testclient import TestClient

from vip_api.auth.models import AuthSession, PasswordResetToken, User, UserStatus, utc_now
from vip_api.auth.password import PasswordService
from vip_api.core.config import Settings
from vip_api.database.session import Database
from vip_api.governance.models import AuditEvent, OrganizationQuota, QuotaDefinition, Role
from vip_api.main import create_application
from vip_api.tenancy.models import (
    Invitation,
    InvitationWorkspace,
    MembershipStatus,
    Organization,
    OrganizationMembership,
    OrganizationStatus,
    Workspace,
    WorkspaceMembership,
    WorkspaceStatus,
)
from vip_api.tenancy.repositories import WorkspaceRepository

PASSWORD = "Tenant test passphrase 2026"


@dataclass(frozen=True)
class TenantFixture:
    users: dict[str, UUID]
    organizations: dict[str, UUID]
    workspaces: dict[str, UUID]
    memberships: dict[str, UUID]


async def reset_all(settings: Settings) -> None:
    database = Database(settings)
    try:
        async with database.session_factory() as db:
            for model in (
                InvitationWorkspace,
                Invitation,
                WorkspaceMembership,
                OrganizationMembership,
                Workspace,
                Organization,
                PasswordResetToken,
                AuthSession,
                User,
            ):
                await db.execute(delete(model))
            await db.commit()
    finally:
        await database.dispose()


async def seed_fixture(settings: Settings) -> TenantFixture:
    database = Database(settings)
    password_hash = PasswordService(settings).hash_password(PASSWORD)
    try:
        async with database.session_factory() as db:
            roles = {role.key: role.id for role in (await db.scalars(select(Role))).all()}
            users = {
                key: User(
                    email=f"user-{key}@tenant.test",
                    normalized_email=f"user-{key}@tenant.test",
                    password_hash=password_hash,
                    display_name=f"User {key.upper()}",
                    status=UserStatus.ACTIVE,
                )
                for key in ("a", "b", "c", "d", "e", "f")
            }
            db.add_all(users.values())
            await db.flush()
            organizations = {
                "alpha": Organization(
                    name="Organization Alpha",
                    slug="alpha",
                    status=OrganizationStatus.ACTIVE,
                    created_by_user_id=users["a"].id,
                ),
                "beta": Organization(
                    name="Organization Beta",
                    slug="beta",
                    status=OrganizationStatus.ACTIVE,
                    created_by_user_id=users["b"].id,
                ),
            }
            db.add_all(organizations.values())
            await db.flush()
            org_members = {
                "a-alpha": OrganizationMembership(
                    organization_id=organizations["alpha"].id,
                    user_id=users["a"].id,
                    role_id=roles["organization_owner"],
                    status=MembershipStatus.ACTIVE,
                    joined_at=utc_now(),
                ),
                "b-beta": OrganizationMembership(
                    organization_id=organizations["beta"].id,
                    user_id=users["b"].id,
                    role_id=roles["organization_owner"],
                    status=MembershipStatus.ACTIVE,
                    joined_at=utc_now(),
                ),
                "c-alpha": OrganizationMembership(
                    organization_id=organizations["alpha"].id,
                    user_id=users["c"].id,
                    role_id=roles["organization_member"],
                    status=MembershipStatus.ACTIVE,
                    joined_at=utc_now(),
                ),
                "c-beta": OrganizationMembership(
                    organization_id=organizations["beta"].id,
                    user_id=users["c"].id,
                    role_id=roles["organization_member"],
                    status=MembershipStatus.ACTIVE,
                    joined_at=utc_now(),
                ),
            }
            db.add_all(org_members.values())
            workspaces: dict[str, Workspace] = {}
            for org_key in ("alpha", "beta"):
                for number in (1, 2):
                    key = f"{org_key}{number}"
                    workspaces[key] = Workspace(
                        organization_id=organizations[org_key].id,
                        name=f"{org_key.title()} Workspace {number}",
                        slug=f"workspace-{number}",
                        status=WorkspaceStatus.ACTIVE,
                        is_default=number == 1,
                        created_by_user_id=users["a" if org_key == "alpha" else "b"].id,
                    )
            db.add_all(workspaces.values())
            await db.flush()
            workspace_access = []
            for key in ("alpha1", "alpha2"):
                workspace_access.append(
                    WorkspaceMembership(
                        organization_id=organizations["alpha"].id,
                        workspace_id=workspaces[key].id,
                        user_id=users["a"].id,
                        role_id=roles["workspace_admin"],
                        status=MembershipStatus.ACTIVE,
                    )
                )
            for key in ("beta1", "beta2"):
                workspace_access.append(
                    WorkspaceMembership(
                        organization_id=organizations["beta"].id,
                        workspace_id=workspaces[key].id,
                        user_id=users["b"].id,
                        role_id=roles["workspace_admin"],
                        status=MembershipStatus.ACTIVE,
                    )
                )
            for org_key, workspace_key in (("alpha", "alpha1"), ("beta", "beta2")):
                workspace_access.append(
                    WorkspaceMembership(
                        organization_id=organizations[org_key].id,
                        workspace_id=workspaces[workspace_key].id,
                        user_id=users["c"].id,
                        role_id=roles["viewer"],
                        status=MembershipStatus.ACTIVE,
                    )
                )
            db.add_all(workspace_access)
            workspace_quota = await db.scalar(
                select(QuotaDefinition).where(QuotaDefinition.key == "workspaces.max")
            )
            assert workspace_quota is not None
            db.add_all(
                OrganizationQuota(
                    organization_id=organization.id,
                    quota_id=workspace_quota.id,
                    limit_value=25,
                    source="system",
                )
                for organization in organizations.values()
            )
            await db.commit()
            return TenantFixture(
                users={key: value.id for key, value in users.items()},
                organizations={key: value.id for key, value in organizations.items()},
                workspaces={key: value.id for key, value in workspaces.items()},
                memberships={key: value.id for key, value in org_members.items()},
            )
    finally:
        await database.dispose()


@pytest.fixture
def tenant_setup(settings: Settings) -> Iterator[tuple[TenantFixture, dict[str, TestClient]]]:
    asyncio.run(reset_all(settings))
    fixture = asyncio.run(seed_fixture(settings))
    clients = {
        key: TestClient(create_application(settings), raise_server_exceptions=False)
        for key in ("a", "b", "c", "d", "e", "f")
    }
    for key, client in clients.items():
        client.__enter__()
        response = client.post(
            "/auth/login", json={"email": f"user-{key}@tenant.test", "password": PASSWORD}
        )
        assert response.status_code == 200
    clients["a"].headers["X-Organization-ID"] = str(fixture.organizations["alpha"])
    clients["b"].headers["X-Organization-ID"] = str(fixture.organizations["beta"])
    clients["c"].headers["X-Organization-ID"] = str(fixture.organizations["alpha"])
    try:
        yield fixture, clients
    finally:
        for client in clients.values():
            client.__exit__(None, None, None)


def csrf(client: TestClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("vip_csrf_token") or ""}


@pytest.mark.integration
def test_organization_and_workspace_access_matrix(
    tenant_setup: tuple[TenantFixture, dict[str, TestClient]],
) -> None:
    fixture, clients = tenant_setup
    alpha = fixture.organizations["alpha"]
    beta = fixture.organizations["beta"]
    assert [item["id"] for item in clients["a"].get("/api/v1/organizations").json()["items"]] == [
        str(alpha)
    ]
    assert clients["a"].get(f"/api/v1/organizations/{beta}").status_code == 404
    assert "Beta" not in clients["a"].get(f"/api/v1/organizations/{beta}").text
    assert clients["b"].get(f"/api/v1/organizations/{alpha}").status_code == 404

    matrix = (
        ("a", "alpha", "alpha1", 200),
        ("a", "alpha", "alpha2", 200),
        ("a", "beta", "beta1", 404),
        ("a", "alpha", "beta1", 404),
        ("b", "beta", "beta1", 200),
        ("b", "alpha", "alpha1", 404),
        ("c", "alpha", "alpha1", 200),
        ("c", "alpha", "alpha2", 404),
        ("c", "beta", "beta2", 200),
        ("c", "beta", "beta1", 404),
    )
    for actor, org_key, workspace_key, expected in matrix:
        response = clients[actor].get(
            "/api/v1/tenant-context",
            headers={
                "X-Organization-ID": str(fixture.organizations[org_key]),
                "X-Workspace-ID": str(fixture.workspaces[workspace_key]),
            },
        )
        assert response.status_code == expected, (actor, org_key, workspace_key, response.text)
        if expected == 200:
            assert response.json()["organization_id"] == str(fixture.organizations[org_key])
            assert response.json()["workspace_id"] == str(fixture.workspaces[workspace_key])

    alpha_for_c = clients["c"].get(f"/api/v1/organizations/{alpha}/workspaces").json()["items"]
    beta_for_c = (
        clients["c"]
        .get(
            f"/api/v1/organizations/{beta}/workspaces",
            headers={"X-Organization-ID": str(beta)},
        )
        .json()["items"]
    )
    assert [item["id"] for item in alpha_for_c] == [str(fixture.workspaces["alpha1"])]
    assert [item["id"] for item in beta_for_c] == [str(fixture.workspaces["beta2"])]


@pytest.mark.integration
def test_audit_api_returns_live_traceable_events(
    tenant_setup: tuple[TenantFixture, dict[str, TestClient]], settings: Settings
) -> None:
    fixture, clients = tenant_setup
    organization_id = fixture.organizations["alpha"]

    async def seed_audit_event() -> None:
        database = Database(settings)
        try:
            async with database.session_factory() as db:
                db.add(
                    AuditEvent(
                        actor_user_id=fixture.users["a"],
                        organization_id=organization_id,
                        workspace_id=fixture.workspaces["alpha1"],
                        correlation_id="audit-api-contract",
                        event_type="workspace.updated",
                        action="workspace.updated",
                        resource_type="workspace",
                        resource_id=fixture.workspaces["alpha1"],
                        outcome="success",
                        event_metadata={"safe": True},
                    )
                )
                await db.commit()
        finally:
            await database.dispose()

    asyncio.run(seed_audit_event())

    response = clients["a"].get(
        "/api/v1/audit-events",
        headers={
            "X-Organization-ID": str(organization_id),
            "X-Workspace-ID": str(fixture.workspaces["alpha1"]),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["limit"] == 50
    assert payload["offset"] == 0
    assert payload["items"]
    event = payload["items"][0]
    assert event["organization_id"] == str(organization_id)
    assert event["correlation_id"]
    assert event["event_type"]
    assert event["action"]


@pytest.mark.integration
def test_creation_updates_cross_tenant_denial_and_last_owner(
    tenant_setup: tuple[TenantFixture, dict[str, TestClient]], settings: Settings
) -> None:
    fixture, clients = tenant_setup
    created = clients["d"].post(
        "/api/v1/organizations",
        json={"name": "Delta Corp", "slug": "delta-corp"},
        headers=csrf(clients["d"]),
    )
    assert created.status_code == 201
    assert created.json()["organization"]["membership"]["role"] == "organization_owner"
    assert created.json()["default_workspace"]["is_default"] is True

    alpha = fixture.organizations["alpha"]
    beta = fixture.organizations["beta"]
    denied = clients["a"].patch(
        f"/api/v1/organizations/{beta}",
        json={"name": "Leaked"},
        headers=csrf(clients["a"]),
    )
    assert denied.status_code == 404 and "Beta" not in denied.text
    denied_delete = clients["a"].delete(
        f"/api/v1/organizations/{beta}/members/{fixture.memberships['b-beta']}",
        headers=csrf(clients["a"]),
    )
    assert denied_delete.status_code == 404
    self_role = clients["a"].patch(
        f"/api/v1/organizations/{alpha}/members/{fixture.memberships['a-alpha']}",
        json={"role": "organization_admin"},
        headers=csrf(clients["a"]),
    )
    assert self_role.status_code == 403
    assert self_role.json()["error"]["code"] == "SELF_ROLE_CHANGE_DENIED"
    invalid_org_scope = clients["a"].patch(
        f"/api/v1/organizations/{alpha}/members/{fixture.memberships['c-alpha']}",
        json={"role": "editor"},
        headers=csrf(clients["a"]),
    )
    assert invalid_org_scope.status_code == 422
    assert invalid_org_scope.json()["error"]["code"] == "ROLE_SCOPE_INVALID"
    invalid_workspace_scope = clients["a"].post(
        f"/api/v1/organizations/{alpha}/workspaces/{fixture.workspaces['alpha1']}/members",
        json={"user_id": str(fixture.users["c"]), "role": "organization_admin"},
        headers=csrf(clients["a"]),
    )
    assert invalid_workspace_scope.status_code == 422
    assert invalid_workspace_scope.json()["error"]["code"] == "ROLE_SCOPE_INVALID"
    last_owner = clients["a"].delete(
        f"/api/v1/organizations/{alpha}/members/{fixture.memberships['a-alpha']}",
        headers=csrf(clients["a"]),
    )
    assert last_owner.status_code == 409
    assert last_owner.json()["error"]["code"] == "LAST_OWNER_REQUIRED"

    workspace = clients["a"].post(
        f"/api/v1/organizations/{alpha}/workspaces",
        json={"name": "Extra", "slug": "extra"},
        headers=csrf(clients["a"]),
    )
    assert workspace.status_code == 201
    workspace_id = workspace.json()["id"]
    archived = clients["a"].patch(
        f"/api/v1/organizations/{alpha}/workspaces/{workspace_id}",
        json={"status": "archived"},
        headers=csrf(clients["a"]),
    )
    assert archived.status_code == 200
    active_items = clients["a"].get(f"/api/v1/organizations/{alpha}/workspaces").json()["items"]
    assert workspace_id not in {item["id"] for item in active_items}
    managed_items = (
        clients["a"]
        .get(f"/api/v1/organizations/{alpha}/workspaces?include_archived=true")
        .json()["items"]
    )
    assert (
        next(item for item in managed_items if item["id"] == workspace_id)["status"] == "archived"
    )
    denied_archived = clients["c"].get(
        f"/api/v1/organizations/{alpha}/workspaces?include_archived=true"
    )
    assert denied_archived.status_code == 403
    restored = clients["a"].patch(
        f"/api/v1/organizations/{alpha}/workspaces/{workspace_id}",
        json={"status": "active"},
        headers=csrf(clients["a"]),
    )
    assert restored.status_code == 200
    duplicate = clients["a"].post(
        f"/api/v1/organizations/{alpha}/workspaces",
        json={"name": "Extra 2", "slug": "extra"},
        headers=csrf(clients["a"]),
    )
    assert duplicate.status_code == 409


@pytest.mark.integration
def test_membership_removal_and_suspension_are_immediate(
    tenant_setup: tuple[TenantFixture, dict[str, TestClient]], settings: Settings
) -> None:
    fixture, clients = tenant_setup
    alpha = fixture.organizations["alpha"]
    beta = fixture.organizations["beta"]
    removed = clients["a"].delete(
        f"/api/v1/organizations/{alpha}/members/{fixture.memberships['c-alpha']}",
        headers=csrf(clients["a"]),
    )
    assert removed.status_code == 204
    assert clients["c"].get(f"/api/v1/organizations/{alpha}").status_code == 404
    assert (
        clients["c"]
        .get(
            f"/api/v1/organizations/{beta}",
            headers={"X-Organization-ID": str(beta)},
        )
        .status_code
        == 200
    )

    async def suspend_beta() -> None:
        database = Database(settings)
        try:
            async with database.session_factory() as db:
                await db.execute(
                    update(OrganizationMembership)
                    .where(OrganizationMembership.id == fixture.memberships["c-beta"])
                    .values(status=MembershipStatus.SUSPENDED)
                )
                await db.commit()
        finally:
            await database.dispose()

    asyncio.run(suspend_beta())
    assert (
        clients["c"]
        .get(
            f"/api/v1/organizations/{beta}",
            headers={"X-Organization-ID": str(beta)},
        )
        .status_code
        == 404
    )


@pytest.mark.integration
def test_invitation_hash_email_expiry_revocation_and_replay(
    tenant_setup: tuple[TenantFixture, dict[str, TestClient]], settings: Settings
) -> None:
    fixture, clients = tenant_setup
    alpha = fixture.organizations["alpha"]
    workspace_id = fixture.workspaces["alpha2"]
    response = clients["a"].post(
        f"/api/v1/organizations/{alpha}/invitations",
        json={"email": "user-d@tenant.test", "workspace_ids": [str(workspace_id)]},
        headers=csrf(clients["a"]),
    )
    assert response.status_code == 201
    token = response.json()["token"]
    assert token

    async def stored_invitation() -> Invitation:
        database = Database(settings)
        try:
            async with database.session_factory() as db:
                invitation = await db.scalar(
                    select(Invitation).where(Invitation.id == response.json()["id"])
                )
                assert invitation is not None
                assert invitation.token_hash != token
                return invitation
        finally:
            await database.dispose()

    asyncio.run(stored_invitation())
    mismatch = clients["c"].post(
        "/api/v1/invitations/accept", json={"token": token}, headers=csrf(clients["c"])
    )
    assert mismatch.status_code == 403
    accepted = clients["d"].post(
        "/api/v1/invitations/accept", json={"token": token}, headers=csrf(clients["d"])
    )
    assert accepted.status_code == 200
    assert accepted.json()["workspace_ids"] == [str(workspace_id)]
    replay = clients["d"].post(
        "/api/v1/invitations/accept", json={"token": token}, headers=csrf(clients["d"])
    )
    assert replay.status_code == 410

    expired_response = clients["a"].post(
        f"/api/v1/organizations/{alpha}/invitations",
        json={"email": "user-e@tenant.test", "workspace_ids": [str(workspace_id)]},
        headers=csrf(clients["a"]),
    )
    assert expired_response.status_code == 201
    expired_token = expired_response.json()["token"]

    async def expire_invitation() -> None:
        database = Database(settings)
        try:
            async with database.session_factory() as db:
                await db.execute(
                    update(Invitation)
                    .where(Invitation.id == UUID(expired_response.json()["id"]))
                    .values(expires_at=utc_now())
                )
                await db.commit()
        finally:
            await database.dispose()

    asyncio.run(expire_invitation())
    expired = clients["e"].post(
        "/api/v1/invitations/accept",
        json={"token": expired_token},
        headers=csrf(clients["e"]),
    )
    assert expired.status_code == 410
    assert expired.json()["error"]["code"] == "INVITATION_EXPIRED"

    revoked_response = clients["a"].post(
        f"/api/v1/organizations/{alpha}/invitations",
        json={"email": "user-f@tenant.test", "workspace_ids": [str(workspace_id)]},
        headers=csrf(clients["a"]),
    )
    assert revoked_response.status_code == 201
    revoked_token = revoked_response.json()["token"]
    revoked = clients["a"].delete(
        f"/api/v1/organizations/{alpha}/invitations/{revoked_response.json()['id']}",
        headers=csrf(clients["a"]),
    )
    assert revoked.status_code == 204
    rejected = clients["f"].post(
        "/api/v1/invitations/accept",
        json={"token": revoked_token},
        headers=csrf(clients["f"]),
    )
    assert rejected.status_code == 410
    assert rejected.json()["error"]["code"] == "INVITATION_REVOKED"


@pytest.mark.integration
def test_repository_methods_are_tenant_filtered(
    tenant_setup: tuple[TenantFixture, dict[str, TestClient]], settings: Settings
) -> None:
    fixture, _clients = tenant_setup

    async def exercise() -> None:
        database = Database(settings)
        try:
            async with database.session_factory() as db:
                repository = WorkspaceRepository(db)
                assert await repository.count_for_tenant(fixture.organizations["alpha"]) == 2
                affected = await repository.tenant_filtered_update(
                    fixture.organizations["beta"],
                    fixture.workspaces["alpha1"],
                    {"name": "Must not change"},
                )
                assert affected == 0
                deleted = await repository.tenant_filtered_delete(
                    fixture.organizations["beta"], fixture.workspaces["alpha1"]
                )
                assert deleted == 0
                await db.rollback()
                assert not hasattr(repository, "get_by_id")
                assert not hasattr(repository, "list_all")

                db.add(
                    WorkspaceMembership(
                        organization_id=fixture.organizations["beta"],
                        workspace_id=fixture.workspaces["alpha1"],
                        user_id=fixture.users["b"],
                        role_id=(await db.scalar(select(Role.id).where(Role.key == "viewer"))),
                        status=MembershipStatus.ACTIVE,
                    )
                )
                with pytest.raises(IntegrityError):
                    await db.flush()
                await db.rollback()
        finally:
            await database.dispose()

    asyncio.run(exercise())
