"""Structured audit-event interface for B2 tenant operations."""

import logging
from uuid import UUID

logger = logging.getLogger("vip_api.audit")


def audit_event(
    action: str,
    *,
    actor_user_id: UUID,
    organization_id: UUID,
    workspace_id: UUID | None = None,
    resource_type: str,
    resource_id: UUID | None = None,
    outcome: str = "success",
) -> None:
    """Emit a safe structured event; persistent audit storage is a later phase."""
    logger.info(
        "Tenant audit event",
        extra={
            "action": action,
            "actor_user_id": str(actor_user_id),
            "organization_id": str(organization_id),
            "workspace_id": str(workspace_id) if workspace_id else None,
            "resource_type": resource_type,
            "resource_id": str(resource_id) if resource_id else None,
            "outcome": outcome,
        },
    )
