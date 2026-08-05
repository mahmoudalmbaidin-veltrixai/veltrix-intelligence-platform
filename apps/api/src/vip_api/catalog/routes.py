"""Tenant-scoped read endpoints for optional platform catalogs."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from vip_api.core.config import AppEnvironment, Settings, get_settings
from vip_api.core.errors import ApplicationError
from vip_api.governance.context import AuthorizationContext
from vip_api.governance.dependencies import require_governance, require_permission

router = APIRouter(tags=["platform-catalogs"])
AI_CATALOG_IMPLEMENTED = False


def _workspace_reader() -> object:
    return Depends(require_permission("workspace.read"))


def _ai_reader() -> object:
    return Depends(
        require_governance(
            "workspace.read",
            feature="ai_studio",
            entitlement="ai_studio",
        )
    )


async def _available_ai_catalog(
    context: Annotated[AuthorizationContext, _ai_reader()],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthorizationContext:
    development_mock = settings.AI_DEVELOPMENT_MOCK_MODE and settings.APP_ENV in {
        AppEnvironment.DEVELOPMENT,
        AppEnvironment.TEST,
    }
    production_ready = settings.AI_CAPABILITIES_PRODUCTION_READY and AI_CATALOG_IMPLEMENTED
    if not development_mock and not production_ready:
        raise ApplicationError(
            code="AI_CAPABILITY_UNAVAILABLE",
            message="The requested AI capability is unavailable.",
            status_code=404,
        )
    return context


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
async def empty_ai_catalog(
    _context: Annotated[AuthorizationContext, Depends(_available_ai_catalog)],
) -> list[dict[str, object]]:
    """Return an empty catalog only after AI capability and readiness checks."""
    return []


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
