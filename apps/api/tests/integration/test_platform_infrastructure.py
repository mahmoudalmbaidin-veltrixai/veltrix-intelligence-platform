"""B8 persistence, tenant isolation, queue and platform schema integration coverage."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select, text

from vip_api.auth.models import User, UserStatus
from vip_api.core.config import Settings
from vip_api.core.errors import ApplicationError
from vip_api.database.session import Database
from vip_api.governance.context import AuthorizationContext
from vip_api.jobs import handlers as _handlers  # noqa: F401
from vip_api.jobs.models import DeadLetterJob, Job, JobAttempt, JobError
from vip_api.jobs.queue import RedisJobQueue
from vip_api.jobs.registry import registry
from vip_api.jobs.retry import RetryableJobError
from vip_api.jobs.schemas import JobCreate
from vip_api.jobs.services import create_job, get_job, list_jobs
from vip_api.jobs.worker import GenericJobWorker
from vip_api.redis.client import RedisClient
from vip_api.tenancy.models import Organization, OrganizationStatus, Workspace, WorkspaceStatus


class RecordingQueue:
    def __init__(self) -> None:
        self.ids: list[UUID] = []

    async def enqueue(
        self, queue: str, job_id: UUID, *, priority: int = 0, delay_seconds: float = 0
    ) -> None:
        self.ids.append(job_id)

    async def dequeue(self, queue: str) -> UUID | None:
        return None

    async def metrics(self, queue: str):  # type: ignore[no-untyped-def]
        raise NotImplementedError


async def always_retry(_context, _payload):  # type: ignore[no-untyped-def]
    raise RetryableJobError("TRANSIENT_TEST_FAILURE", "The transient test failed.")


registry.register("test.always_retry", always_retry)


def context(user: UUID, organization: UUID, workspace: UUID) -> AuthorizationContext:
    return AuthorizationContext(
        user_id=user,
        organization_id=organization,
        workspace_id=workspace,
        organization_role_key="organization_admin",
        workspace_role_key="workspace_admin",
        permissions=frozenset({"job.read", "job.create"}),
        entitlements=frozenset(),
        feature_flags={},
        quotas={},
        correlation_id="b8-integration",
    )


@pytest.mark.integration
@pytest.mark.security
@pytest.mark.asyncio
async def test_job_persistence_and_tenant_isolation(settings: Settings) -> None:
    database = Database(settings)
    try:
        async with database.session_factory() as db:
            tables = set(
                (
                    await db.scalars(
                        text(
                            "SELECT table_name FROM information_schema.tables "
                            "WHERE table_schema='public'"
                        )
                    )
                ).all()
            )
            assert {
                "jobs",
                "job_attempts",
                "job_progress",
                "job_logs",
                "job_errors",
                "dead_letter_jobs",
                "files",
                "file_versions",
                "file_download_tokens",
            } <= tables
            user = User(
                email=f"b8-{uuid4().hex}@vip.test",
                normalized_email=f"b8-{uuid4().hex}@vip.test",
                display_name="B8 Test",
                password_hash="unused",
                status=UserStatus.ACTIVE,
            )
            db.add(user)
            await db.flush()
            alpha = Organization(
                name="B8 Alpha",
                slug=f"b8-alpha-{uuid4().hex[:8]}",
                status=OrganizationStatus.ACTIVE,
                created_by_user_id=user.id,
            )
            beta = Organization(
                name="B8 Beta",
                slug=f"b8-beta-{uuid4().hex[:8]}",
                status=OrganizationStatus.ACTIVE,
                created_by_user_id=user.id,
            )
            db.add_all((alpha, beta))
            await db.flush()
            alpha_ws = Workspace(
                organization_id=alpha.id,
                name="Alpha",
                slug="alpha",
                status=WorkspaceStatus.ACTIVE,
                is_default=True,
                created_by_user_id=user.id,
            )
            beta_ws = Workspace(
                organization_id=beta.id,
                name="Beta",
                slug="beta",
                status=WorkspaceStatus.ACTIVE,
                is_default=True,
                created_by_user_id=user.id,
            )
            db.add_all((alpha_ws, beta_ws))
            await db.commit()
            queue = RecordingQueue()
            created = await create_job(
                db,
                context(user.id, alpha.id, alpha_ws.id),
                JobCreate(
                    job_type="system",
                    handler="platform.noop",
                    name="Isolation test",
                    idempotency_key=f"b8:{uuid4()}",
                ),
                settings,
                queue,
                registry,
            )
            assert queue.ids == [created.id]
            assert (
                len(
                    (
                        await list_jobs(
                            db,
                            context(user.id, alpha.id, alpha_ws.id),
                            limit=10,
                            before=None,
                            status=None,
                        )
                    ).items
                )
                == 1
            )
            with pytest.raises(ApplicationError) as hidden:
                await get_job(db, context(user.id, beta.id, beta_ws.id), created.id)
            assert hidden.value.status_code == 404
            worker = GenericJobWorker(settings)
            try:
                await worker._execute(created.id)
                completed = await db.get(Job, created.id)
                assert completed is not None
                await db.refresh(completed)
                assert completed.status == "succeeded"
                assert completed.progress_percent == 100

                doomed = await create_job(
                    db,
                    context(user.id, alpha.id, alpha_ws.id),
                    JobCreate(
                        job_type="system",
                        handler="test.always_retry",
                        name="Dead-letter test",
                        idempotency_key=f"b8:{uuid4()}",
                        max_attempts=1,
                    ),
                    settings,
                    queue,
                    registry,
                )
                await worker._execute(doomed.id)
                dead = await db.get(Job, doomed.id)
                assert dead is not None
                await db.refresh(dead)
                assert dead.status == "dead_letter"

                expired = await create_job(
                    db,
                    context(user.id, alpha.id, alpha_ws.id),
                    JobCreate(
                        job_type="system",
                        handler="platform.noop",
                        name="Expired lease test",
                        idempotency_key=f"b8:{uuid4()}",
                        max_attempts=1,
                    ),
                    settings,
                    queue,
                    registry,
                )
                assert await worker._claim(expired.id) is not None
                async with worker.database.session_factory() as worker_db:
                    running = await worker_db.get(Job, expired.id)
                    assert running is not None
                    running.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
                    await worker_db.commit()
                await worker._recover_expired_leases()
                expired_job = await db.get(Job, expired.id)
                assert expired_job is not None
                await db.refresh(expired_job)
                attempt = await db.scalar(select(JobAttempt).where(JobAttempt.job_id == expired.id))
                lease_error = await db.scalar(
                    select(JobError).where(
                        JobError.job_id == expired.id,
                        JobError.code == "JOB_LEASE_EXPIRED",
                    )
                )
                dead_letter = await db.scalar(
                    select(DeadLetterJob).where(DeadLetterJob.job_id == expired.id)
                )
                assert expired_job.status == "dead_letter"
                assert attempt is not None and attempt.status == "dead_letter"
                assert attempt.completed_at is not None
                assert lease_error is not None and lease_error.retryable is False
                assert dead_letter is not None and dead_letter.attempt_count == 1
            finally:
                await worker.redis.close()
                await worker.database.dispose()
            await db.execute(delete(Organization).where(Organization.id.in_([alpha.id, beta.id])))
            await db.execute(delete(User).where(User.id == user.id))
            await db.commit()
    finally:
        await database.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_redis_priority_queue_round_trip(settings: Settings) -> None:
    redis = RedisClient(settings)
    queue = RedisJobQueue(redis.client, f"{settings.JOB_QUEUE_PREFIX}:integration:{uuid4()}")
    try:
        low, high = uuid4(), uuid4()
        await queue.enqueue("test", low, priority=0)
        await queue.enqueue("test", high, priority=100)
        assert await queue.dequeue("test") == high
        assert await queue.dequeue("test") == low
        assert await queue.dequeue("test") is None
    finally:
        await redis.close()
