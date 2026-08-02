"""Centralized resource-access engine (Enterprise permissions — Slice B).

This module wires the pure :func:`evaluate_resource_access` evaluator to the
persistent :class:`ResourceAccessEntry` ACL, group memberships, tenant state,
and role-derived permissions. It is the single decision point for resource-level
authorization: dashboards, pipelines, datasets, connections, reports, and
semantic models. There is no duplicated precedence logic — every caller resolves
through :func:`check_access` / :func:`effective_access`.

Precedence is inherited from the evaluator (suspended -> explicit deny ->
super-admin -> archived workspace -> ownership -> grant/role -> default deny).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from vip_api.auth.models import User, UserStatus
from vip_api.core.errors import ApplicationError
from vip_api.governance.context import AuthorizationContext
from vip_api.governance.models import (
    Group,
    GroupMembership,
    Permission,
    ResourceAccessEntry,
    RolePermission,
)
from vip_api.governance.resource_access import (
    LEVEL_ORDERS,
    AccessDecision,
    AccessEntry,
    evaluate_resource_access,
)
from vip_api.tenancy.models import (
    MembershipStatus,
    OrganizationMembership,
    Workspace,
    WorkspaceMembership,
    WorkspaceStatus,
)


@dataclass(frozen=True, slots=True)
class ResourceSpec:
    """Static description of a shareable resource type."""

    feature: str
    entitlement: str
    table: str | None
    owner_column: str | None
    workspace_scoped: bool = True
    # RBAC permission that authorizes managing this resource's sharing/permissions.
    manage_permission: str | None = None
    # RBAC permission -> access level mapping used to derive a role-granted level.
    role_levels: tuple[tuple[str, str], ...] = ()


RESOURCE_SPECS: dict[str, ResourceSpec] = {
    "dashboard": ResourceSpec(
        feature="dashboard_studio",
        entitlement="dashboard_studio",
        table="dashboards",
        owner_column="owner_user_id",
        manage_permission="dashboard.share",
        role_levels=(
            ("dashboard.read", "view"),
            ("dashboard.query", "interact"),
            ("dashboard.update", "edit"),
            ("dashboard.share", "manage"),
        ),
    ),
    "pipeline": ResourceSpec(
        feature="pipeline_studio",
        entitlement="pipeline_studio",
        table="pipelines",
        owner_column="owner_user_id",
        manage_permission="pipeline.update",
        role_levels=(
            ("pipeline.read", "viewer"),
            ("pipeline.execute", "operator"),
            ("pipeline.update", "developer"),
        ),
    ),
    "dataset": ResourceSpec(
        feature="dataset_studio",
        entitlement="dataset_studio",
        table="datasets",
        owner_column="owner_user_id",
        manage_permission="dataset.update",
        role_levels=(
            ("dataset.read", "query"),
            ("dataset.update", "edit"),
            ("dataset.quality.manage", "certify"),
            ("dataset.delete", "manage"),
        ),
    ),
    "connection": ResourceSpec(
        feature="connection_studio",
        entitlement="connection_studio",
        table="connections",
        owner_column=None,
        manage_permission="connection.update",
        role_levels=(
            ("connection.read", "use"),
            ("connection.test", "test"),
            ("connection.update", "edit"),
            ("connection.credentials.rotate", "rotate"),
            ("connection.delete", "manage"),
        ),
    ),
    "report": ResourceSpec(
        feature="report_studio",
        entitlement="report_studio",
        table=None,
        owner_column=None,
        manage_permission="report.update",
        role_levels=(
            ("report.read", "view"),
            ("report.update", "edit"),
        ),
    ),
    "semantic_model": ResourceSpec(
        feature="semantic_layer",
        entitlement="semantic_layer",
        table="semantic_models",
        owner_column=None,
        manage_permission="semantic_model.update",
        role_levels=(
            ("semantic_model.read", "view"),
            ("semantic.query", "query"),
            ("semantic_model.update", "edit"),
            ("semantic_model.publish", "manage"),
        ),
    ),
}

SUBJECT_TYPES = ("user", "group")
EFFECTS = ("allow", "deny")


def resource_types() -> list[str]:
    return list(RESOURCE_SPECS.keys())


def spec_for(resource_type: str) -> ResourceSpec:
    spec = RESOURCE_SPECS.get(resource_type)
    if spec is None:
        raise ApplicationError(
            code="RESOURCE_TYPE_INVALID",
            message="Unknown resource type.",
            status_code=422,
        )
    return spec


def levels_for(resource_type: str) -> tuple[str, ...]:
    spec_for(resource_type)
    return LEVEL_ORDERS[resource_type]


def validate_level(resource_type: str, level: str) -> None:
    if level not in LEVEL_ORDERS.get(resource_type, ()):  # pragma: no branch
        raise ApplicationError(
            code="ACCESS_LEVEL_INVALID",
            message="The access level is not valid for this resource type.",
            status_code=422,
        )


def role_level(resource_type: str, permissions: frozenset[str]) -> str | None:
    """Highest access level granted purely by role-derived permissions."""
    order = LEVEL_ORDERS[resource_type]
    best_rank = -1
    best: str | None = None
    for permission, level in RESOURCE_SPECS[resource_type].role_levels:
        if permission in permissions:
            rank = order.index(level)
            if rank > best_rank:
                best_rank, best = rank, level
    return best


@dataclass(frozen=True, slots=True)
class AccessOverlay:
    """Resource-ACL overlay applied on top of an existing RBAC decision.

    ``allow_rank`` is the highest active allow level (or -1), ``deny_rank`` is the
    lowest active deny level that applies (or None). ``is_owner`` short-circuits
    to full access. Ranks index into ``LEVEL_ORDERS[resource_type]``.
    """

    allow_rank: int
    deny_rank: int | None
    is_owner: bool


async def access_overlay(
    db: AsyncSession,
    *,
    resource_type: str,
    resource_id: UUID,
    organization_id: UUID,
    workspace_id: UUID | None,
    user_id: UUID,
    owner_user_id: UUID | None,
) -> AccessOverlay:
    order = LEVEL_ORDERS[resource_type]
    subject_ids = {user_id} | await group_ids_for_user(db, organization_id, user_id)
    rows = await _load_access_entries(db, resource_type, resource_id)
    now = datetime.now(UTC)
    allow_rank = -1
    deny_rank: int | None = None
    for row in rows:
        if row.subject_id not in subject_ids:
            continue
        if row.expires_at is not None and row.expires_at <= now:
            continue
        try:
            rank = order.index(row.access_level)
        except ValueError:
            continue
        if row.effect == "allow" and rank > allow_rank:
            allow_rank = rank
        elif row.effect == "deny" and (deny_rank is None or rank < deny_rank):
            deny_rank = rank
    return AccessOverlay(
        allow_rank=allow_rank,
        deny_rank=deny_rank,
        is_owner=owner_user_id is not None and owner_user_id == user_id,
    )


async def enforce_resource_guard(
    db: AsyncSession,
    *,
    resource_type: str,
    resource_id: UUID,
    action_level: str,
    organization_id: UUID,
    workspace_id: UUID | None,
    user_id: UUID,
    owner_user_id: UUID | None = None,
) -> None:
    """Additive resource-ACL guard applied on top of route RBAC.

    Route-level RBAC (``require_governance``) remains the coarse gate that decides
    whether a user may reach a resource operation at all. This guard is layered on
    top as defense-in-depth and only ever *restricts* access — it never loosens
    it — so wiring it into existing services introduces no regression:

    * A non-expired **explicit deny** covering ``action_level`` blocks the
      operation for everyone (fail-closed). Per the platform precedence model an
      explicit deny overrides ownership and super-admin, so no subject bypasses it.
    * Expired grants/denies are ignored (handled by :func:`access_overlay`).

    Elevation for users who hold an ACL *allow* but lack the RBAC permission is
    intentionally not performed here because the strict route gate would already
    have rejected them; sharing that grants brand-new access is exposed through
    the generic ``/resources`` API and the dashboard overlay only.
    """
    order = LEVEL_ORDERS[resource_type]
    try:
        required = order.index(action_level)
    except ValueError:  # pragma: no cover - defensive
        return
    overlay = await access_overlay(
        db,
        resource_type=resource_type,
        resource_id=resource_id,
        organization_id=organization_id,
        workspace_id=workspace_id,
        user_id=user_id,
        owner_user_id=owner_user_id,
    )
    # A deny at rank L blocks any action whose required rank is >= L.
    if overlay.deny_rank is not None and required >= overlay.deny_rank:
        raise ApplicationError(
            code="RESOURCE_ACCESS_DENIED",
            message="Access to this resource is denied by an explicit permission rule.",
            status_code=403,
        )


# Per-type physical columns for the tenant-scoped resource picker search. Only
# trusted, fixed identifiers are interpolated (never user input).
_SEARCH_COLUMNS: dict[str, tuple[str, str]] = {
    # resource_type -> (name_column, owner_column)
    "dashboard": ("name", "owner_user_id"),
    "pipeline": ("name", "owner_user_id"),
    "dataset": ("display_name", "owner_user_id"),
    "connection": ("name", "created_by_user_id"),
    "semantic_model": ("name", "created_by_user_id"),
}


@dataclass(frozen=True, slots=True)
class ResourceSearchRow:
    id: UUID
    name: str
    resource_type: str
    status: str | None
    owner_user_id: UUID | None
    workspace_id: UUID | None
    updated_at: datetime | None


async def search_resources(
    db: AsyncSession,
    *,
    resource_type: str,
    organization_id: UUID,
    workspace_id: UUID | None,
    query: str,
    limit: int = 20,
) -> list[ResourceSearchRow]:
    """Tenant-scoped searchable listing that powers resource pickers.

    Report resources have no physical table yet, so they return no rows (the UI
    keeps manual entry as an advanced fallback for such types).
    """
    spec_for(resource_type)
    columns = _SEARCH_COLUMNS.get(resource_type)
    if columns is None:
        return []
    name_col, owner_col = columns
    clauses = ["organization_id = :org", "archived_at IS NULL"]
    params: dict[str, object] = {"org": organization_id, "limit": limit}
    if workspace_id is not None:
        clauses.append("workspace_id = :ws")
        params["ws"] = workspace_id
    if query.strip():
        clauses.append(f"LOWER({name_col}) LIKE :q")
        params["q"] = f"%{query.strip().lower()}%"
    where = " AND ".join(clauses)
    table = spec_for(resource_type).table
    # All interpolated identifiers (columns, table) come from a trusted fixed map;
    # every user value is bound via parameters.
    sql = (
        f"SELECT id, {name_col} AS name, status, {owner_col} AS owner_user_id, "  # noqa: S608
        f"workspace_id, updated_at FROM {table} "
        f"WHERE {where} ORDER BY updated_at DESC NULLS LAST LIMIT :limit"
    )
    rows = (await db.execute(text(sql), params)).mappings().all()
    return [
        ResourceSearchRow(
            id=row["id"],
            name=row["name"] or "Untitled",
            resource_type=resource_type,
            status=row["status"],
            owner_user_id=row["owner_user_id"],
            workspace_id=row["workspace_id"],
            updated_at=row["updated_at"],
        )
        for row in rows
    ]


@dataclass(frozen=True, slots=True)
class ResourceMeta:
    exists: bool
    owner_user_id: UUID | None
    workspace_id: UUID | None
    workspace_archived: bool


async def _workspace_archived(db: AsyncSession, workspace_id: UUID | None) -> bool:
    if workspace_id is None:
        return False
    row = await db.scalar(select(Workspace).where(Workspace.id == workspace_id))
    if row is None:
        return False
    return row.status == WorkspaceStatus.ARCHIVED or row.archived_at is not None


async def load_resource_meta(
    db: AsyncSession,
    resource_type: str,
    resource_id: UUID,
    organization_id: UUID,
    workspace_id: UUID | None,
) -> ResourceMeta:
    """Resolve ownership + tenant state for a concrete resource row.

    Uses parameterized SQL against a fixed, trusted table map to avoid cross
    module import cycles. Resource types without a physical table (``report``)
    are treated as existing within the caller's tenant.
    """
    spec = spec_for(resource_type)
    archived = await _workspace_archived(db, workspace_id)
    if spec.table is None:
        return ResourceMeta(True, None, workspace_id, archived)
    owner_select = (
        f"{spec.owner_column} AS owner_user_id" if spec.owner_column else "NULL AS owner_user_id"
    )
    statement = text(
        f"SELECT {owner_select}, workspace_id FROM {spec.table} "  # noqa: S608
        "WHERE id = :rid AND organization_id = :org"
    )
    result = await db.execute(statement, {"rid": resource_id, "org": organization_id})
    row = result.mappings().first()
    if row is None:
        return ResourceMeta(False, None, None, archived)
    ws_id = row["workspace_id"]
    ws_archived = await _workspace_archived(db, ws_id) if ws_id != workspace_id else archived
    return ResourceMeta(True, row["owner_user_id"], ws_id, ws_archived)


async def group_ids_for_user(db: AsyncSession, organization_id: UUID, user_id: UUID) -> set[UUID]:
    rows = await db.scalars(
        select(GroupMembership.group_id)
        .join(Group, Group.id == GroupMembership.group_id)
        .where(
            Group.organization_id == organization_id,
            Group.deleted_at.is_(None),
            Group.archived_at.is_(None),
            GroupMembership.user_id == user_id,
        )
    )
    return set(rows.all())


async def _user_suspended(
    db: AsyncSession, organization_id: UUID, workspace_id: UUID | None, user_id: UUID
) -> bool:
    status = await db.scalar(select(User.status).where(User.id == user_id))
    if status is None or status != UserStatus.ACTIVE:
        return True
    org_status = await db.scalar(
        select(OrganizationMembership.status).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == user_id,
        )
    )
    if org_status is None or org_status != MembershipStatus.ACTIVE:
        return True
    if workspace_id is not None:
        ws_status = await db.scalar(
            select(WorkspaceMembership.status).where(
                WorkspaceMembership.workspace_id == workspace_id,
                WorkspaceMembership.user_id == user_id,
            )
        )
        if ws_status is not None and ws_status != MembershipStatus.ACTIVE:
            return True
    return False


async def _permission_keys_for_user(
    db: AsyncSession, organization_id: UUID, workspace_id: UUID | None, user_id: UUID
) -> frozenset[str]:
    role_ids: set[UUID] = set()
    org_role = await db.scalar(
        select(OrganizationMembership.role_id).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == user_id,
        )
    )
    if org_role is not None:
        role_ids.add(org_role)
    if workspace_id is not None:
        ws_role = await db.scalar(
            select(WorkspaceMembership.role_id).where(
                WorkspaceMembership.workspace_id == workspace_id,
                WorkspaceMembership.user_id == user_id,
            )
        )
        if ws_role is not None:
            role_ids.add(ws_role)
    # Custom + group role assignments (Slice C) also grant catalog permissions.
    from vip_api.governance.services import assigned_role_ids_for

    role_ids |= await assigned_role_ids_for(
        db, organization_id=organization_id, workspace_id=workspace_id, user_id=user_id
    )
    if not role_ids:
        return frozenset()
    keys = await db.scalars(
        select(Permission.key)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .where(RolePermission.role_id.in_(role_ids))
    )
    return frozenset(keys.all())


async def _load_access_entries(
    db: AsyncSession, resource_type: str, resource_id: UUID
) -> list[ResourceAccessEntry]:
    rows = await db.scalars(
        select(ResourceAccessEntry).where(
            ResourceAccessEntry.resource_type == resource_type,
            ResourceAccessEntry.resource_id == resource_id,
        )
    )
    return list(rows.all())


def _to_access_entries(rows: list[ResourceAccessEntry]) -> list[AccessEntry]:
    return [
        AccessEntry(
            subject_type=row.subject_type,
            subject_id=row.subject_id,
            access_level=row.access_level,
            effect=row.effect,
            expires_at=row.expires_at,
        )
        for row in rows
    ]


async def check_access(
    db: AsyncSession,
    *,
    resource_type: str,
    resource_id: UUID,
    action_level: str,
    organization_id: UUID,
    workspace_id: UUID | None,
    user_id: UUID,
    is_platform_admin: bool = False,
    role_permissions: frozenset[str] | None = None,
) -> AccessDecision:
    """Single decision point for resource-level authorization for one subject."""
    validate_level(resource_type, action_level)
    meta = await load_resource_meta(db, resource_type, resource_id, organization_id, workspace_id)
    subject_ids = {user_id} | await group_ids_for_user(db, organization_id, user_id)
    entries = _to_access_entries(await _load_access_entries(db, resource_type, resource_id))
    if role_permissions is None:
        role_permissions = await _permission_keys_for_user(
            db, organization_id, workspace_id, user_id
        )
    suspended = await _user_suspended(db, organization_id, workspace_id, user_id)
    return evaluate_resource_access(
        resource_type=resource_type,
        action_level=action_level,
        subject_ids=subject_ids,
        entries=entries,
        now=datetime.now(UTC),
        is_platform_admin=is_platform_admin,
        is_owner=meta.owner_user_id is not None and meta.owner_user_id == user_id,
        subject_suspended=suspended,
        workspace_archived=meta.workspace_archived,
        role_granted_level=role_level(resource_type, role_permissions),
    )


@dataclass(frozen=True, slots=True)
class EffectiveAccess:
    resource_type: str
    resource_id: UUID
    user_id: UUID
    level: str | None
    allowed_levels: list[str]
    source: str
    reason: str


async def effective_access(
    db: AsyncSession,
    *,
    resource_type: str,
    resource_id: UUID,
    organization_id: UUID,
    workspace_id: UUID | None,
    user_id: UUID,
    is_platform_admin: bool = False,
    role_permissions: frozenset[str] | None = None,
) -> EffectiveAccess:
    """Compute the highest allowed level and the full allowed ladder for a user."""
    order = levels_for(resource_type)
    allowed: list[str] = []
    top: str | None = None
    top_decision: AccessDecision | None = None
    for level in order:
        decision = await check_access(
            db,
            resource_type=resource_type,
            resource_id=resource_id,
            action_level=level,
            organization_id=organization_id,
            workspace_id=workspace_id,
            user_id=user_id,
            is_platform_admin=is_platform_admin,
            role_permissions=role_permissions,
        )
        if decision.allowed:
            allowed.append(level)
            top, top_decision = level, decision
    if top_decision is None:
        # Re-evaluate the lowest level to surface the denial reason.
        top_decision = await check_access(
            db,
            resource_type=resource_type,
            resource_id=resource_id,
            action_level=order[0],
            organization_id=organization_id,
            workspace_id=workspace_id,
            user_id=user_id,
            is_platform_admin=is_platform_admin,
            role_permissions=role_permissions,
        )
    return EffectiveAccess(
        resource_type=resource_type,
        resource_id=resource_id,
        user_id=user_id,
        level=top,
        allowed_levels=allowed,
        source=top_decision.source,
        reason=top_decision.reason,
    )


def can_manage_resource(
    context: AuthorizationContext,
    spec: ResourceSpec,
    meta: ResourceMeta,
    *,
    is_platform_admin: bool = False,
) -> bool:
    """Whether the acting user may administer sharing/permissions for a resource."""
    if is_platform_admin:
        return True
    if meta.owner_user_id is not None and meta.owner_user_id == context.user_id:
        return True
    return spec.manage_permission is not None and spec.manage_permission in context.permissions


async def authorize_resource(
    db: AsyncSession,
    context: AuthorizationContext,
    *,
    resource_type: str,
    resource_id: UUID,
    action_level: str,
    is_platform_admin: bool = False,
) -> None:
    """Authoritative per-resource guard shared by every domain service.

    Single reuse point for the resource-level decision: combines role-derived
    level, direct/group ACL grants, ownership, explicit deny and expiration
    through :func:`check_access`, so a resource ACL grant *elevates* access
    without the broad workspace permission. An explicit deny yields a
    ``403 RESOURCE_ACCESS_DENIED``; any other denial (no grant, expired,
    insufficient level, cross-tenant) yields a non-disclosing ``404``. No domain
    re-implements precedence — this is the one gate they all call.
    """
    decision = await check_access(
        db,
        resource_type=resource_type,
        resource_id=resource_id,
        action_level=action_level,
        organization_id=context.organization_id,
        workspace_id=context.workspace_id,
        user_id=context.user_id,
        is_platform_admin=is_platform_admin,
        role_permissions=context.permissions,
    )
    if decision.allowed:
        return
    if decision.reason == "EXPLICIT_DENY":
        raise ApplicationError(
            code="RESOURCE_ACCESS_DENIED",
            message="Access to this resource is denied by an explicit permission rule.",
            status_code=403,
        )
    raise ApplicationError(
        code="NOT_FOUND", message="The requested resource was not found.", status_code=404
    )


async def can_manage_access(
    db: AsyncSession,
    context: AuthorizationContext,
    *,
    resource_type: str,
    resource_id: UUID,
    is_platform_admin: bool = False,
) -> bool:
    """Whether the caller may administer sharing for a resource.

    Mirrors the check enforced by :func:`grant_resource_access` /
    :func:`revoke_resource_access` (platform-admin, resource owner, or holder of
    the resource's ``manage_permission``) so the client can show/hide the Share
    control from the same authority the API enforces.
    """
    spec = spec_for(resource_type)
    meta = await load_resource_meta(
        db, resource_type, resource_id, context.organization_id, context.workspace_id
    )
    if not meta.exists:
        return False
    return can_manage_resource(context, spec, meta, is_platform_admin=is_platform_admin)


def collection_visibility_subqueries(
    resource_type: str, subject_ids: set[UUID], *, now: datetime
) -> tuple[Select[tuple[UUID]], Select[tuple[UUID]]]:
    """Return ``(allowed_ids, denied_ids)`` SELECTs for SQL-level list filtering.

    ``allowed_ids`` = non-expired *allow* ACL entries for the given subjects (the
    user plus their groups). ``denied_ids`` = active *deny* entries at the
    resource's lowest level, which blocks every action. Domains combine these
    with ownership / broad-role visibility so collection endpoints filter in SQL
    (no per-row authorization, no N+1) and never leak hidden resources.
    """
    lowest_level = LEVEL_ORDERS[resource_type][0]
    active = or_(
        ResourceAccessEntry.expires_at.is_(None),
        ResourceAccessEntry.expires_at > now,
    )
    allowed = select(ResourceAccessEntry.resource_id).where(
        ResourceAccessEntry.resource_type == resource_type,
        ResourceAccessEntry.subject_id.in_(subject_ids),
        ResourceAccessEntry.effect == "allow",
        active,
    )
    denied = select(ResourceAccessEntry.resource_id).where(
        ResourceAccessEntry.resource_type == resource_type,
        ResourceAccessEntry.subject_id.in_(subject_ids),
        ResourceAccessEntry.effect == "deny",
        ResourceAccessEntry.access_level == lowest_level,
        active,
    )
    return allowed, denied


@dataclass(frozen=True, slots=True)
class ResourceAccessSummary:
    """The caller's effective access to a single resource for client UI states."""

    level: str | None
    allowed_levels: list[str]
    can_manage_access: bool
    source: str
    reason: str


async def resource_access_summary(
    db: AsyncSession,
    context: AuthorizationContext,
    *,
    resource_type: str,
    resource_id: UUID,
    is_platform_admin: bool = False,
) -> ResourceAccessSummary:
    """Resolve effective access + sharing authority for a resource in one place.

    Domains embed this on their read responses so the client renders per-capability
    states (viewer/editor/manager/owner/denied) and the Share control from exactly
    the decision the API enforces. Never a security boundary itself.
    """
    result = await effective_access(
        db,
        resource_type=resource_type,
        resource_id=resource_id,
        organization_id=context.organization_id,
        workspace_id=context.workspace_id,
        user_id=context.user_id,
        is_platform_admin=is_platform_admin,
        role_permissions=context.permissions,
    )
    manage = await can_manage_access(
        db,
        context,
        resource_type=resource_type,
        resource_id=resource_id,
        is_platform_admin=is_platform_admin,
    )
    return ResourceAccessSummary(
        level=result.level,
        allowed_levels=result.allowed_levels,
        can_manage_access=manage,
        source=result.source,
        reason=result.reason,
    )


@dataclass(frozen=True, slots=True)
class ResourceEntryView:
    id: UUID
    subject_type: str
    subject_id: UUID
    subject_label: str
    subject_detail: str | None
    access_level: str
    effect: str
    expires_at: datetime | None
    granted_by_user_id: UUID | None
    created_at: datetime


async def _assert_can_manage(
    db: AsyncSession,
    context: AuthorizationContext,
    resource_type: str,
    resource_id: UUID,
    *,
    is_platform_admin: bool,
) -> tuple[ResourceSpec, ResourceMeta]:
    spec = spec_for(resource_type)
    meta = await load_resource_meta(
        db, resource_type, resource_id, context.organization_id, context.workspace_id
    )
    if not meta.exists:
        raise ApplicationError(
            code="RESOURCE_NOT_FOUND", message="The resource was not found.", status_code=404
        )
    if not can_manage_resource(context, spec, meta, is_platform_admin=is_platform_admin):
        from vip_api.governance.audit import record_audit

        await record_audit(
            db,
            "resource.permission.denied",
            actor_user_id=context.user_id,
            organization_id=context.organization_id,
            workspace_id=context.workspace_id,
            outcome="denied",
            reason_code="RESOURCE_MANAGE_DENIED",
            resource_type=resource_type,
            resource_id=resource_id,
            commit=True,
        )
        raise ApplicationError(
            code="RESOURCE_MANAGE_DENIED",
            message="You do not have permission to manage sharing for this resource.",
            status_code=403,
        )
    return spec, meta


async def _validate_subject(
    db: AsyncSession, context: AuthorizationContext, subject_type: str, subject_id: UUID
) -> None:
    if subject_type not in SUBJECT_TYPES:
        raise ApplicationError(
            code="SUBJECT_TYPE_INVALID", message="Unknown subject type.", status_code=422
        )
    if subject_type == "user":
        membership = await db.scalar(
            select(OrganizationMembership).where(
                OrganizationMembership.organization_id == context.organization_id,
                OrganizationMembership.user_id == subject_id,
            )
        )
        if membership is None:
            raise ApplicationError(
                code="SUBJECT_NOT_FOUND",
                message="The user is not a member of this organization.",
                status_code=422,
            )
    else:
        group = await db.scalar(
            select(Group).where(
                Group.id == subject_id,
                Group.organization_id == context.organization_id,
                Group.deleted_at.is_(None),
            )
        )
        if group is None:
            raise ApplicationError(
                code="SUBJECT_NOT_FOUND", message="The group was not found.", status_code=422
            )


async def grant_resource_access(
    db: AsyncSession,
    context: AuthorizationContext,
    *,
    resource_type: str,
    resource_id: UUID,
    subject_type: str,
    subject_id: UUID,
    access_level: str,
    effect: str = "allow",
    expires_at: datetime | None = None,
    is_platform_admin: bool = False,
) -> ResourceAccessEntry:
    from vip_api.governance.audit import record_audit

    if effect not in EFFECTS:
        raise ApplicationError(code="EFFECT_INVALID", message="Unknown effect.", status_code=422)
    validate_level(resource_type, access_level)
    await _assert_can_manage(
        db, context, resource_type, resource_id, is_platform_admin=is_platform_admin
    )
    await _validate_subject(db, context, subject_type, subject_id)
    # One entry per (subject, effect): replace any prior grant/deny at other levels.
    existing = await db.scalars(
        select(ResourceAccessEntry).where(
            ResourceAccessEntry.resource_type == resource_type,
            ResourceAccessEntry.resource_id == resource_id,
            ResourceAccessEntry.subject_type == subject_type,
            ResourceAccessEntry.subject_id == subject_id,
            ResourceAccessEntry.effect == effect,
        )
    )
    for row in existing.all():
        await db.delete(row)
    await db.flush()
    entry = ResourceAccessEntry(
        id=uuid4(),
        organization_id=context.organization_id,
        workspace_id=context.workspace_id,
        resource_type=resource_type,
        resource_id=resource_id,
        subject_type=subject_type,
        subject_id=subject_id,
        access_level=access_level,
        effect=effect,
        expires_at=expires_at,
        granted_by_user_id=context.user_id,
    )
    db.add(entry)
    await record_audit(
        db,
        "resource.permission.granted",
        actor_user_id=context.user_id,
        organization_id=context.organization_id,
        workspace_id=context.workspace_id,
        resource_type=resource_type,
        resource_id=resource_id,
        metadata={
            "subject_type": subject_type,
            "subject_id": str(subject_id),
            "access_level": access_level,
            "effect": effect,
            "expires_at": expires_at.isoformat() if expires_at else None,
        },
    )
    await db.commit()
    await db.refresh(entry)
    return entry


async def revoke_resource_access(
    db: AsyncSession,
    context: AuthorizationContext,
    *,
    resource_type: str,
    resource_id: UUID,
    entry_id: UUID,
    is_platform_admin: bool = False,
) -> None:
    from vip_api.governance.audit import record_audit

    spec_for(resource_type)
    entry = await db.scalar(
        select(ResourceAccessEntry).where(
            ResourceAccessEntry.id == entry_id,
            ResourceAccessEntry.resource_type == resource_type,
            ResourceAccessEntry.resource_id == resource_id,
            ResourceAccessEntry.organization_id == context.organization_id,
        )
    )
    if entry is None:
        raise ApplicationError(
            code="RESOURCE_GRANT_NOT_FOUND",
            message="The permission entry was not found.",
            status_code=404,
        )
    await _assert_can_manage(
        db, context, resource_type, resource_id, is_platform_admin=is_platform_admin
    )
    metadata: dict[str, object] = {
        "subject_type": entry.subject_type,
        "subject_id": str(entry.subject_id),
        "access_level": entry.access_level,
        "effect": entry.effect,
    }
    await db.delete(entry)
    await record_audit(
        db,
        "resource.permission.revoked",
        actor_user_id=context.user_id,
        organization_id=context.organization_id,
        workspace_id=context.workspace_id,
        resource_type=resource_type,
        resource_id=resource_id,
        metadata=metadata,
    )
    await db.commit()


async def list_resource_entries(
    db: AsyncSession, context: AuthorizationContext, *, resource_type: str, resource_id: UUID
) -> list[ResourceEntryView]:
    spec_for(resource_type)
    rows = await _load_access_entries(db, resource_type, resource_id)
    rows = [row for row in rows if row.organization_id == context.organization_id]
    user_ids = {row.subject_id for row in rows if row.subject_type == "user"}
    group_ids = {row.subject_id for row in rows if row.subject_type == "group"}
    users: dict[UUID, User] = {}
    if user_ids:
        for record in (await db.scalars(select(User).where(User.id.in_(user_ids)))).all():
            users[record.id] = record
    groups: dict[UUID, Group] = {}
    if group_ids:
        for group_row in (await db.scalars(select(Group).where(Group.id.in_(group_ids)))).all():
            groups[group_row.id] = group_row
    views: list[ResourceEntryView] = []
    for row in rows:
        if row.subject_type == "user":
            user = users.get(row.subject_id)
            label = user.display_name if user else "Unknown user"
            detail = (user.email or user.username) if user else None
        else:
            group = groups.get(row.subject_id)
            label = group.name if group else "Unknown group"
            detail = "Group"
        views.append(
            ResourceEntryView(
                id=row.id,
                subject_type=row.subject_type,
                subject_id=row.subject_id,
                subject_label=label,
                subject_detail=detail,
                access_level=row.access_level,
                effect=row.effect,
                expires_at=row.expires_at,
                granted_by_user_id=row.granted_by_user_id,
                created_at=row.created_at,
            )
        )
    views.sort(key=lambda item: (item.effect, item.subject_label.lower()))
    return views
