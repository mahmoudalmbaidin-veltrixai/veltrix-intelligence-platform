"""Append-only governance audit persistence with safe structured-log fallback."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.core.context import get_correlation_id
from vip_api.governance.models import AuditEvent

logger = logging.getLogger("vip_api.governance.audit")


async def record_audit(
    db: AsyncSession,
    event_type: str,
    *,
    actor_user_id: UUID | None,
    organization_id: UUID | None,
    workspace_id: UUID | None = None,
    outcome: str = "success",
    reason_code: str | None = None,
    resource_type: str | None = None,
    resource_id: UUID | None = None,
    metadata: dict[str, object] | None = None,
    commit: bool = False,
) -> AuditEvent:
    event = AuditEvent(
        actor_user_id=actor_user_id,
        organization_id=organization_id,
        workspace_id=workspace_id,
        correlation_id=get_correlation_id(),
        event_type=event_type,
        action=event_type,
        outcome=outcome,
        reason_code=reason_code,
        resource_type=resource_type,
        resource_id=resource_id,
        event_metadata=metadata or {},
    )
    db.add(event)
    await db.flush()
    if commit:
        await db.commit()
    logger.info(
        "Governance audit event",
        extra={
            "event_type": event_type,
            "actor_user_id": str(actor_user_id) if actor_user_id else None,
            "organization_id": str(organization_id) if organization_id else None,
            "workspace_id": str(workspace_id) if workspace_id else None,
            "outcome": outcome,
            "reason_code": reason_code,
        },
    )
    return event
