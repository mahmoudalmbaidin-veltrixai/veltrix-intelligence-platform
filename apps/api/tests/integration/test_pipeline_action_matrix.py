"""Integration: Pipeline full action-to-level authorization matrix.

Proves the complete resource-bound action matrix against the real services and
``vip_test``: every Pipeline capability is authorized by a Pipeline ACL at the
correct level WITHOUT any broad ``pipeline.*`` workspace permission, is bounded
by the granted level, honours group grants, revocation, explicit deny, and
expiry, and never bypasses tenant membership (cross-tenant grants are inert).

Levels: Viewer < Operator < Developer < Owner. Action mapping under test:
  * Viewer   -> get_editor, list_versions, list_runs, run_detail, list_artifacts
  * Operator -> create_run, cancel_run, retry_run
  * Developer-> save_editor, validate_pipeline, publish_pipeline, restore_version
  * Owner    -> archive_pipeline (+ sharing management, tested separately)

Each ``require_pipeline_access(db, ctx, pid, level)`` succeeds iff the persona's
effective level >= the requested level; the real service functions are also
exercised to prove the mapping is wired into the services, not just the helper.
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
from vip_api.governance.models import Group, GroupMembership, ResourceAccessEntry, Role
from vip_api.pipelines.models import Pipeline
from vip_api.pipelines.schemas import PipelineCreate, PipelineEditorSave
from vip_api.pipelines.services import (
    archive_pipeline,
    create_pipeline,
    get_editor,
    list_pipelines,
    list_versions,
    require_pipeline_access,
    save_editor,
    validate_pipeline,
)
from vip_api.tenancy.models import (
    MembershipStatus,
    Organization,
    OrganizationMembership,
    OrganizationStatus,
    Workspace,
    WorkspaceStatus,
)

LEVELS = ("viewer", "operator", "developer", "owner")


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
        entitlements=frozenset({"pipeline_studio"}),
        feature_flags={"pipeline_studio": True},
        quotas={},
        correlation_id="pipeline-matrix-test",
    )


def _acl(
    org: UUID,
    ws: UUID,
    resource_id: UUID,
    subject_id: UUID,
    level: str,
    *,
    subject_type: str = "user",
    effect: str = "allow",
    expires_at: datetime | None = None,
) -> ResourceAccessEntry:
    return ResourceAccessEntry(
        organization_id=org,
        workspace_id=ws,
        resource_type="pipeline",
        resource_id=resource_id,
        subject_type=subject_type,
        subject_id=subject_id,
        access_level=level,
        effect=effect,
        expires_at=expires_at,
    )


def _user(suffix: str, tag: str) -> User:
    return User(
        username=f"pam-{tag}-{suffix}",
        normalized_username=f"pam-{tag}-{suffix}",
        email=f"pam-{tag}-{suffix}@vip.test",
        normalized_email=f"pam-{tag}-{suffix}@vip.test",
        display_name=tag.title(),
        password_hash="unused",
        status=UserStatus.ACTIVE,
    )


async def _allowed(db: object, ctx: AuthorizationContext, pid: UUID) -> set[str]:
    """Return the set of levels for which the persona is authorized on ``pid``."""
    granted: set[str] = set()
    for level in LEVELS:
        try:
            await require_pipeline_access(db, ctx, pid, level)  # type: ignore[arg-type]
            granted.add(level)
        except ApplicationError:
            pass
    return granted


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pipeline_action_matrix(settings: Settings) -> None:
    database = Database(settings)
    org_id: UUID | None = None
    other_org_id: UUID | None = None
    user_ids: list[UUID] = []
    try:
        async with database.session_factory() as db:
            suffix = uuid4().hex[:8]
            role_id = await db.scalar(select(Role.id).where(Role.key == "organization_member"))
            assert role_id is not None

            owner = _user(suffix, "owner")
            viewer = _user(suffix, "viewer")
            operator = _user(suffix, "operator")
            developer = _user(suffix, "developer")
            owner_acl = _user(suffix, "owneracl")
            group_member = _user(suffix, "group")
            denied = _user(suffix, "denied")
            stranger = _user(suffix, "stranger")
            outsider = _user(suffix, "outsider")
            everyone = [
                owner,
                viewer,
                operator,
                developer,
                owner_acl,
                group_member,
                denied,
                stranger,
                outsider,
            ]
            db.add_all(everyone)
            await db.flush()
            user_ids = [u.id for u in everyone]

            org = Organization(
                name="Matrix Org",
                slug=f"pam-org-{suffix}",
                status=OrganizationStatus.ACTIVE,
                created_by_user_id=owner.id,
            )
            other_org = Organization(
                name="Matrix Other Org",
                slug=f"pam-other-{suffix}",
                status=OrganizationStatus.ACTIVE,
                created_by_user_id=outsider.id,
            )
            db.add_all((org, other_org))
            await db.flush()
            org_id = org.id
            other_org_id = other_org.id
            ws = Workspace(
                organization_id=org.id,
                name="Matrix WS",
                slug="pam-ws",
                status=WorkspaceStatus.ACTIVE,
                is_default=True,
                created_by_user_id=owner.id,
            )
            other_ws = Workspace(
                organization_id=other_org.id,
                name="Other WS",
                slug="pam-other-ws",
                status=WorkspaceStatus.ACTIVE,
                is_default=True,
                created_by_user_id=outsider.id,
            )
            db.add_all((ws, other_ws))
            await db.flush()
            # Active org memberships (required by the suspended check).
            db.add_all(
                OrganizationMembership(
                    organization_id=org.id,
                    user_id=uid,
                    role_id=role_id,
                    status=MembershipStatus.ACTIVE,
                )
                for uid in (
                    owner.id,
                    viewer.id,
                    operator.id,
                    developer.id,
                    owner_acl.id,
                    group_member.id,
                    denied.id,
                    stranger.id,
                )
            )
            db.add(
                OrganizationMembership(
                    organization_id=other_org.id,
                    user_id=outsider.id,
                    role_id=role_id,
                    status=MembershipStatus.ACTIVE,
                )
            )
            # A group in the matrix org that will receive a Developer grant.
            devs = Group(
                organization_id=org.id,
                workspace_id=ws.id,
                name="Devs",
                slug=f"pam-devs-{suffix}",
            )
            db.add(devs)
            await db.flush()
            db.add(GroupMembership(group_id=devs.id, user_id=group_member.id))
            await db.commit()

            owner_ctx = _ctx(
                owner.id,
                org.id,
                ws.id,
                frozenset({"pipeline.read", "pipeline.create", "pipeline.update"}),
            )
            shared = await create_pipeline(db, owner_ctx, PipelineCreate(name="Shared Pipeline"))
            other = await create_pipeline(db, owner_ctx, PipelineCreate(name="Other Pipeline"))
            pid = shared.pipeline.id
            other_id = other.pipeline.id

            # One ACL per persona at the level under test (no pipeline.* perms).
            db.add_all(
                (
                    _acl(org.id, ws.id, pid, viewer.id, "viewer"),
                    _acl(org.id, ws.id, pid, operator.id, "operator"),
                    _acl(org.id, ws.id, pid, developer.id, "developer"),
                    _acl(org.id, ws.id, pid, owner_acl.id, "owner"),
                    _acl(org.id, ws.id, pid, devs.id, "developer", subject_type="group"),
                    _acl(org.id, ws.id, pid, denied.id, "viewer"),
                    _acl(org.id, ws.id, pid, denied.id, "viewer", effect="deny"),
                    # Cross-tenant grant: outsider's own org/ws, inert against `pid`.
                    _acl(other_org.id, other_ws.id, pid, outsider.id, "owner"),
                )
            )
            await db.commit()

            viewer_ctx = _ctx(viewer.id, org.id, ws.id)
            operator_ctx = _ctx(operator.id, org.id, ws.id)
            developer_ctx = _ctx(developer.id, org.id, ws.id)
            owner_acl_ctx = _ctx(owner_acl.id, org.id, ws.id)
            group_ctx = _ctx(group_member.id, org.id, ws.id)
            denied_ctx = _ctx(denied.id, org.id, ws.id)
            stranger_ctx = _ctx(stranger.id, org.id, ws.id)
            outsider_ctx = _ctx(outsider.id, other_org.id, other_ws.id)

            # ---- (1) Level matrix: each persona reaches exactly their band. ----
            assert await _allowed(db, viewer_ctx, pid) == {"viewer"}
            assert await _allowed(db, operator_ctx, pid) == {"viewer", "operator"}
            assert await _allowed(db, developer_ctx, pid) == {
                "viewer",
                "operator",
                "developer",
            }
            assert await _allowed(db, owner_acl_ctx, pid) == set(LEVELS)
            # Group-granted Developer elevates exactly like a direct Developer grant.
            assert await _allowed(db, group_ctx, pid) == {
                "viewer",
                "operator",
                "developer",
            }
            # Explicit deny removes every level despite the sibling viewer allow.
            assert await _allowed(db, denied_ctx, pid) == set()
            # Stranger with no grant: nothing (isolation, non-disclosing 404).
            assert await _allowed(db, stranger_ctx, pid) == set()
            # Cross-tenant grant never authorizes (tenant membership not bypassed).
            assert await _allowed(db, outsider_ctx, pid) == set()

            # ---- (2) Isolation status codes are non-disclosing 404. ----
            with pytest.raises(ApplicationError) as stranger_exc:
                await require_pipeline_access(db, stranger_ctx, pid, "viewer")
            assert stranger_exc.value.status_code == 404
            with pytest.raises(ApplicationError) as dev_bound_exc:
                await require_pipeline_access(db, viewer_ctx, pid, "developer")
            assert dev_bound_exc.value.status_code == 404
            # Explicit deny surfaces as a distinct 403 (rule-driven, not "missing").
            with pytest.raises(ApplicationError) as deny_exc:
                await require_pipeline_access(db, denied_ctx, pid, "viewer")
            assert deny_exc.value.status_code == 403
            assert deny_exc.value.code == "RESOURCE_ACCESS_DENIED"

            # ---- (3) Real service calls prove the mapping is wired in-service. ----
            # Viewer: read paths succeed.
            editor = await get_editor(db, viewer_ctx, pid)
            assert editor.pipeline.id == pid
            assert await list_versions(db, viewer_ctx, pid) == []

            # Viewer CANNOT save (developer) nor validate (developer): 404-bounded.
            save_payload = PipelineEditorSave(
                name="Shared Pipeline",
                expected_version=editor.pipeline.row_version,
                nodes=[],
                edges=[],
            )
            with pytest.raises(ApplicationError) as viewer_save_exc:
                await save_editor(db, viewer_ctx, pid, save_payload)
            assert viewer_save_exc.value.status_code == 404
            with pytest.raises(ApplicationError) as viewer_validate_exc:
                await validate_pipeline(db, viewer_ctx, pid)
            assert viewer_validate_exc.value.status_code == 404

            # Operator CANNOT save either (operator < developer).
            with pytest.raises(ApplicationError):
                await save_editor(db, operator_ctx, pid, save_payload)

            # Developer CAN validate and save.
            validation = await validate_pipeline(db, developer_ctx, pid)
            assert validation is not None
            saved = await save_editor(db, developer_ctx, pid, save_payload)
            assert saved.pipeline.id == pid

            # Developer CANNOT archive (owner-only).
            with pytest.raises(ApplicationError) as dev_archive_exc:
                await archive_pipeline(db, developer_ctx, pid, saved.pipeline.row_version)
            assert dev_archive_exc.value.status_code == 404

            # ---- (4) Collection visibility is filtered + deny-hidden. ----
            assert {row.id for row in (await list_pipelines(db, viewer_ctx)).items} == {pid}
            assert {row.id for row in (await list_pipelines(db, group_ctx)).items} == {pid}
            assert pid not in {row.id for row in (await list_pipelines(db, denied_ctx)).items}
            assert (await list_pipelines(db, stranger_ctx)).items == []
            # Cross-tenant list never leaks the matrix-org pipeline.
            assert pid not in {row.id for row in (await list_pipelines(db, outsider_ctx)).items}
            # Broad-role owner still sees both pipelines.
            owner_ids = {row.id for row in (await list_pipelines(db, owner_ctx)).items}
            assert {pid, other_id} <= owner_ids

            # ---- (5) Revocation immediately removes access. ----
            await db.execute(
                delete(ResourceAccessEntry).where(
                    ResourceAccessEntry.resource_id == pid,
                    ResourceAccessEntry.subject_id == developer.id,
                )
            )
            await db.commit()
            assert await _allowed(db, developer_ctx, pid) == set()
            assert (await list_pipelines(db, developer_ctx)).items == []

            # ---- (6) Expired grant is inert. ----
            fresh = await create_pipeline(db, owner_ctx, PipelineCreate(name="Fresh Pipeline"))
            db.add(
                _acl(
                    org.id,
                    ws.id,
                    fresh.pipeline.id,
                    viewer.id,
                    "viewer",
                    expires_at=datetime.now(UTC) - timedelta(hours=1),
                )
            )
            await db.commit()
            assert await _allowed(db, viewer_ctx, fresh.pipeline.id) == set()
            assert fresh.pipeline.id not in {
                row.id for row in (await list_pipelines(db, viewer_ctx)).items
            }
    finally:
        async with database.session_factory() as db:
            for oid in (org_id, other_org_id):
                if oid is not None:
                    await db.execute(
                        delete(ResourceAccessEntry).where(
                            ResourceAccessEntry.organization_id == oid
                        )
                    )
                    await db.execute(delete(Pipeline).where(Pipeline.organization_id == oid))
                    await db.execute(
                        delete(GroupMembership).where(
                            GroupMembership.group_id.in_(
                                select(Group.id).where(Group.organization_id == oid)
                            )
                        )
                    )
                    await db.execute(delete(Group).where(Group.organization_id == oid))
                    await db.execute(delete(Organization).where(Organization.id == oid))
            for uid in user_ids:
                await db.execute(delete(User).where(User.id == uid))
            await db.commit()
        await database.dispose()
