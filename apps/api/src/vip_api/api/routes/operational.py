"""Unversioned liveness and readiness endpoints."""

import asyncio
import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import text

from vip_api.core.config import Settings
from vip_api.core.metrics import metrics
from vip_api.database.health import check_database
from vip_api.database.session import Database, get_database
from vip_api.jobs.queue import RedisJobQueue
from vip_api.redis.client import RedisClient
from vip_api.redis.health import check_redis
from vip_api.schemas.health import (
    DependencyCheck,
    HealthResponse,
    ReadinessChecks,
    ReadinessResponse,
)

router = APIRouter(tags=["operations"])
_SAFE_LABEL = re.compile(r"[^a-zA-Z0-9_.:-]")


def get_redis_client(request: Request) -> RedisClient:
    redis_client: RedisClient = request.app.state.redis
    return redis_client


def get_app_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


@router.get("/health", response_model=HealthResponse)
async def health(settings: Annotated[Settings, Depends(get_app_settings)]) -> HealthResponse:
    """Report process liveness without touching external dependencies."""
    return HealthResponse(
        status="healthy",
        service=settings.SERVICE_NAME,
        version=settings.APP_VERSION,
    )


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadinessResponse}},
)
async def readiness(
    response: Response,
    settings: Annotated[Settings, Depends(get_app_settings)],
    database: Annotated[Database, Depends(get_database)],
    redis_client: Annotated[RedisClient, Depends(get_redis_client)],
) -> ReadinessResponse:
    """Check required dependencies concurrently with bounded timeouts."""
    database_healthy, redis_healthy = await asyncio.gather(
        check_database(database, settings.DATABASE_CONNECT_TIMEOUT),
        check_redis(redis_client, settings.REDIS_SOCKET_TIMEOUT),
    )
    ready = database_healthy and redis_healthy
    metrics.dependencies(database=database_healthy, redis=redis_healthy)
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(
        status="ready" if ready else "not_ready",
        checks=ReadinessChecks(
            database=DependencyCheck(status="healthy" if database_healthy else "unhealthy"),
            redis=DependencyCheck(status="healthy" if redis_healthy else "unhealthy"),
        ),
    )


