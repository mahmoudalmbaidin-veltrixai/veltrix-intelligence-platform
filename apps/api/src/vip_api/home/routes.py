"""Production home aggregation endpoint."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from vip_api.auth.dependencies import require_csrf
from vip_api.connections.models import Connection
from vip_api.dashboards.models import Dashboard
from vip_api.database.session import get_db_session
from vip_api.datasets.models import Dataset
from vip_api.governance.context import AuthorizationContext
from vip_api.governance.dependencies import require_permission
from vip_api.governance.models import AuditEvent
from vip_api.home.models import NotificationRead
from vip_api.home.schemas import (
    ActivityEntry,
    ActivityFeedEntry,
    ChecklistItem,
    HealthMetric,
    HomeSummary,
    NotificationEntry,
    NotificationResource,
    RecentResource,
    UnreadCountResponse,
)
from vip_api.jobs.models import DeadLetterJob, Job
from vip_api.pipelines.models import Pipeline, PipelineRun
from vip_api.semantic.models import SemanticModel

router = APIRouter(prefix="/home", tags=["home"])
notifications_router = APIRouter(tags=["notifications"])

_ACTIVITY_DOMAINS = {
    "pipeline": "pipeline",
    "pipeline_run": "pipeline",
    "dataset": "dataset",
    "dashboard": "dashboard",
    "dashboard_export": "dashboard",
    "dashboard_delivery": "report",
    "report": "report",
    "semantic_model": "dataset",
    "connection": "admin",
    "organization": "admin",
    "workspace": "admin",
    "role": "admin",
    "membership": "admin",
    "billing": "billing",
    "automation": "automation",
    "ai": "ai",
}


def _scope(
    model: Any, context: AuthorizationContext
) -> tuple[ColumnElement[bool], ColumnElement[bool]]:
    return (
        getattr(model, "organization_id") == context.organization_id,  # noqa: B009
        getattr(model, "workspace_id") == context.workspace_id,  # noqa: B009
    )


async def _notification_feed(
    db: AsyncSession, context: AuthorizationContext
) -> list[NotificationEntry]:
    """Build the tenant-scoped derived notification feed (without read state)."""
    rows = (
        await db.scalars(
            select(Job)
            .where(*_scope(Job, context))
            .order_by(Job.updated_at.desc(), Job.id.desc())
            .limit(30)
        )
    ).all()
    result: list[NotificationEntry] = []
    for job in rows:
        if job.status not in {"succeeded", "failed", "cancelled", "retrying", "running"}:
            continue
        severity = {
            "succeeded": "success",
            "failed": "danger",
            "cancelled": "warning",
            "retrying": "warning",
            "running": "info",
        }[job.status]
        category = {
            "pipeline_run": "Pipelines",
            "dashboard_export": "Dashboards",
            "dashboard_delivery": "Reports",
            "dataset_quality": "Datasets",
        }.get(job.job_type, "System")
        result.append(
            NotificationEntry.model_validate(
                {
                    "id": f"job:{job.id}:{job.row_version}",
                    "severity": severity,
                    "title": f"{job.name}: {job.status.replace('_', ' ')}",
                    "body": job.progress_message
                    or f"{job.job_type.replace('_', ' ').title()} is {job.status}.",
                    "category": category,
                    "ts": job.updated_at,
                    "resource": NotificationResource(label="Open job", to=f"/jobs/{job.id}"),
                }
            )
        )
    return result


async def _read_ids(db: AsyncSession, context: AuthorizationContext) -> set[str]:
    """The notification ids this user has already marked read (per-user state)."""
    ids = await db.scalars(
        select(NotificationRead.notification_id).where(NotificationRead.user_id == context.user_id)
    )
    return set(ids)


@notifications_router.get("/notifications", response_model=list[NotificationEntry])
async def notifications(
    context: Annotated[AuthorizationContext, Depends(require_permission("workspace.read"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[NotificationEntry]:
    """Return tenant-scoped operational facts with each user's persisted read state."""
    feed = await _notification_feed(db, context)
    read_ids = await _read_ids(db, context)
    for entry in feed:
        entry.read = entry.id in read_ids
    return feed


