"""Small management CLI for authentication operations."""

from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import secrets
import sys
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select

from vip_api.auth.authentication import normalize_email
from vip_api.auth.models import User, UserStatus, utc_now
from vip_api.auth.password import PasswordService
from vip_api.auth.sessions import cleanup_expired_sessions, revoke_all_user_sessions
from vip_api.connections.seed import seed_connection_types as sync_connection_types
from vip_api.core.config import get_settings
from vip_api.dashboards.seed import seed_dashboard_demo as sync_dashboard_demo
from vip_api.database.session import Database
from vip_api.datasets.seed import seed_dataset_catalogs as sync_dataset_catalogs
from vip_api.governance.models import (
    FeatureFlag,
    FeatureFlagOverride,
    OrganizationQuota,
    QuotaDefinition,
    QuotaUsage,
)
from vip_api.governance.seed import provision_organization_governance, seed_system_governance
from vip_api.governance.services import get_role
from vip_api.semantic.seed import seed_semantic_layer as sync_semantic_layer
from vip_api.tenancy.models import (
    Invitation,
    InvitationStatus,
    MembershipStatus,
    Organization,
    OrganizationMembership,
    OrganizationStatus,
    Workspace,
    WorkspaceMembership,
    WorkspaceStatus,
)
from vip_api.tenancy.services import invitation_token_hash


def read_password(*, password_stdin: bool) -> str:
    if password_stdin:
        password = sys.stdin.readline().rstrip("\r\n")
        if not password:
            raise SystemExit("A password is required on standard input.")
        return password
    password = getpass.getpass("Password: ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match.")
    return password


async def create_user(email: str, display_name: str, *, password_stdin: bool = False) -> None:
    settings = get_settings()
    password = read_password(password_stdin=password_stdin)
    password_service = PasswordService(settings)
    password_hash = password_service.hash_password(password)
    database = Database(settings)
    try:
        async with database.session_factory() as db:
            normalized = normalize_email(email)
            if await db.scalar(select(User.id).where(User.normalized_email == normalized)):
                raise SystemExit("A user with that email already exists.")
            db.add(
                User(
                    email=email.strip(),
                    normalized_email=normalized,
                    display_name=display_name.strip(),
                    password_hash=password_hash,
                    status=UserStatus.ACTIVE,
                )
            )
            await db.commit()
    finally:
        await database.dispose()
    print("User created successfully.")


async def revoke_user_sessions(email: str) -> None:
    settings = get_settings()
    database = Database(settings)
    try:
        async with database.session_factory() as db:
            user_id = await db.scalar(
                select(User.id).where(User.normalized_email == normalize_email(email))
            )
            if user_id is None:
                raise SystemExit("No user exists with that email.")
            revoked = await revoke_all_user_sessions(db, user_id, "operator_revocation")
            await db.commit()
    finally:
        await database.dispose()
    print(f"Revoked {revoked} active session(s).")


async def cleanup_sessions() -> None:
    settings = get_settings()
    database = Database(settings)
    try:
        async with database.session_factory() as db:
            removed = await cleanup_expired_sessions(db)
            await db.commit()
    finally:
        await database.dispose()
    print(f"Removed {removed} expired session(s).")


async def seed_governance() -> None:
    settings = get_settings()
    database = Database(settings)
    try:
        async with database.session_factory() as db:
            await seed_system_governance(db)
    finally:
        await database.dispose()
    print("System governance definitions synchronized.")


async def seed_connection_types() -> None:
    database = Database(get_settings())
    try:
        async with database.session_factory() as db:
            await sync_connection_types(db)
    finally:
        await database.dispose()
    print("System connection-type definitions synchronized.")


async def seed_dataset_catalogs() -> None:
    require_nonproduction()
    settings = get_settings()
    password = os.getenv("B5_DEMO_POSTGRES_PASSWORD")
    if not password:
        raise SystemExit("Set B5_DEMO_POSTGRES_PASSWORD in the process environment.")
    database = Database(settings)
    try:
        async with database.session_factory() as db:
            await sync_dataset_catalogs(db, settings, password)
    finally:
        await database.dispose()
    print("B5 dataset catalog is ready (credentials were not printed).")