@router.get("/metrics", response_class=PlainTextResponse, include_in_schema=False)
async def prometheus_metrics(
    settings: Annotated[Settings, Depends(get_app_settings)],
    database: Annotated[Database, Depends(get_database)],
    redis_client: Annotated[RedisClient, Depends(get_redis_client)],
    authorization: Annotated[str | None, Header()] = None,
) -> PlainTextResponse:
    """Expose bounded process metrics without tenant or user labels."""
    if not settings.METRICS_ENABLED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    expected = settings.metrics_bearer_token
    supplied = authorization.removeprefix("Bearer ").strip() if authorization else ""
    if expected is not None and not secrets.compare_digest(supplied, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": "Bearer"},
        )
    database_healthy, redis_healthy = await asyncio.gather(
        check_database(database, settings.DATABASE_CONNECT_TIMEOUT),
        check_redis(redis_client, settings.REDIS_SOCKET_TIMEOUT),
    )
    metrics.dependencies(database=database_healthy, redis=redis_healthy)
    platform_metrics = await _platform_metrics(database, redis_client, settings)
    return PlainTextResponse(
        metrics.render() + platform_metrics,
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


async def _platform_metrics(
    database: Database, redis_client: RedisClient, settings: Settings
) -> str:
    """Collect cross-tenant aggregate operational metrics without identifiers."""
    lines = [
        "# TYPE vip_workers_active gauge",
        "# TYPE vip_workers_stale gauge",
        "# TYPE vip_jobs_by_state gauge",
        "# TYPE vip_pipeline_runs_by_state gauge",
        "# TYPE vip_dashboard_exports_by_state gauge",
        "# TYPE vip_dashboard_deliveries_by_state gauge",
    ]
    cutoff = datetime.now(UTC) - timedelta(seconds=max(settings.JOB_HEARTBEAT_SECONDS * 3, 30))
    now = datetime.now(UTC)
    try:
        async with database.session_factory() as db:
            workers = (
                await db.execute(
                    text(
                        """
                        SELECT
                          count(*) FILTER (WHERE status = 'running' AND last_seen_at >= :cutoff),
                          count(*) FILTER (WHERE status = 'running' AND last_seen_at < :cutoff)
                        FROM worker_heartbeats
                        """
                    ),
                    {"cutoff": cutoff},
                )
            ).one()
            lines.extend([f"vip_workers_active {workers[0]}", f"vip_workers_stale {workers[1]}"])
            grouped = (
                await db.execute(
                    text(
                        """
                        SELECT 'vip_jobs_by_state', status, count(*) FROM jobs GROUP BY status
                        UNION ALL
                        SELECT 'vip_pipeline_runs_by_state', status, count(*)
                          FROM pipeline_runs GROUP BY status
                        UNION ALL
                        SELECT 'vip_dashboard_exports_by_state', status, count(*)
                          FROM dashboard_exports GROUP BY status
                        UNION ALL
                        SELECT 'vip_dashboard_deliveries_by_state', status, count(*)
                          FROM dashboard_delivery_runs GROUP BY status
                        """
                    )
                )
            ).all()
            for name, state, value in grouped:
                safe_state = _SAFE_LABEL.sub("_", str(state))[:32]
                lines.append(f'{name}{{state="{safe_state}"}} {value}')
            totals = (
                await db.execute(
                    text(
                        """
                        SELECT
                          (SELECT coalesce(sum(current_attempt), 0) FROM jobs),
                          (SELECT count(*) FROM jobs WHERE current_attempt > 1),
                          (SELECT count(*) FROM jobs WHERE status = 'failed'),
                          (SELECT count(*) FROM dead_letter_jobs),
                          (SELECT count(*) FROM jobs WHERE status = 'cancelled'),
                          (SELECT count(*) FROM jobs
                            WHERE status = 'running' AND lease_expires_at < :now),
                          (SELECT count(*) FROM jobs WHERE current_attempt > 1),
                          (SELECT coalesce(sum(rows_processed), 0) FROM pipeline_runs),
                          (SELECT coalesce(sum(rows_in), 0) FROM pipeline_node_runs),
                          (SELECT coalesce(sum(rows_out), 0) FROM pipeline_node_runs),
                          (SELECT count(*) FROM pipeline_runs WHERE current_attempt > 1),
                          (SELECT count(*) FROM pipeline_runs WHERE status = 'cancelled'),
                          (SELECT count(*) FROM pipeline_runs
                            WHERE status = 'running' AND lease_expires_at < :now),
                          (SELECT count(*) FROM pipeline_artifacts),
                          (SELECT count(*) FROM pipeline_runs
                            WHERE status = 'failed'
                              AND safe_error_code LIKE '%ARTIFACT%'),
                          (SELECT count(*) FROM dashboard_exports WHERE attempts > 1),
                          (SELECT count(*) FROM dashboard_delivery_runs WHERE attempt > 1),
                          (SELECT count(*) FROM dashboard_delivery_schedules
                            WHERE enabled AND next_run_at < :now)
                        """
                    ),
                    {"now": now},
                )
            ).one()
            names = [
                "vip_job_attempts_total",
                "vip_job_retries_total",
                "vip_job_failures_total",
                "vip_job_dead_letters",
                "vip_job_cancellations_total",
                "vip_job_stale_leases",
                "vip_job_recoveries_total",
                "vip_pipeline_rows_processed_total",
                "vip_pipeline_input_rows_total",
                "vip_pipeline_output_rows_total",
                "vip_pipeline_retries_total",
                "vip_pipeline_cancellations_total",
                "vip_pipeline_stale_leases",
                "vip_pipeline_artifacts_total",
                "vip_pipeline_artifact_failures_total",
                "vip_dashboard_export_retries_total",
                "vip_dashboard_delivery_retries_total",
                "vip_dashboard_scheduled_jobs_late",
            ]
            lines.extend(f"{name} {value}" for name, value in zip(names, totals, strict=True))
            durations = (
                await db.execute(
                    text(
                        """
                        SELECT
                          (SELECT coalesce(sum(extract(epoch FROM completed_at - started_at)), 0)
                            FROM jobs WHERE completed_at IS NOT NULL AND started_at IS NOT NULL),
                          (SELECT count(*) FROM jobs
                            WHERE completed_at IS NOT NULL AND started_at IS NOT NULL),
                          (SELECT coalesce(sum(extract(epoch FROM completed_at - started_at)), 0)
                            FROM pipeline_runs
                            WHERE completed_at IS NOT NULL AND started_at IS NOT NULL),
                          (SELECT count(*) FROM pipeline_runs
                            WHERE completed_at IS NOT NULL AND started_at IS NOT NULL),
                          (SELECT coalesce(sum(extract(epoch FROM completed_at - started_at)), 0)
                            FROM dashboard_exports
                            WHERE completed_at IS NOT NULL AND started_at IS NOT NULL),
                          (SELECT count(*) FROM dashboard_exports
                            WHERE completed_at IS NOT NULL AND started_at IS NOT NULL),
                          (SELECT coalesce(sum(extract(epoch FROM completed_at - created_at)), 0)
                            FROM dashboard_delivery_runs WHERE completed_at IS NOT NULL),
                          (SELECT count(*) FROM dashboard_delivery_runs
                            WHERE completed_at IS NOT NULL)
                        """
                    )
                )
            ).one()
            duration_names = [
                "vip_job_duration_seconds",
                "vip_pipeline_run_duration_seconds",
                "vip_dashboard_export_duration_seconds",
                "vip_dashboard_delivery_duration_seconds",
            ]
            for index, name in enumerate(duration_names):
                lines.extend(
                    [
                        f"# TYPE {name} summary",
                        f"{name}_sum {durations[index * 2]}",
                        f"{name}_count {durations[index * 2 + 1]}",
                    ]
                )
    except Exception:
        lines.append("vip_platform_metrics_collection_error 1")
    else:
        lines.append("vip_platform_metrics_collection_error 0")

    queue = RedisJobQueue(redis_client.client, settings.JOB_QUEUE_PREFIX)
    for name in settings.JOB_WORKER_QUEUES:
        safe_name = _SAFE_LABEL.sub("_", name)[:80]
        try:
            queue_metrics = await queue.metrics(name)
            lines.extend(
                [
                    (
                        f'vip_job_queue_depth{{queue="{safe_name}",state="ready"}} '
                        f"{queue_metrics.ready}"
                    ),
                    (
                        f'vip_job_queue_depth{{queue="{safe_name}",state="delayed"}} '
                        f"{queue_metrics.delayed}"
                    ),
                ]
            )
        except Exception:
            lines.append(f'vip_job_queue_collection_error{{queue="{safe_name}"}} 1')
    return "\n".join(lines) + "\n"