@notifications_router.get("/notifications/unread-count", response_model=UnreadCountResponse)
async def unread_count(
    context: Annotated[AuthorizationContext, Depends(require_permission("workspace.read"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> UnreadCountResponse:
    """Authoritative unread count for the signed-in user — the badge source of truth."""
    feed = await _notification_feed(db, context)
    read_ids = await _read_ids(db, context)
    return UnreadCountResponse(count=sum(1 for entry in feed if entry.id not in read_ids))


async def _mark(db: AsyncSession, user_id: UUID, notification_ids: list[str]) -> None:
    """Persist read markers for a user, ignoring ids already read (idempotent)."""
    if not notification_ids:
        return
    now = datetime.now(UTC)
    await db.execute(
        pg_insert(NotificationRead)
        .values(
            [
                {"user_id": user_id, "notification_id": nid, "read_at": now}
                for nid in notification_ids
            ]
        )
        .on_conflict_do_nothing(constraint="uq_notification_reads_user_notification")
    )
    await db.commit()


@notifications_router.post(
    "/notifications/{notification_id}/read",
    response_model=UnreadCountResponse,
    dependencies=[Depends(require_csrf)],
)
async def mark_notification_read(
    notification_id: str,
    context: Annotated[AuthorizationContext, Depends(require_permission("workspace.read"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> UnreadCountResponse:
    """Persist a single notification as read for the signed-in user only.

    Read state is keyed by the session user id, so a user can never change
    another user's notification state. Only ids present in the caller's own
    tenant-scoped feed are accepted.
    """
    feed = await _notification_feed(db, context)
    if any(entry.id == notification_id for entry in feed):
        await _mark(db, context.user_id, [notification_id])
    read_ids = await _read_ids(db, context)
    return UnreadCountResponse(count=sum(1 for entry in feed if entry.id not in read_ids))


@notifications_router.delete(
    "/notifications/{notification_id}/read",
    response_model=UnreadCountResponse,
    dependencies=[Depends(require_csrf)],
)
async def unmark_notification_read(
    notification_id: str,
    context: Annotated[AuthorizationContext, Depends(require_permission("workspace.read"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> UnreadCountResponse:
    """Remove a single notification's read marker for the signed-in user only."""
    await db.execute(
        delete(NotificationRead).where(
            NotificationRead.user_id == context.user_id,
            NotificationRead.notification_id == notification_id,
        )
    )
    await db.commit()
    feed = await _notification_feed(db, context)
    read_ids = await _read_ids(db, context)
    return UnreadCountResponse(count=sum(1 for entry in feed if entry.id not in read_ids))


@notifications_router.post(
    "/notifications/read-all",
    response_model=UnreadCountResponse,
    dependencies=[Depends(require_csrf)],
)
async def mark_all_notifications_read(
    context: Annotated[AuthorizationContext, Depends(require_permission("workspace.read"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> UnreadCountResponse:
    """Persist every currently-unread notification as read for the signed-in user."""
    feed = await _notification_feed(db, context)
    read_ids = await _read_ids(db, context)
    await _mark(db, context.user_id, [entry.id for entry in feed if entry.id not in read_ids])
    return UnreadCountResponse(count=0)


@notifications_router.get("/activity", response_model=list[ActivityFeedEntry])
async def activity(
    context: Annotated[AuthorizationContext, Depends(require_permission("workspace.read"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[ActivityFeedEntry]:
    """Return the latest persisted tenant activity without synthetic feed items."""
    rows = (
        await db.scalars(
            select(AuditEvent)
            .where(*_scope(AuditEvent, context))
            .order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())
            .limit(100)
        )
    ).all()
    return [
        ActivityFeedEntry.model_validate(
            {
                "id": str(item.id),
                "domain": _ACTIVITY_DOMAINS.get(item.resource_type or "", "admin"),
                "actor": "You" if item.actor_user_id == context.user_id else "Platform",
                "action": item.action.replace("_", " "),
                "target": (
                    f"{item.resource_type.replace('_', ' ').title()} {str(item.resource_id)[:8]}"
                    if item.resource_type and item.resource_id
                    else (item.resource_type or "workspace").replace("_", " ").title()
                ),
                "ts": item.occurred_at,
            }
        )
        for item in rows
    ]


@router.get("/summary", response_model=HomeSummary)
async def summary(
    context: Annotated[AuthorizationContext, Depends(require_permission("workspace.read"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> HomeSummary:
    connection_total = await db.scalar(
        select(func.count()).select_from(Connection).where(*_scope(Connection, context))
    )
    connection_healthy = await db.scalar(
        select(func.count())
        .select_from(Connection)
        .where(*_scope(Connection, context), Connection.health_status == "healthy")
    )
    dataset_total = await db.scalar(
        select(func.count())
        .select_from(Dataset)
        .where(*_scope(Dataset, context), Dataset.status == "active")
    )
    run_total = await db.scalar(
        select(func.count()).select_from(PipelineRun).where(*_scope(PipelineRun, context))
    )
    run_succeeded = await db.scalar(
        select(func.count())
        .select_from(PipelineRun)
        .where(*_scope(PipelineRun, context), PipelineRun.status == "succeeded")
    )
    active_jobs = await db.scalar(
        select(func.count())
        .select_from(Job)
        .where(*_scope(Job, context), Job.status.in_(("queued", "running", "retrying")))
    )
    dead_letters = await db.scalar(
        select(func.count())
        .select_from(DeadLetterJob)
        .where(*_scope(DeadLetterJob, context), DeadLetterJob.status == "active")
    )
    totals = {
        "connections": int(connection_total or 0),
        "healthy_connections": int(connection_healthy or 0),
        "datasets": int(dataset_total or 0),
        "runs": int(run_total or 0),
        "successful_runs": int(run_succeeded or 0),
        "active_jobs": int(active_jobs or 0),
        "dead_letters": int(dead_letters or 0),
    }
    success_rate = (
        round(100 * totals["successful_runs"] / totals["runs"]) if totals["runs"] else 100
    )

    resources: list[RecentResource] = []
    resource_queries = (
        (
            Dashboard,
            Dashboard.name,
            Dashboard.updated_at,
            "Dashboard",
            "chart",
            "/dashboards/",
        ),
        (Pipeline, Pipeline.name, Pipeline.updated_at, "Pipeline", "workflow", "/pipelines/"),
        (Dataset, Dataset.display_name, Dataset.updated_at, "Dataset", "database", "/datasets/"),
        (
            SemanticModel,
            SemanticModel.name,
            SemanticModel.updated_at,
            "Semantic Model",
            "layers",
            "/semantic/",
        ),
    )
    for model, name_column, updated_column, type_name, icon, path in resource_queries:
        rows = (
            await db.execute(
                select(model.id, name_column, updated_column)
                .where(*_scope(model, context))
                .order_by(updated_column.desc())
                .limit(3)
            )
        ).all()
        resources.extend(
            RecentResource(
                id=str(item_id),
                name=name,
                type=type_name,
                icon=icon,
                to=f"{path}{item_id}",
                when=updated_at,
            )
            for item_id, name, updated_at in rows
        )
    resources.sort(key=lambda item: item.when, reverse=True)

    audit_rows = (
        await db.scalars(
            select(AuditEvent)
            .where(*_scope(AuditEvent, context))
            .order_by(AuditEvent.occurred_at.desc())
            .limit(8)
        )
    ).all()
    activity = [
        ActivityEntry(
            id=str(item.id),
            actor="You" if item.actor_user_id == context.user_id else "Platform",
            action=item.action.replace("_", " "),
            target=item.resource_type.replace("_", " ").title()
            if item.resource_type
            else "workspace",
            when=item.occurred_at,
            icon={
                "dashboard": "chart",
                "pipeline": "workflow",
                "dataset": "database",
                "connection": "plug",
            }.get(item.resource_type or "", "clock"),
        )
        for item in audit_rows
    ]

    dashboard_count = await db.scalar(
        select(func.count()).select_from(Dashboard).where(*_scope(Dashboard, context))
    )
    pipeline_count = await db.scalar(
        select(func.count()).select_from(Pipeline).where(*_scope(Pipeline, context))
    )
    semantic_count = await db.scalar(
        select(func.count()).select_from(SemanticModel).where(*_scope(SemanticModel, context))
    )
    checklist = [
        ChecklistItem(
            id="connection",
            label="Connect your first data source",
            done=totals["connections"] > 0,
            to="/connections/new",
        ),
        ChecklistItem(
            id="pipeline",
            label="Build a pipeline",
            done=int(pipeline_count or 0) > 0,
            to="/pipelines/new",
        ),
        ChecklistItem(
            id="semantic",
            label="Create a semantic model",
            done=int(semantic_count or 0) > 0,
            to="/semantic",
        ),
        ChecklistItem(
            id="dashboard",
            label="Author a dashboard",
            done=int(dashboard_count or 0) > 0,
            to="/dashboards/new",
        ),
    ]
    return HomeSummary(
        health=[
            HealthMetric(
                label="Connections healthy",
                value=f"{totals['healthy_connections']} / {totals['connections']}",
                tone="success"
                if totals["healthy_connections"] == totals["connections"]
                else "warning",
                icon="plug",
                spark=[totals["healthy_connections"]] * 7,
            ),
            HealthMetric(
                label="Pipeline success",
                value=f"{success_rate}%",
                tone="success" if success_rate >= 95 else "warning",
                icon="workflow",
                spark=[success_rate] * 7,
            ),
            HealthMetric(
                label="Active datasets",
                value=str(totals["datasets"]),
                tone="info",
                icon="database",
                spark=[totals["datasets"]] * 7,
            ),
            HealthMetric(
                label="Active jobs",
                value=str(totals["active_jobs"]),
                tone="danger" if totals["dead_letters"] else "neutral",
                icon="clock",
                spark=[totals["active_jobs"]] * 7,
            ),
        ],
        recent=resources[:8],
        activity=activity,
        checklist=checklist,
        pendingApprovals=0,
    )