async def seed_semantic_layer() -> None:
    require_nonproduction()
    database = Database(get_settings())
    try:
        async with database.session_factory() as db:
            await sync_semantic_layer(db)
    finally:
        await database.dispose()
    print("B5 semantic layer is ready.")


async def seed_dashboard_governance() -> None:
    await seed_governance()


async def seed_dashboard_demo() -> None:
    require_nonproduction()
    database = Database(get_settings())
    try:
        async with database.session_factory() as db:
            await sync_dashboard_demo(db)
    finally:
        await database.dispose()
    print("B6 Dashboard Studio demo is ready.")


def require_nonproduction() -> None:
    settings = get_settings()
    if settings.APP_ENV.value not in {"development", "test"}:
        raise SystemExit("This command is available only in development and test environments.")


async def seed_multitenancy_demo() -> None:
    require_nonproduction()
    settings = get_settings()
    passwords = {
        "a": os.getenv("VIP_DEMO_USER_A_PASSWORD"),
        "b": os.getenv("VIP_DEMO_USER_B_PASSWORD"),
        "c": os.getenv("VIP_DEMO_USER_C_PASSWORD"),
    }
    if any(not value for value in passwords.values()):
        raise SystemExit(
            "Set VIP_DEMO_USER_A_PASSWORD, VIP_DEMO_USER_B_PASSWORD, and "
            "VIP_DEMO_USER_C_PASSWORD without placing secrets in command arguments."
        )
    password_service = PasswordService(settings)
    database = Database(settings)
    try:
        async with database.session_factory() as db:
            users: dict[str, User] = {}
            for key, email, name in (
                ("a", "tenant-a@vip.demo", "Tenant User A"),
                ("b", "tenant-b@vip.demo", "Tenant User B"),
                ("c", "tenant-c@vip.demo", "Tenant User C"),
            ):
                user = await db.scalar(select(User).where(User.normalized_email == email))
                if user is None:
                    password = passwords[key]
                    assert password is not None
                    user = User(
                        email=email,
                        normalized_email=email,
                        display_name=name,
                        password_hash=password_service.hash_password(password),
                        status=UserStatus.ACTIVE,
                    )
                    db.add(user)
                    await db.flush()
                else:
                    password = passwords[key]
                    assert password is not None
                    user.password_hash = password_service.hash_password(password)
                    user.status = UserStatus.ACTIVE
                users[key] = user

            organizations: dict[str, Organization] = {}
            for key, name, slug, owner_key in (
                ("alpha", "Organization Alpha", "demo-alpha", "a"),
                ("beta", "Organization Beta", "demo-beta", "b"),
            ):
                organization = await db.scalar(
                    select(Organization).where(Organization.slug == slug)
                )
                if organization is None:
                    organization = Organization(
                        name=name,
                        slug=slug,
                        status=OrganizationStatus.ACTIVE,
                        created_by_user_id=users[owner_key].id,
                    )
                    db.add(organization)
                    await db.flush()
                organizations[key] = organization

            for organization in organizations.values():
                await provision_organization_governance(db, organization.id)

            async def ensure_org_member(org_key: str, user_key: str, role_key: str) -> None:
                role = await get_role(db, role_key, "organization")
                organization = organizations[org_key]
                user = users[user_key]
                membership = await db.scalar(
                    select(OrganizationMembership).where(
                        OrganizationMembership.organization_id == organization.id,
                        OrganizationMembership.user_id == user.id,
                    )
                )
                if membership is None:
                    db.add(
                        OrganizationMembership(
                            organization_id=organization.id,
                            user_id=user.id,
                            role_id=role.id,
                            status=MembershipStatus.ACTIVE,
                            joined_at=utc_now(),
                        )
                    )
                else:
                    membership.role_id = role.id
                    membership.role = role
                    membership.status = MembershipStatus.ACTIVE

            await ensure_org_member("alpha", "a", "organization_owner")
            await ensure_org_member("beta", "b", "organization_owner")
            await ensure_org_member("alpha", "c", "organization_member")
            await ensure_org_member("beta", "c", "organization_member")

            workspaces: dict[str, Workspace] = {}
            for org_key, number, owner_key in (
                ("alpha", 1, "a"),
                ("alpha", 2, "a"),
                ("beta", 1, "b"),
                ("beta", 2, "b"),
            ):
                organization = organizations[org_key]
                slug = f"workspace-{number}"
                workspace = await db.scalar(
                    select(Workspace).where(
                        Workspace.organization_id == organization.id, Workspace.slug == slug
                    )
                )
                if workspace is None:
                    workspace = Workspace(
                        organization_id=organization.id,
                        name=f"{org_key.title()} Workspace {number}",
                        slug=slug,
                        status=WorkspaceStatus.ACTIVE,
                        is_default=number == 1,
                        created_by_user_id=users[owner_key].id,
                    )
                    db.add(workspace)
                    await db.flush()
                workspaces[f"{org_key}{number}"] = workspace

            async def ensure_workspace_member(
                workspace_key: str, user_key: str, role_key: str
            ) -> None:
                role = await get_role(db, role_key, "workspace")
                workspace = workspaces[workspace_key]
                user = users[user_key]
                membership = await db.scalar(
                    select(WorkspaceMembership).where(
                        WorkspaceMembership.workspace_id == workspace.id,
                        WorkspaceMembership.user_id == user.id,
                    )
                )
                if membership is None:
                    db.add(
                        WorkspaceMembership(
                            organization_id=workspace.organization_id,
                            workspace_id=workspace.id,
                            user_id=user.id,
                            role_id=role.id,
                            status=MembershipStatus.ACTIVE,
                        )
                    )
                else:
                    membership.role_id = role.id
                    membership.role = role
                    membership.status = MembershipStatus.ACTIVE

            for workspace_key in ("alpha1", "alpha2"):
                await ensure_workspace_member(workspace_key, "a", "workspace_admin")
            for workspace_key in ("beta1", "beta2"):
                await ensure_workspace_member(workspace_key, "b", "workspace_admin")
            await ensure_workspace_member("alpha1", "c", "viewer")
            await ensure_workspace_member("beta2", "c", "viewer")

            pending = await db.scalar(
                select(Invitation).where(
                    Invitation.organization_id == organizations["alpha"].id,
                    Invitation.normalized_email == "pending@vip.demo",
                    Invitation.status == InvitationStatus.PENDING,
                )
            )
            if pending is None:
                raw = secrets.token_urlsafe(settings.INVITATION_TOKEN_BYTES)
                db.add(
                    Invitation(
                        organization_id=organizations["alpha"].id,
                        email="pending@vip.demo",
                        normalized_email="pending@vip.demo",
                        organization_role_id=(
                            await get_role(db, "organization_member", "organization")
                        ).id,
                        workspace_role_id=(await get_role(db, "viewer", "workspace")).id,
                        token_hash=invitation_token_hash(raw),
                        status=InvitationStatus.PENDING,
                        expires_at=utc_now() + timedelta(hours=settings.INVITATION_TOKEN_TTL_HOURS),
                        invited_by_user_id=users["a"].id,
                    )
                )
            await db.commit()
    finally:
        await database.dispose()
    print("Multi-tenancy demo data is ready (secrets were not printed).")


