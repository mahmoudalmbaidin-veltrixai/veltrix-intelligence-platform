"""Tenant-, access-, version-, and data-qualified widget result cache."""

from __future__ import annotations

import hashlib
import json
import logging
from uuid import UUID

from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.core.config import Settings
from vip_api.dashboards.schemas import WidgetDataRequest, WidgetDataResponse, WidgetInput
from vip_api.datasets.models import Dataset
from vip_api.governance.context import AuthorizationContext
from vip_api.redis.client import RedisClient
from vip_api.semantic.models import SemanticModel, SemanticModelDataset

logger = logging.getLogger(__name__)


def _digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


async def cache_key(
    db: AsyncSession,
    context: AuthorizationContext,
    dashboard_id: UUID,
    published_version_id: UUID,
    published_version_number: int,
    widget: WidgetInput,
    payload: WidgetDataRequest,
    access: dict[str, bool],
    locale: str,
    timezone: str,
) -> str:
    assert context.workspace_id is not None
    assert widget.semantic_model_id is not None
    semantic = await db.execute(
        select(
            SemanticModel.published_version,
            SemanticModel.version,
            SemanticModel.primary_dataset_id,
        ).where(
            SemanticModel.id == widget.semantic_model_id,
            SemanticModel.organization_id == context.organization_id,
            SemanticModel.workspace_id == context.workspace_id,
        )
    )
    semantic_row = semantic.one()
    dataset_versions = list(
        (
            await db.execute(
                select(Dataset.id, Dataset.version)
                .outerjoin(
                    SemanticModelDataset,
                    SemanticModelDataset.dataset_id == Dataset.id,
                )
                .where(
                    Dataset.organization_id == context.organization_id,
                    Dataset.workspace_id == context.workspace_id,
                    (
                        (SemanticModelDataset.semantic_model_id == widget.semantic_model_id)
                        | (Dataset.id == semantic_row.primary_dataset_id)
                    ),
                )
                .order_by(Dataset.id)
            )
        ).tuples()
    )
    access_scope = {
        "user": str(context.user_id),
        "permissions": sorted(context.permissions),
        "entitlements": sorted(context.entitlements),
        "features": sorted(context.feature_flags.items()),
        "resource_access": sorted(access.items()),
    }
    dimensions = {
        "organization": str(context.organization_id),
        "workspace": str(context.workspace_id),
        "dashboard": str(dashboard_id),
        "published_version_id": str(published_version_id),
        "published_version": published_version_number,
        "widget": str(widget.id),
        "widget_contract": widget.model_dump(mode="json"),
        "filters": payload.filters,
        "limit": payload.limit_override,
        "semantic_model": str(widget.semantic_model_id),
        "semantic_version": [semantic_row.published_version, semantic_row.version],
        "dataset_versions": [(str(item[0]), item[1]) for item in dataset_versions],
        "access": access_scope,
        "locale": locale,
        "timezone": timezone,
    }
    return f"vip:dashboard-widget-data:{_digest(dimensions)}"


async def read_cache(
    redis_client: RedisClient | None,
    key: str,
    context: AuthorizationContext,
    settings: Settings,
) -> WidgetDataResponse | None:
    if not settings.DASHBOARD_QUERY_CACHE_ENABLED or redis_client is None:
        return None
    try:
        value = await redis_client.client.get(key)
        if value is None:
            return None
        result = WidgetDataResponse.model_validate_json(value)
        result.correlation_id = context.correlation_id
        result.execution = {**result.execution, "cache_hit": True}
        return result
    except (RedisError, ValueError):
        logger.warning("Dashboard widget cache read failed", exc_info=True)
        return None


async def write_cache(
    redis_client: RedisClient | None,
    key: str,
    result: WidgetDataResponse,
    settings: Settings,
) -> None:
    if (
        not settings.DASHBOARD_QUERY_CACHE_ENABLED
        or redis_client is None
        or settings.DASHBOARD_QUERY_CACHE_TTL_SECONDS <= 0
    ):
        return
    try:
        await redis_client.client.setex(
            key,
            settings.DASHBOARD_QUERY_CACHE_TTL_SECONDS,
            result.model_dump_json(),
        )
    except RedisError:
        logger.warning("Dashboard widget cache write failed", exc_info=True)
