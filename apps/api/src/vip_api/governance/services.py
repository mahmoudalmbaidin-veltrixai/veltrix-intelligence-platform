"""Permission resolution and governance decision services."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import MappingProxyType
from typing import Any, Never
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.core.errors import ApplicationError
from vip_api.governance.audit import record_audit
from vip_api.governance.context import AuthorizationContext, QuotaSnapshot
from vip_api.governance.models import (
    Entitlement,
    FeatureFlag,
    FeatureFlagOverride,
    Group,
    GroupMembership,
    GroupRoleAssignment,
    OrganizationEntitlement,
    OrganizationQuota,
    Permission,
    QuotaDefinition,
    QuotaUsage,
    Role,
    RolePermission,
    UserRoleAssignment,
)
from vip_api.governance.policies import SYSTEM_PERMISSION_KEYS
from vip_api.tenancy.context import TenantContext


async def get_role(db: AsyncSession, key: str, scope: str) -> Role:
    role = await db.scalar(select(Role).where(Role.key == key, Role.scope == scope))
    if role is None:
        raise ApplicationError(
            code="ROLE_SCOPE_INVALID",
            message="The selected role is not valid for this membership.",
            status_code=422,
        )
    return role


async def _permission_keys(db: AsyncSession, role_ids: set[UUID]) -> frozenset[str]:
    if not role_ids:
        return frozenset()
    keys = await db.scalars(
        select(Permission.key)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .where(RolePermission.role_id.in_(role_ids))
    )
    return frozenset(keys.all())


async def assigned_role_ids_for(
    db: AsyncSession,
    *,
    organization_id: UUID,
    workspace_id: UUID | None,
    user_id: UUID,
) -> set[UUID]:
    """Role IDs assigned to a user directly or via their groups.

    Includes only active (non-archived, non-deleted) roles. Organization-scoped
    assignments (``workspace_id IS NULL``) apply everywhere in the org; workspace
    -scoped assignments apply only in the matching workspace. This is the single
    place custom + group role grants enter the permission set, so all existing
    route guards enforce them without duplicated logic.
    """

    def _scope_ok(column: Any) -> Any:
        if workspace_id is None:
            return column.is_(None)
        return or_(column.is_(None), column == workspace_id)

    direct = (
        await db.scalars(
            select(UserRoleAssignment.role_id).where(
                UserRoleAssignment.organization_id == organization_id,
                UserRoleAssignment.user_id == user_id,
                _scope_ok(UserRoleAssignment.workspace_id),
            )
        )
    ).all()

    group_ids = (
        await db.scalars(
            select(GroupMembership.group_id)
            .join(Group, Group.id == GroupMembership.group_id)
            .where(
                Group.organization_id == organization_id,
                Group.deleted_at.is_(None),
                Group.archived_at.is_(None),
                GroupMembership.user_id == user_id,
            )
        )
    ).all()

    via_group: list[UUID] = []
    if group_ids:
        via_group = list(
            (
                await db.scalars(
                    select(GroupRoleAssignment.role_id).where(
                        GroupRoleAssignment.organization_id == organization_id,
                        GroupRoleAssignment.group_id.in_(group_ids),
                        _scope_ok(GroupRoleAssignment.workspace_id),
                    )
                )
            ).all()
        )

    candidate_ids = set(direct) | set(via_group)
    if not candidate_ids:
        return set()
    active = await db.scalars(
        select(Role.id).where(
            Role.id.in_(candidate_ids),
            Role.deleted_at.is_(None),
            Role.archived_at.is_(None),
            Role.status == "active",
        )
    )
    return set(active.all())


async def _assigned_role_ids(db: AsyncSession, tenant: TenantContext) -> set[UUID]:
    return await assigned_role_ids_for(
        db,
        organization_id=tenant.organization_id,
        workspace_id=tenant.workspace_id,
        user_id=tenant.user_id,
    )


async def resolve_authorization_context(
    db: AsyncSession, tenant: TenantContext
) -> AuthorizationContext:
    now = datetime.now(UTC)
    role_keys = {tenant.organization_role}
    if tenant.workspace_role:
        role_keys.add(tenant.workspace_role)
    roles = list((await db.scalars(select(Role).where(Role.key.in_(role_keys)))).all())
    roles_by_key = {role.key: role for role in roles}
    if tenant.organization_role not in roles_by_key or (
        tenant.workspace_role and tenant.workspace_role not in roles_by_key
    ):
        raise ApplicationError(
            code="GOVERNANCE_CONFIGURATION_ERROR",
            message="Authorization could not be evaluated.",
            status_code=503,
        )
    membership_role_ids = {role.id for role in roles}
    assigned_role_ids = await _assigned_role_ids(db, tenant)
    permissions = await _permission_keys(db, membership_role_ids | assigned_role_ids)

    entitlement_keys = await db.scalars(
        select(Entitlement.key)
        .join(OrganizationEntitlement, OrganizationEntitlement.entitlement_id == Entitlement.id)
        .where(
            OrganizationEntitlement.organization_id == tenant.organization_id,
            OrganizationEntitlement.status == "active",
            or_(
                OrganizationEntitlement.starts_at.is_(None),
                OrganizationEntitlement.starts_at <= now,
            ),
            or_(
                OrganizationEntitlement.ends_at.is_(None),
                OrganizationEntitlement.ends_at > now,
            ),
        )
    )
    entitlements = frozenset(entitlement_keys.all())

    flags = list((await db.scalars(select(FeatureFlag))).all())
    overrides = list(
        (
            await db.scalars(
                select(FeatureFlagOverride).where(
                    FeatureFlagOverride.organization_id == tenant.organization_id,
                    or_(
                        FeatureFlagOverride.workspace_id.is_(None),
                        FeatureFlagOverride.workspace_id == tenant.workspace_id,
                    ),
                    or_(
                        FeatureFlagOverride.starts_at.is_(None),
                        FeatureFlagOverride.starts_at <= now,
                    ),
                    or_(FeatureFlagOverride.ends_at.is_(None), FeatureFlagOverride.ends_at > now),
                )
            )
        ).all()
    )
    override_by_flag: dict[UUID, FeatureFlagOverride] = {}
    for override in overrides:
        current = override_by_flag.get(override.feature_flag_id)
        if current is None or (current.workspace_id is None and override.workspace_id is not None):
            override_by_flag[override.feature_flag_id] = override
    feature_flags = {
        flag.key: (
            override_by_flag[flag.id].enabled
            if flag.id in override_by_flag
            else flag.default_enabled
        )
        for flag in flags
    }

    quota_rows = (
        (
            await db.execute(
                select(OrganizationQuota, QuotaDefinition)
                .join(QuotaDefinition, QuotaDefinition.id == OrganizationQuota.quota_id)
                .where(
                    OrganizationQuota.organization_id == tenant.organization_id,
                    or_(OrganizationQuota.starts_at.is_(None), OrganizationQuota.starts_at <= now),
                    or_(OrganizationQuota.ends_at.is_(None), OrganizationQuota.ends_at > now),
                )
            )
        )
        .tuples()
        .all()
    )
    quotas: dict[str, QuotaSnapshot] = {}
    for organization_quota, definition in quota_rows:
        usage = await db.scalar(
            select(
                func.coalesce(func.sum(QuotaUsage.used_value + QuotaUsage.reserved_value), 0)
            ).where(
                QuotaUsage.organization_id == tenant.organization_id,
                QuotaUsage.quota_id == definition.id,
                or_(
                    QuotaUsage.workspace_id.is_(None),
                    QuotaUsage.workspace_id == tenant.workspace_id,
                ),
            )
        )
        used = int(usage or 0)
        quotas[definition.key] = QuotaSnapshot(
            limit=organization_quota.limit_value,
            used=used,
            reserved=0,
            remaining=max(organization_quota.limit_value - used, 0),
            hard=definition.is_hard_limit,
        )
    return AuthorizationContext(
        user_id=tenant.user_id,
        organization_id=tenant.organization_id,
        workspace_id=tenant.workspace_id,
        organization_role_key=tenant.organization_role,
        workspace_role_key=tenant.workspace_role,
        permissions=permissions,
        entitlements=entitlements,
        feature_flags=MappingProxyType(feature_flags),
        quotas=MappingProxyType(quotas),
        correlation_id=tenant.correlation_id,
    )


@dataclass(frozen=True, slots=True)
class GovernanceRequirement:
    permission: str
    feature: str | None = None
    entitlement: str | None = None
    quota: str | None = None
    amount: int = 1


async def authorize(
    db: AsyncSession, context: AuthorizationContext, requirement: GovernanceRequirement
) -> None:
    if (
        requirement.permission not in SYSTEM_PERMISSION_KEYS
        or requirement.permission not in context.permissions
    ):
        await _deny(db, context, "permission.denied", "PERMISSION_DENIED")
    if requirement.feature and not context.feature_flags.get(requirement.feature, False):
        await _deny(db, context, "feature.denied", "FEATURE_DISABLED")
    if requirement.entitlement and requirement.entitlement not in context.entitlements:
        await _deny(db, context, "entitlement.denied", "ENTITLEMENT_REQUIRED")
    if requirement.quota:
        quota = context.quotas.get(requirement.quota)
        if quota is None:
            await _deny(db, context, "quota.denied", "QUOTA_CONFIGURATION_MISSING")
        if quota.hard and quota.remaining < requirement.amount:
            await _deny(db, context, "quota.exceeded", "QUOTA_EXCEEDED")


async def authorize_capability(
    db: AsyncSession,
    context: AuthorizationContext,
    *,
    feature: str,
    entitlement: str,
) -> None:
    """Enforce platform availability when resource access is granted independently.

    Direct resource shares are additive to RBAC. They may grant access to one
    dashboard, but they must never bypass an organization feature flag or
    entitlement.
    """
    if not context.feature_flags.get(feature, False):
        await _deny(db, context, "feature.denied", "FEATURE_DISABLED")
    if entitlement not in context.entitlements:
        await _deny(db, context, "entitlement.denied", "ENTITLEMENT_REQUIRED")


async def authorize_any(
    db: AsyncSession, context: AuthorizationContext, permissions: frozenset[str]
) -> None:
    """Require at least one known permission without weakening unknown-key handling."""
    if not permissions or not permissions <= SYSTEM_PERMISSION_KEYS:
        await _deny(db, context, "permission.denied", "PERMISSION_DENIED")
    if context.permissions.isdisjoint(permissions):
        await _deny(db, context, "permission.denied", "PERMISSION_DENIED")


def _period_window(period: str, now: datetime) -> tuple[datetime, datetime | None]:
    if period == "monthly":
        start = datetime(now.year, now.month, 1, tzinfo=UTC)
        if now.month == 12:
            end = datetime(now.year + 1, 1, 1, tzinfo=UTC)
        else:
            end = datetime(now.year, now.month + 1, 1, tzinfo=UTC)
        return start, end
    if period == "daily":
        start = datetime(now.year, now.month, now.day, tzinfo=UTC)
        return start, start + timedelta(days=1)
    return datetime(1970, 1, 1, tzinfo=UTC), None


async def consume_quota(
    db: AsyncSession,
    context: AuthorizationContext,
    quota_key: str,
    *,
    amount: int = 1,
) -> QuotaUsage:
    """Atomically enforce and consume an organization quota inside the caller transaction."""
    if amount <= 0:
        raise ValueError("Quota consumption amount must be positive")
    row = (
        (
            await db.execute(
                select(OrganizationQuota, QuotaDefinition)
                .join(QuotaDefinition, QuotaDefinition.id == OrganizationQuota.quota_id)
                .where(
                    OrganizationQuota.organization_id == context.organization_id,
                    QuotaDefinition.key == quota_key,
                )
                .with_for_update(of=OrganizationQuota)
            )
        )
        .tuples()
        .one_or_none()
    )
    if row is None:
        await _deny(db, context, "quota.denied", "QUOTA_CONFIGURATION_MISSING")
    organization_quota, definition = row
    now = datetime.now(UTC)
    period_start, period_end = _period_window(definition.period, now)
    usage = await db.scalar(
        select(QuotaUsage)
        .where(
            QuotaUsage.organization_id == context.organization_id,
            QuotaUsage.workspace_id.is_(None),
            QuotaUsage.quota_id == definition.id,
            QuotaUsage.period_start == period_start,
        )
        .with_for_update()
    )
    used = (usage.used_value + usage.reserved_value) if usage else 0
    if definition.is_hard_limit and used + amount > organization_quota.limit_value:
        await _deny(db, context, "quota.exceeded", "QUOTA_EXCEEDED")
    if usage is None:
        usage = QuotaUsage(
            organization_id=context.organization_id,
            workspace_id=None,
            quota_id=definition.id,
            period_start=period_start,
            period_end=period_end,
            used_value=0,
            reserved_value=0,
        )
        db.add(usage)
    usage.used_value += amount
    await db.flush()
    return usage


async def release_quota(
    db: AsyncSession,
    context: AuthorizationContext,
    quota_key: str,
    *,
    amount: int = 1,
) -> None:
    """Atomically release a reusable capacity quota without allowing a negative balance."""
    if amount <= 0:
        raise ValueError("Quota release amount must be positive")
    row = (
        (
            await db.execute(
                select(OrganizationQuota, QuotaDefinition)
                .join(QuotaDefinition, QuotaDefinition.id == OrganizationQuota.quota_id)
                .where(
                    OrganizationQuota.organization_id == context.organization_id,
                    QuotaDefinition.key == quota_key,
                )
                .with_for_update(of=OrganizationQuota)
            )
        )
        .tuples()
        .one_or_none()
    )
    if row is None:
        await _deny(db, context, "quota.denied", "QUOTA_CONFIGURATION_MISSING")
    _, definition = row
    period_start, _ = _period_window(definition.period, datetime.now(UTC))
    usage = await db.scalar(
        select(QuotaUsage)
        .where(
            QuotaUsage.organization_id == context.organization_id,
            QuotaUsage.workspace_id.is_(None),
            QuotaUsage.quota_id == definition.id,
            QuotaUsage.period_start == period_start,
        )
        .with_for_update()
    )
    if usage is not None:
        usage.used_value = max(0, usage.used_value - amount)
        await db.flush()


async def _deny(
    db: AsyncSession, context: AuthorizationContext, event_type: str, reason_code: str
) -> Never:
    await record_audit(
        db,
        event_type,
        actor_user_id=context.user_id,
        organization_id=context.organization_id,
        workspace_id=context.workspace_id,
        outcome="denied",
        reason_code=reason_code,
        commit=True,
    )
    messages = {
        "PERMISSION_DENIED": "You do not have permission to perform this action.",
        "FEATURE_DISABLED": "This feature is currently unavailable.",
        "ENTITLEMENT_REQUIRED": "This capability is not available for the current organization.",
        "QUOTA_EXCEEDED": "The current organization has reached its allowed limit.",
        "QUOTA_CONFIGURATION_MISSING": "Quota configuration is unavailable.",
    }
    raise ApplicationError(code=reason_code, message=messages[reason_code], status_code=403)