async def configure_governance_demo() -> None:
    require_nonproduction()
    settings = get_settings()
    persona_specs = (
        (
            "admin",
            "governance-admin@vip.demo",
            "Admin User",
            "organization_admin",
            "workspace_admin",
        ),
        ("editor", "governance-editor@vip.demo", "Editor User", "organization_member", "editor"),
        ("viewer", "governance-viewer@vip.demo", "Viewer User", "organization_member", "viewer"),
        (
            "restricted",
            "governance-restricted@vip.demo",
            "Restricted User",
            "organization_member",
            "restricted_user",
        ),
    )
    passwords = {
        key: os.getenv(f"VIP_GOVERNANCE_{key.upper()}_PASSWORD") for key, *_rest in persona_specs
    }
    if any(not password for password in passwords.values()):
        raise SystemExit(
            "Set VIP_GOVERNANCE_ADMIN_PASSWORD, VIP_GOVERNANCE_EDITOR_PASSWORD, "
            "VIP_GOVERNANCE_VIEWER_PASSWORD, and VIP_GOVERNANCE_RESTRICTED_PASSWORD."
        )
    database = Database(settings)
    password_service = PasswordService(settings)
    try:
        async with database.session_factory() as db:
            await seed_system_governance(db)
            users: dict[str, User] = {}
            for key, email, name, _org_role, _workspace_role in persona_specs:
                user = await db.scalar(select(User).where(User.normalized_email == email))
                if user is None:
                    password = passwords[key]
                    assert password is not None
                    user = User(
                        email=email,
                        normalized_email=email,
                        display_name=name,
                        password_hash=password_service.hash_password(password),
                        status=UserStatus.ACTIVE,
                    )
                    db.add(user)
                    await db.flush()
                else:
                    password = passwords[key]
                    assert password is not None
                    user.password_hash = password_service.hash_password(password)
                    user.status = UserStatus.ACTIVE
                users[key] = user
            organization = await db.scalar(
                select(Organization).where(Organization.slug == "governance-demo")
            )
            if organization is None:
                organization = Organization(
                    name="Governance Demo",
                    slug="governance-demo",
                    status=OrganizationStatus.ACTIVE,
                    created_by_user_id=users["admin"].id,
                )
                db.add(organization)
                await db.flush()
            workspace = await db.scalar(
                select(Workspace).where(
                    Workspace.organization_id == organization.id, Workspace.slug == "default"
                )
            )
            if workspace is None:
                workspace = Workspace(
                    organization_id=organization.id,
                    name="Governance Workspace",
                    slug="default",
                    status=WorkspaceStatus.ACTIVE,
                    is_default=True,
                    created_by_user_id=users["admin"].id,
                )
                db.add(workspace)
                await db.flush()
            await provision_organization_governance(db, organization.id)
            for key, _email, _name, organization_role, workspace_role in persona_specs:
                user = users[key]
                org_role = await get_role(db, organization_role, "organization")
                org_membership = await db.scalar(
                    select(OrganizationMembership).where(
                        OrganizationMembership.organization_id == organization.id,
                        OrganizationMembership.user_id == user.id,
                    )
                )
                if org_membership is None:
                    db.add(
                        OrganizationMembership(
                            organization_id=organization.id,
                            user_id=user.id,
                            role_id=org_role.id,
                            status=MembershipStatus.ACTIVE,
                            joined_at=utc_now(),
                        )
                    )
                else:
                    org_membership.role_id = org_role.id
                    org_membership.status = MembershipStatus.ACTIVE
                ws_role = await get_role(db, workspace_role, "workspace")
                ws_membership = await db.scalar(
                    select(WorkspaceMembership).where(
                        WorkspaceMembership.workspace_id == workspace.id,
                        WorkspaceMembership.user_id == user.id,
                    )
                )
                if ws_membership is None:
                    db.add(
                        WorkspaceMembership(
                            organization_id=organization.id,
                            workspace_id=workspace.id,
                            user_id=user.id,
                            role_id=ws_role.id,
                            status=MembershipStatus.ACTIVE,
                        )
                    )
                else:
                    ws_membership.role_id = ws_role.id
                    ws_membership.status = MembershipStatus.ACTIVE
            workspace_quota = await db.scalar(
                select(OrganizationQuota)
                .join(QuotaDefinition, QuotaDefinition.id == OrganizationQuota.quota_id)
                .where(
                    OrganizationQuota.organization_id == organization.id,
                    QuotaDefinition.key == "workspaces.max",
                )
            )
            assert workspace_quota is not None
            workspace_quota.limit_value = 1
            usage = await db.scalar(
                select(QuotaUsage).where(
                    QuotaUsage.organization_id == organization.id,
                    QuotaUsage.workspace_id.is_(None),
                    QuotaUsage.quota_id == workspace_quota.quota_id,
                    QuotaUsage.period_start == datetime(1970, 1, 1, tzinfo=UTC),
                )
            )
            if usage is None:
                db.add(
                    QuotaUsage(
                        organization_id=organization.id,
                        workspace_id=None,
                        quota_id=workspace_quota.quota_id,
                        period_start=datetime(1970, 1, 1, tzinfo=UTC),
                        used_value=1,
                        reserved_value=0,
                    )
                )
            else:
                usage.used_value = 1
            for feature_key, enabled in (("dashboard_studio", True), ("ai_studio", False)):
                feature = await db.scalar(select(FeatureFlag).where(FeatureFlag.key == feature_key))
                assert feature is not None
                override = await db.scalar(
                    select(FeatureFlagOverride).where(
                        FeatureFlagOverride.feature_flag_id == feature.id,
                        FeatureFlagOverride.organization_id == organization.id,
                        FeatureFlagOverride.workspace_id == workspace.id,
                    )
                )
                if override is None:
                    db.add(
                        FeatureFlagOverride(
                            feature_flag_id=feature.id,
                            organization_id=organization.id,
                            workspace_id=workspace.id,
                            enabled=enabled,
                        )
                    )
                else:
                    override.enabled = enabled
            await db.commit()
    finally:
        await database.dispose()
    print("Governance demo personas and policy states are ready (secrets were not printed).")


