"""Tenant-scoped read endpoints for optional platform catalogs."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from vip_api.governance.context import AuthorizationContext
from vip_api.governance.dependencies import require_permission

router = APIRouter(tags=["platform-catalogs"])


def _workspace_reader() -> object:
    return Depends(require_permission("workspace.read"))


@router.get("/usage")
async def usage(
    context: Annotated[AuthorizationContext, _workspace_reader()],
) -> list[dict[str, object]]:
    """Expose real organization quota consumption to the operations UI."""
    return [
        {
            "label": key.replace("_", " ").replace(".", " ").title(),
            "used": quota.used + quota.reserved,
            "limit": quota.limit,
            "unit": "count",
        }
        for key, quota in sorted(context.quotas.items())
    ]


@router.get("/ai/conversations")
@router.get("/ai/assistants")
@router.get("/ai/knowledge")
@router.get("/ai/agents")
@router.get("/ai/agent-runs")
@router.get("/insights")
@router.get("/marketplace/extensions")
@router.get("/reports")
@router.get("/reports/templates")
@router.get("/reports/deliveries")
@router.get("/reports/exports")
async def empty_platform_catalog(
    _context: Annotated[AuthorizationContext, _workspace_reader()],
) -> list[dict[str, object]]:
    """Return an honest empty catalog when the tenant has no configured resources."""
    return []
