"""Generic concurrent VIP job worker with durable leases and recovery."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import socket
import traceback
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from vip_api.core.config import Settings, get_settings
from vip_api.core.context import correlation_id_var
from vip_api.core.logging import configure_logging
from vip_api.database.session import Database
from vip_api.events.broker import RedisEventBroker
from vip_api.governance.audit import record_audit
from vip_api.jobs.models import (
    DeadLetterJob,
    Job,
    JobAttempt,
    JobError,
    JobLog,
    JobPayload,
    JobProgress,
    JobResult,
    WorkerHeartbeat,
)
from vip_api.jobs.queue import RedisJobQueue
from vip_api.jobs.registry import JobContextProtocol, registry
from vip_api.jobs.retry import JobExecutionError, RetryPolicy, RetryStrategy
from vip_api.redis.client import RedisClient

logger = logging.getLogger("vip_api.jobs.worker")


class JobCancelled(Exception):
    pass


class ExecutionContext(JobContextProtocol):
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        broker: RedisEventBroker,
        job_id: UUID,
    ) -> None:
        self._sessions = session_factory
        self._broker = broker
        self.job_id = job_id

    async def progress(
        self,
        percent: int,
        *,
        stage: str,
        message: str,
        completed_steps: int = 0,
        total_steps: int | None = None,
    ) -> None:
        async with self._sessions() as db:
            job = await db.get(Job, self.job_id)
            if job is None:
                return
            sequence = (
                int(
                    await db.scalar(
                        select(func.coalesce(func.max(JobProgress.sequence), 0)).where(
                            JobProgress.job_id == self.job_id
                        )
                    )
                    or 0
                )
                + 1
            )
            job.progress_percent = max(0, min(percent, 100))
            job.progress_step = completed_steps
            job.progress_total_steps = total_steps
            job.progress_stage = stage[:120]
            job.progress_message = message[:500]
            job.updated_at = datetime.now(UTC)
            job.row_version += 1
            db.add(
                JobProgress(
                    job_id=job.id,
                    sequence=sequence,
                    percent=job.progress_percent,
                    completed_steps=completed_steps,
                    total_steps=total_steps,
                    stage=job.progress_stage,
                    message=job.progress_message,
                )
            )
            await db.commit()
            await self._broker.publish(
                job.organization_id,
                job.workspace_id,
                "job.progress",
                {
                    "job_id": str(job.id),
                    "status": job.status,
                    "percent": job.progress_percent,
                    "stage": job.progress_stage,
                    "message": job.progress_message,
                },
            )

    async def cancellation_requested(self) -> bool:
        async with self._sessions() as db:
            value = await db.scalar(select(Job.cancellation_requested).where(Job.id == self.job_id))
            return bool(value)


class GenericJobWorker:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.database = Database(settings)
        self.redis = RedisClient(settings)
        self.queue = RedisJobQueue(self.redis.client, settings.JOB_QUEUE_PREFIX)
        self.broker = RedisEventBroker(
            self.redis.client, settings.JOB_QUEUE_PREFIX, settings.JOB_EVENT_STREAM_MAXLEN
        )
        self.worker_id = f"{socket.gethostname()}:{os.getpid()}"
        self.stop = asyncio.Event()
        self.active: set[asyncio.Task[None]] = set()

    async def run(self) -> None:
        self._install_signals()
        await self._heartbeat("running")
        try:
            while not self.stop.is_set():
                await self._recover_expired_leases()
                self.active = {task for task in self.active if not task.done()}
                capacity = self.settings.JOB_WORKER_CONCURRENCY - len(self.active)
                for _ in range(max(0, capacity)):
                    job_id = await self._next_job()
                    if job_id is None:
                        break
                    task = asyncio.create_task(self._execute(job_id))
                    self.active.add(task)
                await self._heartbeat("running")
                with suppress(TimeoutError):
                    await asyncio.wait_for(
                        self.stop.wait(), timeout=self.settings.JOB_WORKER_POLL_SECONDS
                    )
        finally:
            if self.active:
                await asyncio.gather(*self.active, return_exceptions=True)
            await self._heartbeat("stopped")
            await self.redis.close()
            await self.database.dispose()

    async def _next_job(self) -> UUID | None:
        for name in self.settings.JOB_WORKER_QUEUES:
            queued = await self.queue.dequeue(name)
            if queued is not None:
                return queued
        now = datetime.now(UTC)
        async with self.database.session_factory() as db:
            statement = (
                select(Job.id)
                .where(
                    Job.queue_name.in_(self.settings.JOB_WORKER_QUEUES),
                    Job.status.in_(("queued", "pending", "retrying")),
                    Job.available_at <= now,
                )
                .order_by(Job.priority.desc(), Job.available_at, Job.created_at)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            job_id: UUID | None = await db.scalar(statement)
            return job_id

    async def _recover_expired_leases(self) -> None:
        """Return abandoned work to the queue after a worker crash."""
        now = datetime.now(UTC)
        requeue: list[Job] = []
        async with self.database.session_factory() as db:
            jobs = (
                await db.scalars(
                    select(Job)
                    .where(
                        Job.status == "running",
                        Job.lease_expires_at.is_not(None),
                        Job.lease_expires_at < now,
                    )
                    .with_for_update(skip_locked=True)
                    .limit(self.settings.JOB_WORKER_CONCURRENCY * 2)
                )
            ).all()
            for item in jobs:
                attempt = await self._attempt(db, item)
                attempt.completed_at = now
                attempt.duration_ms = _duration_ms(attempt.started_at, now)
                attempt.error_code = "JOB_LEASE_EXPIRED"
                should_retry = item.current_attempt < item.max_attempts
                attempt.retryable = should_retry
                item.status = "retrying" if should_retry else "dead_letter"
                attempt.status = item.status
                item.available_at = now
                item.lease_owner = None
                item.lease_expires_at = None
                item.worker_id = None
                item.row_version += 1
                if should_retry:
                    requeue.append(item)
                else:
                    item.completed_at = now
                    payload = await db.get(JobPayload, item.id)
                    db.add(
                        DeadLetterJob(
                            job_id=item.id,
                            organization_id=item.organization_id,
                            workspace_id=item.workspace_id,
                            failure_reason="The worker lease expired.",
                            last_error_code="JOB_LEASE_EXPIRED",
                            worker_id=attempt.worker_id,
                            attempt_count=item.current_attempt,
                            payload_snapshot=payload.payload if payload else {},
                        )
                    )
                db.add(
                    JobError(
                        job_id=item.id,
                        attempt_number=item.current_attempt,
                        code="JOB_LEASE_EXPIRED",
                        safe_message="The worker lease expired.",
                        exception_type=None,
                        stack_trace=None,
                        retryable=should_retry,
                    )
                )
                await self._log(db, item, "WARNING", "Expired lease recovered")
                await record_audit(
                    db,
                    "job.lease.recovered",
                    actor_user_id=item.created_by_user_id,
                    organization_id=item.organization_id,
                    workspace_id=item.workspace_id,
                    outcome="failure",
                    reason_code="JOB_LEASE_EXPIRED",
                    resource_type="job",
                    resource_id=item.id,
                    metadata={"attempt": item.current_attempt, "retrying": should_retry},
                )
            await db.commit()
        for item in requeue:
            await self.queue.enqueue(item.queue_name, item.id, priority=item.priority)

    async def _execute(self, job_id: UUID) -> None:
        job = await self._claim(job_id)
        if job is None:
            return
        context = ExecutionContext(self.database.session_factory, self.broker, job.id)
        lease_task = asyncio.create_task(self._renew_lease(job.id))
        correlation_token = correlation_id_var.set(job.correlation_id)
        try:
            async with self.database.session_factory() as db:
                payload_row = await db.get(JobPayload, job.id)
                payload = payload_row.payload if payload_row else {}
            handler = registry.get(job.handler)
            if await context.cancellation_requested():
                raise JobCancelled
            result = await asyncio.wait_for(handler(context, payload), timeout=job.timeout_seconds)
            if await context.cancellation_requested():
                raise JobCancelled
            await self._succeed(job.id, result)
        except JobCancelled:
            await self._cancel(job.id)
        except TimeoutError:
            await self._fail(
                job.id, "JOB_TIMED_OUT", "The job timed out.", True, "TimeoutError", None
            )
        except JobExecutionError as exc:
            await self._fail(
                job.id,
                exc.code,
                exc.safe_message,
                exc.retryable,
                type(exc).__name__,
                traceback.format_exc(),
            )
        except Exception as exc:
            await self._fail(
                job.id,
                "JOB_EXECUTION_FAILED",
                "The job could not be completed.",
                False,
                type(exc).__name__,
                traceback.format_exc(),
            )
            logger.exception("Unhandled job failure", extra={"job_id": str(job.id)})
        finally:
            lease_task.cancel()
            with suppress(asyncio.CancelledError):
                await lease_task
            correlation_id_var.reset(correlation_token)

    async def _claim(self, job_id: UUID) -> Job | None:
        now = datetime.now(UTC)
        async with self.database.session_factory() as db:
            item = await db.scalar(
                select(Job).where(Job.id == job_id).with_for_update(skip_locked=True)
            )
            if item is None or item.status not in {"queued", "pending", "retrying"}:
                return None
            if item.available_at > now or item.cancellation_requested:
                return None
            item.status = "running"
            item.current_attempt += 1
            item.progress_percent = 0
            item.progress_step = 0
            item.progress_total_steps = None
            item.progress_stage = None
            item.progress_message = None
            item.worker_id = self.worker_id
            item.lease_owner = self.worker_id
            item.heartbeat_at = now
            item.lease_expires_at = now + self._lease_delta()
            item.started_at = item.started_at or now
            item.row_version += 1
            db.add(
                JobAttempt(
                    job_id=item.id,
                    attempt_number=item.current_attempt,
                    worker_id=self.worker_id,
                )
            )
            await self._log(db, item, "INFO", "Job started")
            await db.commit()
            await db.refresh(item)
            await self.broker.publish(
                item.organization_id,
                item.workspace_id,
                "job.started",
                {"job_id": str(item.id), "attempt": item.current_attempt},
            )
            return item

    async def _succeed(self, job_id: UUID, result: dict[str, object]) -> None:
        encoded_result = json.dumps(
            result, sort_keys=True, separators=(",", ":"), default=str
        ).encode()
        if len(encoded_result) > self.settings.JOB_MAX_RESULT_BYTES:
            raise JobExecutionError(
                "JOB_RESULT_TOO_LARGE",
                "The job result exceeded the configured size limit.",
                retryable=False,
            )
        async with self.database.session_factory() as db:
            item = await db.scalar(select(Job).where(Job.id == job_id).with_for_update())
            if item is None or not self._owns_active_lease(item):
                return
            now = datetime.now(UTC)
            item.status = "succeeded"
            item.progress_percent = 100
            item.completed_at = now
            item.updated_at = now
            item.lease_expires_at = None
            item.lease_owner = None
            item.row_version += 1
            attempt = await self._attempt(db, item)
            attempt.status = "succeeded"
            attempt.completed_at = now
            attempt.duration_ms = _duration_ms(attempt.started_at, now)
            result_file_id_value = result.get("file_id")
            result_file_id = (
                UUID(result_file_id_value) if isinstance(result_file_id_value, str) else None
            )
            size_value = result.get("size_bytes", 0)
            result_size = size_value if isinstance(size_value, int) else len(encoded_result)
            db.add(
                JobResult(
                    job_id=item.id,
                    result=result,
                    result_file_id=result_file_id,
                    size_bytes=result_size,
                )
            )
            await self._log(db, item, "INFO", "Job completed")
            await record_audit(
                db,
                "job.completed",
                actor_user_id=item.created_by_user_id,
                organization_id=item.organization_id,
                workspace_id=item.workspace_id,
                resource_type="job",
                resource_id=item.id,
                metadata={"job_type": item.job_type, "attempt": item.current_attempt},
            )
            await db.commit()
            await self.broker.publish(
                item.organization_id,
                item.workspace_id,
                "job.completed",
                {"job_id": str(item.id), "status": item.status},
            )

    async def _cancel(self, job_id: UUID) -> None:
        async with self.database.session_factory() as db:
            item = await db.scalar(select(Job).where(Job.id == job_id).with_for_update())
            if item is None or not self._owns_active_lease(item):
                return
            now = datetime.now(UTC)
            item.status = "cancelled"
            item.cancelled_at = now
            item.completed_at = now
            item.lease_owner = None
            item.lease_expires_at = None
            attempt = await self._attempt(db, item)
            attempt.status = "cancelled"
            attempt.completed_at = now
            attempt.duration_ms = _duration_ms(attempt.started_at, now)
            await record_audit(
                db,
                "job.cancelled",
                actor_user_id=item.cancelled_by_user_id or item.created_by_user_id,
                organization_id=item.organization_id,
                workspace_id=item.workspace_id,
                resource_type="job",
                resource_id=item.id,
            )
            await db.commit()
            await self.broker.publish(
                item.organization_id,
                item.workspace_id,
                "job.cancelled",
                {"job_id": str(item.id), "status": item.status},
            )

    async def _fail(
        self,
        job_id: UUID,
        code: str,
        safe_message: str,
        retryable: bool,
        exception_type: str,
        stack: str | None,
    ) -> None:
        async with self.database.session_factory() as db:
            item = await db.scalar(select(Job).where(Job.id == job_id).with_for_update())
            if item is None or not self._owns_active_lease(item):
                return
            now = datetime.now(UTC)
            attempt = await self._attempt(db, item)
            attempt.completed_at = now
            attempt.duration_ms = _duration_ms(attempt.started_at, now)
            attempt.retryable = retryable
            attempt.error_code = code
            db.add(
                JobError(
                    job_id=item.id,
                    attempt_number=item.current_attempt,
                    code=code,
                    safe_message=safe_message,
                    exception_type=exception_type,
                    stack_trace=stack,
                    retryable=retryable,
                )
            )
            await self._log(db, item, "ERROR", safe_message)
            should_retry = retryable and item.current_attempt < item.max_attempts
            if should_retry:
                policy = RetryPolicy(
                    RetryStrategy(item.retry_strategy),
                    item.retry_base_seconds,
                    item.retry_max_seconds,
                )
                delay = policy.delay(item.current_attempt)
                item.status = "retrying"
                item.available_at = now + delay
                attempt.status = "retrying"
            else:
                item.status = (
                    "dead_letter" if item.current_attempt >= item.max_attempts else "failed"
                )
                item.completed_at = now
                attempt.status = item.status
                if item.status == "dead_letter":
                    payload = await db.get(JobPayload, item.id)
                    db.add(
                        DeadLetterJob(
                            job_id=item.id,
                            organization_id=item.organization_id,
                            workspace_id=item.workspace_id,
                            failure_reason=safe_message,
                            last_error_code=code,
                            stack_trace=stack,
                            worker_id=self.worker_id,
                            attempt_count=item.current_attempt,
                            payload_snapshot=payload.payload if payload else {},
                        )
                    )
            item.lease_owner = None
            item.lease_expires_at = None
            item.updated_at = now
            item.row_version += 1
            await record_audit(
                db,
                "job.retry_scheduled" if should_retry else "job.failed",
                actor_user_id=item.created_by_user_id,
                organization_id=item.organization_id,
                workspace_id=item.workspace_id,
                outcome="failure",
                reason_code=code,
                resource_type="job",
                resource_id=item.id,
                metadata={"attempt": item.current_attempt, "retryable": retryable},
            )
            await db.commit()
            if should_retry:
                delay_seconds = max(0.0, (item.available_at - now).total_seconds())
                await self.queue.enqueue(
                    item.queue_name, item.id, priority=item.priority, delay_seconds=delay_seconds
                )
            await self.broker.publish(
                item.organization_id,
                item.workspace_id,
                "job.retry" if should_retry else "job.failed",
                {"job_id": str(item.id), "status": item.status, "error_code": code},
            )

    async def _renew_lease(self, job_id: UUID) -> None:
        while True:
            await asyncio.sleep(self.settings.JOB_HEARTBEAT_SECONDS)
            async with self.database.session_factory() as db:
                item = await db.get(Job, job_id)
                if item is None or item.status != "running" or item.lease_owner != self.worker_id:
                    return
                now = datetime.now(UTC)
                item.heartbeat_at = now
                item.lease_expires_at = now + self._lease_delta()
                await db.commit()

    async def _heartbeat(self, status: str) -> None:
        async with self.database.session_factory() as db:
            row = await db.get(WorkerHeartbeat, self.worker_id)
            now = datetime.now(UTC)
            if row is None:
                row = WorkerHeartbeat(
                    worker_id=self.worker_id,
                    queue_name=",".join(self.settings.JOB_WORKER_QUEUES),
                    hostname=socket.gethostname(),
                    process_id=os.getpid(),
                    concurrency=self.settings.JOB_WORKER_CONCURRENCY,
                    started_at=now,
                )
                db.add(row)
            row.status = status
            row.active_jobs = len(self.active)
            row.last_seen_at = now
            row.shutdown_at = now if status == "stopped" else None
            await db.commit()

    async def _attempt(self, db: AsyncSession, item: Job) -> JobAttempt:
        attempt = await db.scalar(
            select(JobAttempt).where(
                JobAttempt.job_id == item.id,
                JobAttempt.attempt_number == item.current_attempt,
            )
        )
        if attempt is None:
            raise RuntimeError("Job attempt record is missing")
        return attempt

    async def _log(self, db: AsyncSession, item: Job, level: str, message: str) -> None:
        sequence = (
            int(
                await db.scalar(
                    select(func.coalesce(func.max(JobLog.sequence), 0)).where(
                        JobLog.job_id == item.id
                    )
                )
                or 0
            )
            + 1
        )
        db.add(
            JobLog(
                job_id=item.id,
                sequence=sequence,
                attempt_number=item.current_attempt,
                level=level,
                message=message,
            )
        )

    def _lease_delta(self) -> timedelta:
        return timedelta(seconds=self.settings.JOB_LEASE_SECONDS)

    def _owns_active_lease(self, item: Job) -> bool:
        return item.status == "running" and item.lease_owner == self.worker_id

    def _install_signals(self) -> None:
        loop = asyncio.get_running_loop()
        for signal_name in (signal.SIGINT, signal.SIGTERM):
            with suppress(NotImplementedError):
                loop.add_signal_handler(signal_name, self.stop.set)


def _duration_ms(started: datetime, completed: datetime) -> int:
    return max(0, int((completed - started).total_seconds() * 1000))


async def _main() -> None:
    from vip_api.jobs import handlers as _handlers  # noqa: F401

    settings = get_settings()
    configure_logging(settings)
    await GenericJobWorker(settings).run()


if __name__ == "__main__":
    asyncio.run(_main())
