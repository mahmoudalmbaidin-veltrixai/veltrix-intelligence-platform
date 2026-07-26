"""Idempotent synchronization of checked-in system governance definitions."""

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.governance.models import (
    Entitlement,
    FeatureFlag,
    OrganizationEntitlement,
    OrganizationQuota,
    Permission,
    QuotaDefinition,
    Role,
    RolePermission,
)
from vip_api.governance.policies import (
    ENTITLEMENT_DEFINITIONS,
    FEATURE_DEFINITIONS,
    QUOTA_DEFINITIONS,
    SYSTEM_PERMISSIONS,
    SYSTEM_ROLE_PERMISSIONS,
    SYSTEM_ROLES,
)


async def seed_system_governance(db: AsyncSession) -> None:
    permissions: dict[str, Permission] = {}
    for permission_definition in SYSTEM_PERMISSIONS:
        permission = await db.scalar(
            select(Permission).where(Permission.key == permission_definition.key)
        )
        if permission is None:
            permission = Permission(
                key=permission_definition.key,
                name=permission_definition.name,
                scope=permission_definition.scope.value,
                category=permission_definition.category,
            )
            db.add(permission)
        else:
            permission.name, permission.scope, permission.category = (
                permission_definition.name,
                permission_definition.scope.value,
                permission_definition.category,
            )
        permissions[permission_definition.key] = permission
    roles: dict[str, Role] = {}
    for role_definition in SYSTEM_ROLES:
        role = await db.scalar(select(Role).where(Role.key == role_definition.key))
        if role is None:
            role = Role(
                key=role_definition.key,
                name=role_definition.name,
                scope=role_definition.scope.value,
                priority=role_definition.priority,
                is_assignable=role_definition.is_assignable,
            )
            db.add(role)
        else:
            role.name, role.scope, role.priority, role.is_assignable = (
                role_definition.name,
                role_definition.scope.value,
                role_definition.priority,
                role_definition.is_assignable,
            )
        roles[role_definition.key] = role
    await db.flush()
    await db.execute(
        delete(RolePermission).where(
            RolePermission.role_id.in_([role.id for role in roles.values()])
        )
    )
    db.add_all(
        RolePermission(role_id=roles[role].id, permission_id=permissions[permission].id)
        for role, values in SYSTEM_ROLE_PERMISSIONS.items()
        for permission in values
    )
    for key in ENTITLEMENT_DEFINITIONS:
        if await db.scalar(select(Entitlement.id).where(Entitlement.key == key)) is None:
            db.add(Entitlement(key=key, name=key.replace("_", " ").title()))
    for key, enabled in FEATURE_DEFINITIONS:
        item = await db.scalar(select(FeatureFlag).where(FeatureFlag.key == key))
        if item is None:
            db.add(
                FeatureFlag(key=key, name=key.replace("_", " ").title(), default_enabled=enabled)
            )
        else:
            item.default_enabled = enabled
    for key, unit, period, hard in QUOTA_DEFINITIONS:
        item = await db.scalar(select(QuotaDefinition).where(QuotaDefinition.key == key))
        if item is None:
            db.add(
                QuotaDefinition(
                    key=key,
                    name=key.replace(".", " ").title(),
                    unit=unit,
                    period=period,
                    is_hard_limit=hard,
                )
            )
        else:
            item.unit, item.period, item.is_hard_limit = unit, period, hard
    await db.commit()


DEFAULT_ORGANIZATION_ENTITLEMENTS = frozenset(
    {
        "dashboard_studio",
        "dashboard_publishing",
        "dashboard_sharing",
        "dashboard_snapshots",
        "dashboard_exports",
        "dashboard_delivery",
        "pipeline_studio",
        "dataset_studio",
        "report_studio",
        "advanced_audit",
        "marketplace",
        "connection_studio",
        "semantic_layer",
        "business_glossary",
        "data_quality",
        "data_lineage",
        "semantic_query",
    }
)
DEFAULT_ORGANIZATION_QUOTAS: dict[str, int] = {
    "users.max": 100,
    "workspaces.max": 10,
    "dashboards.max": 100,
    "dashboard_pages.max_per_dashboard": 50,
    "dashboard_widgets.max_per_dashboard": 250,
    "dashboard_versions.max_per_dashboard": 100,
    "dashboard_snapshots.max_per_dashboard": 100,
    "dashboard_queries.per_day": 10000,
    "dashboard_query_rows.max": 1000,
    "dashboard_exports.per_day": 1000,
    "dashboard_delivery_schedules.max": 100,
    "pipelines.max": 100,
    "pipeline_runs.monthly": 10_000,
    "ai_requests.monthly": 0,
    "connections.max": 25,
    "datasets.max": 500,
    "semantic_models.max": 100,
    "metrics.max": 1000,
    "glossary_terms.max": 1000,
    "metadata_discoveries.per_day": 100,
    "semantic_queries.per_day": 10000,
    "semantic_query_rows.max": 1000,
}


async def provision_organization_governance(db: AsyncSession, organization_id: UUID) -> None:
    """Attach explicit starter-contract grants to a new organization."""
    entitlements = list(
        (
            await db.scalars(
                select(Entitlement).where(Entitlement.key.in_(DEFAULT_ORGANIZATION_ENTITLEMENTS))
            )
        ).all()
    )
    existing_entitlements = set(
        (
            await db.scalars(
                select(OrganizationEntitlement.entitlement_id).where(
                    OrganizationEntitlement.organization_id == organization_id
                )
            )
        ).all()
    )
    db.add_all(
        OrganizationEntitlement(
            organization_id=organization_id,
            entitlement_id=entitlement.id,
            status="active",
            source="system",
        )
        for entitlement in entitlements
        if entitlement.id not in existing_entitlements
    )
    quotas = list(
        (
            await db.scalars(
                select(QuotaDefinition).where(QuotaDefinition.key.in_(DEFAULT_ORGANIZATION_QUOTAS))
            )
        ).all()
    )
    existing_quotas = set(
        (
            await db.scalars(
                select(OrganizationQuota.quota_id).where(
                    OrganizationQuota.organization_id == organization_id
                )
            )
        ).all()
    )
    db.add_all(
        OrganizationQuota(
            organization_id=organization_id,
            quota_id=quota.id,
            limit_value=DEFAULT_ORGANIZATION_QUOTAS[quota.key],
            source="system",
        )
        for quota in quotas
        if quota.id not in existing_quotas
    )
    await db.flush()
