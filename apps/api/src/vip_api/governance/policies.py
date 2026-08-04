"""Deterministic system permissions, roles, and controlled role mappings."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class GovernanceScope(StrEnum):
    ORGANIZATION = "organization"
    WORKSPACE = "workspace"
    PLATFORM = "platform"


@dataclass(frozen=True, slots=True)
class PermissionDefinition:
    key: str
    name: str
    scope: GovernanceScope
    category: str


@dataclass(frozen=True, slots=True)
class RoleDefinition:
    key: str
    name: str
    scope: GovernanceScope
    priority: int
    is_assignable: bool = True


def _permission(key: str, scope: GovernanceScope, category: str) -> PermissionDefinition:
    return PermissionDefinition(key, key.replace(".", " ").title(), scope, category)


ORGANIZATION_PERMISSION_KEYS = (
    "organization.read",
    "organization.update",
    "organization.members.read",
    "organization.members.invite",
    "organization.members.update",
    "organization.members.remove",
    "workspace.create",
    "settings.read",
    "settings.update",
    "audit.read",
    "governance.read",
    "group.read",
    "group.create",
    "group.update",
    "group.delete",
    "group.members.manage",
    "role.read",
    "role.create",
    "role.update",
    "role.delete",
    "role.assign",
)
WORKSPACE_PERMISSION_KEYS = (
    "workspace.read",
    "workspace.update",
    "workspace.archive",
    "workspace.members.read",
    "workspace.members.manage",
    "resource.permissions.read",
    "resource.permissions.manage",
    "dashboard.read",
    "dashboard.create",
    "dashboard.update",
    "dashboard.archive",
    "dashboard.delete",
    "dashboard.publish",
    "dashboard.unpublish",
    "dashboard.versions.read",
    "dashboard.versions.restore",
    "dashboard.export",
    "dashboard.export.read",
    "dashboard.export.cancel",
    "dashboard.export.download",
    "dashboard.delivery.read",
    "dashboard.delivery.manage",
    "dashboard.delivery.send",
    "dashboard.share",
    "dashboard.permissions.manage",
    "dashboard.snapshot.create",
    "dashboard.snapshot.read",
    "dashboard.query",
    "dashboard.widget.read",
    "dashboard.widget.create",
    "dashboard.widget.update",
    "dashboard.widget.delete",
    "dashboard.filter.manage",
    "dashboard.layout.update",
    "pipeline.read",
    "pipeline.create",
    "pipeline.update",
    "pipeline.delete",
    "pipeline.execute",
    "pipeline.publish",
    "pipeline.versions.read",
    "pipeline.versions.restore",
    "pipeline.runs.read",
    "pipeline.runs.cancel",
    "pipeline.runs.retry",
    "job.read",
    "job.create",
    "job.cancel",
    "job.retry",
    "job.manage",
    "job.dead_letter",
    "file.upload",
    "file.download",
    "file.delete",
    "file.manage",
    "events.subscribe",
    "dataset.read",
    "dataset.create",
    "dataset.update",
    "dataset.delete",
    "dataset.archive",
    "dataset.discover",
    "dataset.metadata.refresh",
    "dataset.fields.read",
    "dataset.fields.update",
    "dataset.classification.update",
    "dataset.quality.read",
    "dataset.quality.manage",
    "dataset.quality.evaluate",
    "dataset.lineage.read",
    "dataset.lineage.manage",
    "semantic_model.read",
    "semantic_model.create",
    "semantic_model.update",
    "semantic_model.publish",
    "semantic_model.archive",
    "semantic_dimension.manage",
    "semantic_measure.manage",
    "semantic_metric.manage",
    "semantic_kpi.manage",
    "semantic.query",
    "glossary.read",
    "glossary.create",
    "glossary.update",
    "glossary.approve",
    "glossary.deprecate",
    "glossary.assign",
    "connection.read",
    "connection.create",
    "connection.update",
    "connection.delete",
    "connection.archive",
    "connection.test",
    "connection.credentials.update",
    "connection.credentials.rotate",
    "connection.health.read",
    "connection.types.read",
    "report.read",
    "report.create",
    "report.update",
    "report.delete",
    "report.schedule",
    "ai.read",
    "ai.use",
    "ai.configure",
)

SYSTEM_PERMISSIONS: tuple[PermissionDefinition, ...] = tuple(
    _permission(key, GovernanceScope.ORGANIZATION, key.split(".", 1)[0])
    for key in ORGANIZATION_PERMISSION_KEYS
) + tuple(
    _permission(key, GovernanceScope.WORKSPACE, key.split(".", 1)[0])
    for key in WORKSPACE_PERMISSION_KEYS
)
SYSTEM_PERMISSION_KEYS = frozenset(item.key for item in SYSTEM_PERMISSIONS)

SYSTEM_ROLES: tuple[RoleDefinition, ...] = (
    RoleDefinition(
        "organization_owner", "Organization Owner", GovernanceScope.ORGANIZATION, 100, False
    ),
    RoleDefinition(
        "organization_admin", "Organization Administrator", GovernanceScope.ORGANIZATION, 80
    ),
    RoleDefinition("organization_member", "Organization Member", GovernanceScope.ORGANIZATION, 10),
    RoleDefinition("workspace_admin", "Workspace Administrator", GovernanceScope.WORKSPACE, 70),
    RoleDefinition("editor", "Editor", GovernanceScope.WORKSPACE, 50),
    RoleDefinition("viewer", "Viewer", GovernanceScope.WORKSPACE, 30),
    RoleDefinition("restricted_user", "Restricted User", GovernanceScope.WORKSPACE, 10),
)
SYSTEM_ROLE_KEYS = frozenset(item.key for item in SYSTEM_ROLES)

_ALL_ORGANIZATION = frozenset(ORGANIZATION_PERMISSION_KEYS)
_ALL_WORKSPACE = frozenset(WORKSPACE_PERMISSION_KEYS)
_WORKSPACE_EDITOR = frozenset(
    {
        "workspace.read",
        "resource.permissions.read",
        "resource.permissions.manage",
        "dashboard.read",
        "dashboard.create",
        "dashboard.update",
        "dashboard.versions.read",
        "dashboard.versions.restore",
        "dashboard.snapshot.create",
        "dashboard.snapshot.read",
        "dashboard.query",
        "dashboard.widget.read",
        "dashboard.widget.create",
        "dashboard.widget.update",
        "dashboard.widget.delete",
        "dashboard.filter.manage",
        "dashboard.layout.update",
        "dashboard.export",
        "dashboard.export.read",
        "dashboard.export.cancel",
        "dashboard.export.download",
        "dashboard.delivery.read",
        "dashboard.delivery.manage",
        "dashboard.delivery.send",
        "dashboard.share",
        "pipeline.read",
        "pipeline.create",
        "pipeline.update",
        "pipeline.execute",
        "pipeline.publish",
        "pipeline.versions.read",
        "pipeline.versions.restore",
        "pipeline.runs.read",
        "pipeline.runs.cancel",
        "pipeline.runs.retry",
        "job.read",
        "job.create",
        "job.cancel",
        "job.retry",
        "file.upload",
        "file.download",
        "file.delete",
        "events.subscribe",
        "dataset.read",
        "dataset.create",
        "dataset.update",
        "dataset.discover",
        "dataset.metadata.refresh",
        "dataset.fields.read",
        "dataset.fields.update",
        "dataset.quality.read",
        "dataset.quality.manage",
        "dataset.lineage.read",
        "dataset.lineage.manage",
        "semantic_model.read",
        "semantic_model.create",
        "semantic_model.update",
        "semantic_dimension.manage",
        "semantic_measure.manage",
        "semantic_metric.manage",
        "semantic_kpi.manage",
        "semantic.query",
        "glossary.read",
        "glossary.create",
        "glossary.update",
        "glossary.assign",
        "connection.read",
        "connection.create",
        "connection.update",
        "connection.test",
        "connection.health.read",
        "connection.types.read",
        "report.read",
        "report.create",
        "report.update",
        "ai.read",
        "ai.use",
    }
)
_WORKSPACE_VIEWER = frozenset(
    {
        "workspace.read",
        "resource.permissions.read",
        "dashboard.read",
        "dashboard.versions.read",
        "dashboard.snapshot.read",
        "dashboard.query",
        "dashboard.widget.read",
        "pipeline.read",
        "job.read",
        "file.download",
        "events.subscribe",
        "dataset.read",
        "dataset.fields.read",
        "dataset.quality.read",
        "dataset.lineage.read",
        "semantic_model.read",
        "semantic.query",
        "glossary.read",
        "connection.read",
        "connection.health.read",
        "connection.types.read",
        "report.read",
        "ai.read",
    }
)

SYSTEM_ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "organization_owner": _ALL_ORGANIZATION | _ALL_WORKSPACE,
    "organization_admin": _ALL_ORGANIZATION | _ALL_WORKSPACE,
    "organization_member": frozenset({"organization.read", "workspace.read"}),
    "workspace_admin": _ALL_WORKSPACE,
    "editor": _WORKSPACE_EDITOR,
    "viewer": _WORKSPACE_VIEWER,
    "restricted_user": frozenset({"workspace.read"}),
}

FEATURE_DEFINITIONS: tuple[tuple[str, bool], ...] = (
    ("dashboard_studio", True),
    ("pipeline_studio", True),
    ("dataset_studio", True),
    # Placeholder modules gated OFF in live mode (no production backend yet):
    # report_studio/insights/marketplace/billing are recognized capability keys
    # but are not granted by DEFAULT_ORGANIZATION_ENTITLEMENTS, so their routes
    # resolve to the upgrade wall and their nav is hidden until the module ships.
    ("report_studio", True),
    ("insights", False),
    ("billing", False),
    ("ai_studio", False),
    ("advanced_audit", True),
    ("developer_api", False),
    ("marketplace", True),
    ("connection_studio", True),
    ("semantic_layer", True),
    ("business_glossary", True),
    ("data_quality", True),
    ("data_lineage", True),
    ("semantic_query", True),
    ("dashboard_publishing", True),
    ("dashboard_sharing", True),
    ("dashboard_snapshots", True),
    ("dashboard_exports", True),
    ("dashboard_delivery", True),
)
ENTITLEMENT_DEFINITIONS: tuple[str, ...] = tuple(key for key, _ in FEATURE_DEFINITIONS)
QUOTA_DEFINITIONS: tuple[tuple[str, str, str, bool], ...] = (
    ("users.max", "users", "none", True),
    ("workspaces.max", "workspaces", "none", True),
    ("dashboards.max", "dashboards", "none", True),
    ("pipelines.max", "pipelines", "none", True),
    ("pipeline_runs.monthly", "runs", "monthly", True),
    ("ai_requests.monthly", "requests", "monthly", True),
    ("connections.max", "connections", "none", True),
    ("datasets.max", "datasets", "none", True),
    ("semantic_models.max", "semantic models", "none", True),
    ("metrics.max", "metrics", "none", True),
    ("glossary_terms.max", "glossary terms", "none", True),
    ("metadata_discoveries.per_day", "discoveries", "daily", True),
    ("semantic_queries.per_day", "queries", "daily", True),
    ("semantic_query_rows.max", "rows", "none", True),
    ("dashboard_pages.max_per_dashboard", "pages", "none", True),
    ("dashboard_widgets.max_per_dashboard", "widgets", "none", True),
    ("dashboard_versions.max_per_dashboard", "versions", "none", True),
    ("dashboard_snapshots.max_per_dashboard", "snapshots", "none", True),
    ("dashboard_queries.per_day", "queries", "daily", True),
    ("dashboard_query_rows.max", "rows", "none", True),
    ("dashboard_exports.per_day", "exports", "daily", True),
    ("dashboard_delivery_schedules.max", "schedules", "none", True),
)


def validate_policy_catalog() -> None:
    permission_keys = [item.key for item in SYSTEM_PERMISSIONS]
    role_keys = [item.key for item in SYSTEM_ROLES]
    if len(permission_keys) != len(set(permission_keys)):
        raise RuntimeError("Duplicate system permission key")
    if len(role_keys) != len(set(role_keys)):
        raise RuntimeError("Duplicate system role key")
    for role_key, permissions in SYSTEM_ROLE_PERMISSIONS.items():
        if role_key not in SYSTEM_ROLE_KEYS or not permissions <= SYSTEM_PERMISSION_KEYS:
            raise RuntimeError(f"Invalid system role mapping: {role_key}")


validate_policy_catalog()
