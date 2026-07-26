"""Separately deployable, duplicate-safe PostgreSQL-backed pipeline worker."""

from __future__ import annotations

import asyncio
import logging
import os
import socket
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID

from sqlalchemy import func, or_, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from vip_api.connections.crypto import EnvironmentEncryptionKeyProvider
from vip_api.connections.secrets import DatabaseEncryptedSecretProvider
from vip_api.core.config import Settings, get_settings
from vip_api.core.errors import ApplicationError
from vip_api.core.logging import configure_logging
from vip_api.database.session import Database
from vip_api.governance.audit import record_audit
from vip_api.governance.context import AuthorizationContext
from vip_api.governance.services import (
    GovernanceRequirement,
    authorize,
    resolve_authorization_context,
)
from vip_api.pipelines.execution import execute_snapshot
from vip_api.pipelines.models import (
    PipelineArtifact,
    PipelineNodeRun,
    PipelineOutboxEvent,
    PipelineRun,
    PipelineRunAttempt,
    PipelineRunLog,
    PipelineVersion,
)
from vip_api.pipelines.schemas import NodeInput
from vip_api.pipelines.storage import PipelineArtifactStorage
from vip_api.tenancy.context import TenantContext
from vip_api.tenancy.models import MembershipStatus, OrganizationMembership, WorkspaceMembership

logger = logging.getLogger(__name__)


async def _context(db: AsyncSession, run: PipelineRun) -> AuthorizationContext:
    organization = await db.scalar(
        select(OrganizationMembership)
        .options(selectinload(OrganizationMembership.role))
        .where(
            OrganizationMembership.organization_id == run.organization_id,
            OrganizationMembership.user_id == run.requested_by_user_id,
            OrganizationMembership.status == MembershipStatus.ACTIVE,
        )
    )
    workspace = await db.scalar(
        select(WorkspaceMembership)
        .options(selectinload(WorkspaceMembership.role))
        .where(
            WorkspaceMembership.organization_id == run.organization_id,
            WorkspaceMembership.workspace_id == run.workspace_id,
            WorkspaceMembership.user_id == run.requested_by_user_id,
            WorkspaceMembership.status == MembershipStatus.ACTIVE,
        )
    )
    if organization is None or workspace is None:
        raise ApplicationError(
            code="PIPELINE_ACCESS_REVOKED",
            message="Pipeline execution access is no longer available.",
            status_code=403,
        )
    tenant = TenantContext(
        user_id=run.requested_by_user_id,
        organization_id=run.organization_id,
        workspace_id=run.workspace_id,
        organization_membership_id=organization.id,
        workspace_membership_id=workspace.id,
        organization_role=organization.role.key,
        workspace_role=workspace.role.key,
        correlation_id=run.correlation_id,
    )
    context = await resolve_authorization_context(db, tenant)
    await authorize(
        db, context, GovernanceRequirement("pipeline.execute", "pipeline_studio", "pipeline_studio")
    )
    return context


