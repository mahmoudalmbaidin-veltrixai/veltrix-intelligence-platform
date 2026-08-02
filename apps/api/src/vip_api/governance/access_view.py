"""Shared response contract for a caller's effective access to a resource.

Embedded on Dataset / Connection / Semantic (and any resource) read responses so
the frontend can render viewer/editor/operator/manager/owner (and denied) states
and the Share control from the same centralized decision the API enforces.
``allowed_levels`` is the source of truth — the client maps the resource's level
ladder to per-capability booleans. Frontend visibility is never the security
boundary; every action is independently authorized server-side.
"""

from __future__ import annotations

from pydantic import BaseModel

from vip_api.governance.resource_access_service import ResourceAccessSummary


class ResourceEffectiveAccess(BaseModel):
    """The caller's effective access to a resource, per the centralized evaluator."""

    level: str | None
    allowed_levels: list[str]
    can_manage_access: bool
    source: str
    reason: str

    @classmethod
    def from_summary(cls, summary: ResourceAccessSummary) -> ResourceEffectiveAccess:
        return cls(
            level=summary.level,
            allowed_levels=summary.allowed_levels,
            can_manage_access=summary.can_manage_access,
            source=summary.source,
            reason=summary.reason,
        )