async def cleanup_multitenancy_demo() -> None:
    require_nonproduction()
    database = Database(get_settings())
    try:
        async with database.session_factory() as db:
            await db.execute(
                delete(Organization).where(Organization.slug.in_(["demo-alpha", "demo-beta"]))
            )
            await db.execute(
                delete(User).where(
                    User.normalized_email.in_(
                        ["tenant-a@vip.demo", "tenant-b@vip.demo", "tenant-c@vip.demo"]
                    )
                )
            )
            await db.commit()
    finally:
        await database.dispose()
    print("Multi-tenancy demo data removed.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m vip_api.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("create-user", help="Create an active local-password user")
    create.add_argument("--email", required=True)
    create.add_argument("--display-name", required=True)
    create.add_argument(
        "--password-stdin",
        action="store_true",
        help=(
            "Read one password line from standard input for automation without exposing it in argv."
        ),
    )
    revoke = subparsers.add_parser(
        "revoke-all-sessions", help="Revoke every active session for one user"
    )
    revoke.add_argument("--email", required=True)
    subparsers.add_parser("cleanup-expired-sessions", help="Delete expired session records")
    subparsers.add_parser("seed-governance", help="Synchronize deterministic B3 definitions")
    subparsers.add_parser(
        "seed-connection-types", help="Synchronize deterministic B4 connection types"
    )
    subparsers.add_parser("seed-dataset-catalogs", help="Seed the local B5 dataset catalog")
    subparsers.add_parser("seed-semantic-layer", help="Seed the local B5 semantic layer")
    subparsers.add_parser(
        "seed-dashboard-governance", help="Synchronize deterministic B6 governance"
    )
    subparsers.add_parser("seed-dashboard-demo", help="Seed the local B6 dashboard demo")
    subparsers.add_parser(
        "configure-governance-demo", help="Idempotently configure B3 governance personas"
    )
    subparsers.add_parser(
        "seed-multitenancy-demo", help="Idempotently create the B2 two-tenant demo fixture"
    )
    subparsers.add_parser("cleanup-multitenancy-demo", help="Remove only the known B2 demo fixture")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "create-user":
        asyncio.run(create_user(args.email, args.display_name, password_stdin=args.password_stdin))
    elif args.command == "revoke-all-sessions":
        asyncio.run(revoke_user_sessions(args.email))
    elif args.command == "cleanup-expired-sessions":
        asyncio.run(cleanup_sessions())
    elif args.command == "seed-governance":
        asyncio.run(seed_governance())
    elif args.command == "seed-connection-types":
        asyncio.run(seed_connection_types())
    elif args.command == "seed-dataset-catalogs":
        asyncio.run(seed_dataset_catalogs())
    elif args.command == "seed-semantic-layer":
        asyncio.run(seed_semantic_layer())
    elif args.command == "seed-dashboard-governance":
        asyncio.run(seed_dashboard_governance())
    elif args.command == "seed-dashboard-demo":
        asyncio.run(seed_dashboard_demo())
    elif args.command == "configure-governance-demo":
        asyncio.run(configure_governance_demo())
    elif args.command == "seed-multitenancy-demo":
        asyncio.run(seed_multitenancy_demo())
    elif args.command == "cleanup-multitenancy-demo":
        asyncio.run(cleanup_multitenancy_demo())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