async def claim(
    db: AsyncSession,
    worker_id: str,
    settings: Settings,
    storage: PipelineArtifactStorage,
) -> PipelineRun | None:
    now = datetime.now(UTC)
    run = await db.scalar(
        select(PipelineRun)
        .where(
            or_(
                PipelineRun.status.in_(["queued", "retrying"]),
                (PipelineRun.status == "running") & (PipelineRun.lease_expires_at < now),
            ),
            PipelineRun.available_at <= now,
            PipelineRun.cancellation_requested.is_(False),
        )
        .order_by(PipelineRun.created_at)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if run is None:
        await db.rollback()
        return None
    recovering = run.status == "running"
    if recovering:
        previous_attempt = await db.scalar(
            select(PipelineRunAttempt).where(
                PipelineRunAttempt.run_id == run.id,
                PipelineRunAttempt.attempt_number == run.current_attempt,
            )
        )
        if previous_attempt:
            previous_attempt.status = "failed"
            previous_attempt.completed_at = now
            previous_attempt.safe_error_code = "PIPELINE_LEASE_EXPIRED"
            previous_attempt.safe_error_message = (
                "The worker lease expired before the attempt completed."
            )
        previous_nodes = (
            await db.scalars(
                select(PipelineNodeRun).where(
                    PipelineNodeRun.run_id == run.id,
                    PipelineNodeRun.attempt_number == run.current_attempt,
                )
            )
        ).all()
        for node_run in previous_nodes:
            if node_run.status == "running":
                node_run.status = "failed"
                node_run.safe_error_code = "PIPELINE_LEASE_EXPIRED"
                node_run.completed_at = now
            elif node_run.status == "queued":
                node_run.status = "skipped"
        abandoned_artifacts = (
            await db.scalars(select(PipelineArtifact).where(PipelineArtifact.run_id == run.id))
        ).all()
        for artifact in abandoned_artifacts:
            storage.delete(artifact.storage_key)
            await db.delete(artifact)
        await add_log(
            db,
            run,
            "warning",
            "Worker lease expired; the run is being recovered without reusing attempt artifacts.",
        )
        await record_audit(
            db,
            "pipeline.run.lease.recovered",
            actor_user_id=run.requested_by_user_id,
            organization_id=run.organization_id,
            workspace_id=run.workspace_id,
            resource_type="pipeline_run",
            resource_id=run.id,
            metadata={"abandoned_attempt": run.current_attempt},
        )
        run.rows_processed = 0
        run.result_summary = {}
    run.status = "running"
    run.current_attempt += 1
    run.started_at = run.started_at or now
    run.lease_owner = worker_id
    run.lease_expires_at = now + timedelta(seconds=settings.PIPELINE_WORKER_LEASE_SECONDS)
    run.progress = 0
    attempt = PipelineRunAttempt(
        organization_id=run.organization_id,
        workspace_id=run.workspace_id,
        run_id=run.id,
        attempt_number=run.current_attempt,
        status="running",
        worker_id=worker_id,
    )
    db.add(attempt)
    event = await db.scalar(
        select(PipelineOutboxEvent).where(
            PipelineOutboxEvent.run_id == run.id,
            PipelineOutboxEvent.attempt_number == run.current_attempt,
            PipelineOutboxEvent.published_at.is_(None),
        )
    )
    if event:
        event.published_at = now
    await db.commit()
    await db.refresh(run)
    return run


async def heartbeat_lease(
    database: Database,
    run_id: UUID,
    worker_id: str,
    settings: Settings,
    stop: asyncio.Event,
) -> None:
    """Renew a live run lease from an independent session.

    The executor session may be waiting on a source database, so using it for
    heartbeats would either be unsafe or leave the lease stale.
    """
    interval = max(0.25, min(settings.PIPELINE_WORKER_LEASE_SECONDS / 3, 5.0))
    while True:
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
            return
        except TimeoutError:
            pass
        async with database.session_factory() as heartbeat_db:
            result = cast(
                CursorResult[object],
                await heartbeat_db.execute(
                    update(PipelineRun)
                    .where(
                        PipelineRun.id == run_id,
                        PipelineRun.status == "running",
                        PipelineRun.lease_owner == worker_id,
                    )
                    .values(
                        lease_expires_at=datetime.now(UTC)
                        + timedelta(seconds=settings.PIPELINE_WORKER_LEASE_SECONDS)
                    )
                ),
            )
            if result.rowcount != 1:
                await heartbeat_db.rollback()
                raise RuntimeError("Pipeline worker lost its run lease")
            await heartbeat_db.commit()


async def add_log(
    db: AsyncSession, run: PipelineRun, level: str, message: str, node_key: str | None = None
) -> None:
    sequence = (
        await db.scalar(
            select(func.max(PipelineRunLog.sequence)).where(PipelineRunLog.run_id == run.id)
        )
        or 0
    ) + 1
    db.add(
        PipelineRunLog(
            organization_id=run.organization_id,
            workspace_id=run.workspace_id,
            run_id=run.id,
            sequence=sequence,
            attempt_number=run.current_attempt,
            node_key=node_key,
            level=level,
            message=message[:2000],
        )
    )


async def process(
    db: AsyncSession,
    run: PipelineRun,
    settings: Settings,
    provider: DatabaseEncryptedSecretProvider,
    storage: PipelineArtifactStorage,
) -> None:
    attempt = await db.scalar(
        select(PipelineRunAttempt).where(
            PipelineRunAttempt.run_id == run.id,
            PipelineRunAttempt.attempt_number == run.current_attempt,
        )
    )
    try:
        context = await _context(db, run)
        version = await db.scalar(
            select(PipelineVersion).where(
                PipelineVersion.id == run.pipeline_version_id,
                PipelineVersion.organization_id == run.organization_id,
                PipelineVersion.workspace_id == run.workspace_id,
            )
        )
        if version is None:
            raise ApplicationError(
                code="PIPELINE_VERSION_UNAVAILABLE",
                message="The published pipeline version is unavailable.",
                status_code=422,
            )
        nodes = [
            NodeInput.model_validate(item) for item in cast(list[object], version.snapshot["nodes"])
        ]
        for node in nodes:
            db.add(
                PipelineNodeRun(
                    organization_id=run.organization_id,
                    workspace_id=run.workspace_id,
                    run_id=run.id,
                    attempt_number=run.current_attempt,
                    node_key=node.key,
                    node_type=node.type,
                    status="queued",
                )
            )
        await add_log(
            db, run, "info", f"Published pipeline version {version.version_number} started."
        )
        await db.commit()
        # Node-level status is updated around the bounded executor in topological completion order.
        result = await asyncio.wait_for(
            execute_snapshot(db, context, run, version, settings, provider, storage),
            settings.PIPELINE_RUN_TIMEOUT_SECONDS,
        )
        await db.refresh(run, attribute_names=["cancellation_requested"])
        if run.cancellation_requested:
            raise ApplicationError(
                code="PIPELINE_RUN_CANCELLED",
                message="The pipeline run was cancelled.",
                status_code=409,
            )
        now = datetime.now(UTC)
        run.status = "succeeded"
        run.progress = 100
        run.completed_at = now
        run.result_summary = result
        run.lease_owner = None
        run.lease_expires_at = None
        if attempt:
            attempt.status = "succeeded"
            attempt.completed_at = now
        await add_log(db, run, "info", "Pipeline run completed successfully.")
        await record_audit(
            db,
            "pipeline.run.succeeded",
            actor_user_id=run.requested_by_user_id,
            organization_id=run.organization_id,
            workspace_id=run.workspace_id,
            resource_type="pipeline_run",
            resource_id=run.id,
            metadata={"attempt": run.current_attempt, "rows_processed": run.rows_processed},
        )
    except Exception as exc:
        now = datetime.now(UTC)
        cancelled = isinstance(exc, ApplicationError) and exc.code == "PIPELINE_RUN_CANCELLED"
        run.status = "cancelled" if cancelled else "failed"
        run.completed_at = now
        run.lease_owner = None
        run.lease_expires_at = None
        code = exc.code if isinstance(exc, ApplicationError) else "PIPELINE_EXECUTION_FAILED"
        message = (
            exc.message
            if isinstance(exc, ApplicationError)
            else "The pipeline run could not be completed."
        )
        run.safe_error_code, run.safe_error_message = code, message
        if attempt:
            failed_artifacts = (
                await db.scalars(
                    select(PipelineArtifact).where(
                        PipelineArtifact.run_id == run.id,
                        PipelineArtifact.created_at >= attempt.started_at,
                    )
                )
            ).all()
            for artifact in failed_artifacts:
                storage.delete(artifact.storage_key)
                await db.delete(artifact)
        node_runs = (
            await db.scalars(
                select(PipelineNodeRun).where(
                    PipelineNodeRun.run_id == run.id,
                    PipelineNodeRun.attempt_number == run.current_attempt,
                )
            )
        ).all()
        for node_run in node_runs:
            if node_run.status == "running":
                node_run.status = "cancelled" if cancelled else "failed"
                node_run.safe_error_code = code
                node_run.completed_at = now
            elif node_run.status == "queued":
                node_run.status = "cancelled" if cancelled else "skipped"
        if attempt:
            attempt.status = run.status
            attempt.completed_at = now
            attempt.safe_error_code = code
            attempt.safe_error_message = message
        await add_log(db, run, "warning" if cancelled else "error", message)
        await record_audit(
            db,
            f"pipeline.run.{run.status}",
            actor_user_id=run.requested_by_user_id,
            organization_id=run.organization_id,
            workspace_id=run.workspace_id,
            outcome="success" if cancelled else "failure",
            reason_code=code,
            resource_type="pipeline_run",
            resource_id=run.id,
            metadata={"attempt": run.current_attempt},
        )
        logger.exception("Pipeline run failed", extra={"run_id": str(run.id), "error_code": code})
    await db.commit()


async def serve() -> None:
    settings = get_settings()
    configure_logging(settings)
    database = Database(settings)
    provider = DatabaseEncryptedSecretProvider(EnvironmentEncryptionKeyProvider(settings))
    storage = PipelineArtifactStorage(settings.PIPELINE_ARTIFACT_ROOT)
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    logger.info("Pipeline worker started", extra={"worker_id": worker_id})
    try:
        while True:
            async with database.session_factory() as db:
                run = await claim(db, worker_id, settings, storage)
                if run is not None:
                    try:
                        stop_heartbeat = asyncio.Event()
                        process_task = asyncio.create_task(
                            process(db, run, settings, provider, storage)
                        )
                        heartbeat_task = asyncio.create_task(
                            heartbeat_lease(database, run.id, worker_id, settings, stop_heartbeat)
                        )
                        done, _ = await asyncio.wait(
                            {process_task, heartbeat_task},
                            return_when=asyncio.FIRST_COMPLETED,
                        )
                        if process_task in done:
                            stop_heartbeat.set()
                            await heartbeat_task
                            await process_task
                        else:
                            process_task.cancel()
                            with suppress(asyncio.CancelledError):
                                await process_task
                            await heartbeat_task
                    except Exception:
                        logger.exception(
                            "Pipeline run processing interrupted after lease failure",
                            extra={"run_id": str(run.id)},
                        )
            if run is None:
                await asyncio.sleep(settings.PIPELINE_WORKER_POLL_SECONDS)
    finally:
        await database.dispose()


if __name__ == "__main__":
    asyncio.run(serve())
