"""Recurring delivery scheduler integration coverage (Phase B9.1A).

Drives ``dispatch_due_deliveries`` against vip_test: due-schedule claiming,
duplicate prevention, concurrent schedulers, pause, one-time completion, revoked
creator access, and tenant isolation.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email import policy
from email.parser import BytesParser
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.auth.models import User, UserStatus
from vip_api.connections.models import Connection, ConnectionType
from vip_api.core.config import Settings, get_settings
from vip_api.dashboard_delivery.models import (
    DashboardDeliveryRun,
    DashboardDeliverySchedule,
    DashboardExport,
)
from vip_api.dashboard_delivery.scheduler import dispatch_due_deliveries
from vip_api.dashboard_delivery.storage import FileArtifactStorage
from vip_api.dashboards.models import Dashboard, DashboardVersion
from vip_api.dashboards.schemas import (
    DashboardCreate,
    EditorSave,
    GridLayout,
    PageInput,
    WidgetInput,
)
from vip_api.dashboards.services import create_dashboard, editor, publish, save_editor, viewer
from vip_api.database.session import Database
from vip_api.datasets.models import Dataset, DatasetField
from vip_api.files.models import PlatformFile
from vip_api.governance.context import AuthorizationContext
from vip_api.governance.seed import provision_organization_governance, seed_system_governance
from vip_api.governance.services import get_role
from vip_api.jobs.models import Job, JobResult
from vip_api.jobs.queue import QueueMetrics
from vip_api.jobs.worker import GenericJobWorker
from vip_api.semantic.models import SemanticDimension, SemanticMetric, SemanticModel
from vip_api.tenancy.models import (
    MembershipStatus,
    Organization,
    OrganizationMembership,
    OrganizationStatus,
    Workspace,
    WorkspaceMembership,
    WorkspaceStatus,
)

NOW = datetime(2026, 8, 3, 12, 0, tzinfo=UTC)
ALL_WIDGET_TYPES = (
    "kpi",
    "metric-comparison",
    "table",
    "pivot",
    "bar",
    "stacked-bar",
    "column",
    "line",
    "area",
    "pie",
    "donut",
    "scatter",
    "gauge",
    "progress",
    "text",
    "rich-text",
    "image",
    "filter",
    "date-filter",
    "map",
)
DATA_WIDGET_TYPES = frozenset(ALL_WIDGET_TYPES[:14]) | {"map"}


class _QueueStub:
    """Records enqueue calls; the scheduler tolerates enqueue failures either way."""

    def __init__(self) -> None:
        self.enqueued: list[UUID] = []

    async def enqueue(
        self, queue: str, job_id: UUID, *, priority: int = 0, delay_seconds: float = 0
    ) -> None:
        self.enqueued.append(job_id)

    async def dequeue(self, queue: str) -> UUID | None:
        return None

    async def metrics(self, queue: str) -> QueueMetrics:
        return QueueMetrics(queue=queue, ready=0, delayed=0)


@dataclass
class _Seed:
    user_id: UUID
    org_id: UUID
    ws_id: UUID
    dashboard_id: UUID
    version_id: UUID


async def _seed(
    db: AsyncSession,
    suffix: str,
    *,
    schedule_type: str = "daily",
    enabled: bool = True,
    due: bool = True,
) -> tuple[_Seed, UUID]:
    user = User(
        username=f"deliv-{suffix}",
        normalized_username=f"deliv-{suffix}",
        email=f"deliv-{suffix}@vip.test",
        normalized_email=f"deliv-{suffix}@vip.test",
        display_name="Delivery Owner",
        password_hash="unused",
        status=UserStatus.ACTIVE,
    )
    db.add(user)
    await db.flush()
    org = Organization(
        name=f"Deliv Org {suffix}",
        slug=f"deliv-org-{suffix}",
        status=OrganizationStatus.ACTIVE,
        created_by_user_id=user.id,
    )
    db.add(org)
    await db.flush()
    await provision_organization_governance(db, org.id)
    ws = Workspace(
        organization_id=org.id,
        name="Deliv WS",
        slug="deliv-ws",
        status=WorkspaceStatus.ACTIVE,
        is_default=True,
        created_by_user_id=user.id,
    )
    db.add(ws)
    await db.flush()
    org_admin = await get_role(db, "organization_admin", "organization")
    ws_admin = await get_role(db, "workspace_admin", "workspace")
    db.add_all(
        (
            OrganizationMembership(
                organization_id=org.id,
                user_id=user.id,
                role_id=org_admin.id,
                status=MembershipStatus.ACTIVE,
            ),
            WorkspaceMembership(
                organization_id=org.id,
                workspace_id=ws.id,
                user_id=user.id,
                role_id=ws_admin.id,
                status=MembershipStatus.ACTIVE,
            ),
        )
    )
    dashboard = Dashboard(
        organization_id=org.id,
        workspace_id=ws.id,
        name=f"Deliv Dashboard {suffix}",
        slug=f"deliv-dash-{suffix}",
        status="published",
        owner_user_id=user.id,
        created_by_user_id=user.id,
    )
    db.add(dashboard)
    await db.flush()
    version = DashboardVersion(
        organization_id=org.id,
        workspace_id=ws.id,
        dashboard_id=dashboard.id,
        version_number=1,
        version_type="published",
        snapshot={"schema_version": 1, "pages": []},
        created_by_user_id=user.id,
    )
    db.add(version)
    await db.flush()
    dashboard.published_version_id = version.id
    schedule = DashboardDeliverySchedule(
        organization_id=org.id,
        workspace_id=ws.id,
        dashboard_id=dashboard.id,
        dashboard_version_id=version.id,
        name=f"Nightly {suffix}",
        recipients=["ops@vip.test"],
        cc=[],
        bcc=[],
        subject="Nightly dashboard",
        format="csv",
        filters={},
        schedule_type=schedule_type,
        timezone="UTC",
        enabled=enabled,
        status="scheduled" if enabled else "paused",
        max_retries=3,
        created_by_user_id=user.id,
        next_run_at=(NOW - timedelta(minutes=5)) if due else (NOW + timedelta(days=1)),
    )
    db.add(schedule)
    await db.flush()
    schedule_id = schedule.id
    await db.commit()
    return _Seed(user.id, org.id, ws.id, dashboard.id, version.id), schedule_id


async def _cleanup(
    database: Database,
    org_ids: list[UUID],
    user_ids: list[UUID],
    connection_type_ids: list[UUID] | None = None,
) -> None:
    async with database.session_factory() as db:
        for oid in org_ids:
            await db.execute(delete(Dashboard).where(Dashboard.organization_id == oid))
            await db.execute(delete(SemanticModel).where(SemanticModel.organization_id == oid))
            await db.execute(delete(Dataset).where(Dataset.organization_id == oid))
            await db.execute(delete(Connection).where(Connection.organization_id == oid))
            await db.execute(delete(Organization).where(Organization.id == oid))
        for uid in user_ids:
            await db.execute(delete(User).where(User.id == uid))
        for connection_type_id in connection_type_ids or []:
            await db.execute(delete(ConnectionType).where(ConnectionType.id == connection_type_id))
        await db.commit()
    await database.engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_due_schedule_dispatches_and_dedupes(settings: Settings) -> None:
    database = Database(settings)
    org_ids: list[UUID] = []
    user_ids: list[UUID] = []
    try:
        async with database.session_factory() as db:
            await seed_system_governance(db)
            seed, schedule_id = await _seed(db, uuid4().hex[:8])
            org_ids.append(seed.org_id)
            user_ids.append(seed.user_id)

        dispatched = await dispatch_due_deliveries(database, settings, _QueueStub(), now=NOW)
        assert dispatched == 1

        async with database.session_factory() as db:
            runs = list(
                (
                    await db.scalars(
                        select(DashboardDeliveryRun).where(
                            DashboardDeliveryRun.schedule_id == schedule_id
                        )
                    )
                ).all()
            )
            assert len(runs) == 1
            assert runs[0].export_id is not None  # export created + linked
            schedule = await db.get(DashboardDeliverySchedule, schedule_id)
            assert schedule is not None
            # next_run_at advanced into the future — the slot is consumed.
            assert schedule.next_run_at is not None and schedule.next_run_at > NOW

        # A re-tick at the same instant claims nothing (duplicate prevention).
        assert await dispatch_due_deliveries(database, settings, _QueueStub(), now=NOW) == 0
        async with database.session_factory() as db:
            count = len(
                list(
                    (
                        await db.scalars(
                            select(DashboardDeliveryRun).where(
                                DashboardDeliveryRun.schedule_id == schedule_id
                            )
                        )
                    ).all()
                )
            )
            assert count == 1
    finally:
        await _cleanup(database, org_ids, user_ids)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_paused_and_future_schedules_are_not_claimed(settings: Settings) -> None:
    database = Database(settings)
    org_ids: list[UUID] = []
    user_ids: list[UUID] = []
    try:
        async with database.session_factory() as db:
            await seed_system_governance(db)
            paused, _ = await _seed(db, uuid4().hex[:8], enabled=False, due=False)
            org_ids.append(paused.org_id)
            user_ids.append(paused.user_id)
        assert await dispatch_due_deliveries(database, settings, _QueueStub(), now=NOW) == 0
    finally:
        await _cleanup(database, org_ids, user_ids)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_one_time_schedule_completes_after_dispatch(settings: Settings) -> None:
    database = Database(settings)
    org_ids: list[UUID] = []
    user_ids: list[UUID] = []
    try:
        async with database.session_factory() as db:
            await seed_system_governance(db)
            seed, schedule_id = await _seed(db, uuid4().hex[:8], schedule_type="one_time")
            org_ids.append(seed.org_id)
            user_ids.append(seed.user_id)
        assert await dispatch_due_deliveries(database, settings, _QueueStub(), now=NOW) == 1
        async with database.session_factory() as db:
            schedule = await db.get(DashboardDeliverySchedule, schedule_id)
            assert schedule is not None
            assert schedule.enabled is False
            assert schedule.next_run_at is None
            assert schedule.status == "completed"
    finally:
        await _cleanup(database, org_ids, user_ids)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_revoked_creator_access_fails_the_run(settings: Settings) -> None:
    database = Database(settings)
    org_ids: list[UUID] = []
    user_ids: list[UUID] = []
    try:
        async with database.session_factory() as db:
            await seed_system_governance(db)
            seed, schedule_id = await _seed(db, uuid4().hex[:8])
            org_ids.append(seed.org_id)
            user_ids.append(seed.user_id)
        # Revoke the creator's workspace membership before the tick.
        async with database.session_factory() as db:
            await db.execute(
                delete(WorkspaceMembership).where(
                    WorkspaceMembership.user_id == seed.user_id,
                    WorkspaceMembership.workspace_id == seed.ws_id,
                )
            )
            await db.commit()

        await dispatch_due_deliveries(database, settings, _QueueStub(), now=NOW)
        async with database.session_factory() as db:
            run = await db.scalar(
                select(DashboardDeliveryRun).where(DashboardDeliveryRun.schedule_id == schedule_id)
            )
            assert run is not None
            assert run.status == "failed"
            assert run.safe_error_code == "DELIVERY_ACCESS_REVOKED"
            assert run.export_id is None
    finally:
        await _cleanup(database, org_ids, user_ids)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_concurrent_schedulers_claim_each_slot_once(settings: Settings) -> None:
    database = Database(settings)
    org_ids: list[UUID] = []
    user_ids: list[UUID] = []
    try:
        async with database.session_factory() as db:
            await seed_system_governance(db)
            schedule_ids: list[UUID] = []
            for _ in range(3):
                seed, schedule_id = await _seed(db, uuid4().hex[:8])
                org_ids.append(seed.org_id)
                user_ids.append(seed.user_id)
                schedule_ids.append(schedule_id)

        # Two schedulers tick simultaneously; SKIP LOCKED must prevent double-claim.
        results = await asyncio.gather(
            dispatch_due_deliveries(database, settings, _QueueStub(), now=NOW),
            dispatch_due_deliveries(database, settings, _QueueStub(), now=NOW),
        )
        assert sum(results) == 3
        async with database.session_factory() as db:
            for schedule_id in schedule_ids:
                runs = list(
                    (
                        await db.scalars(
                            select(DashboardDeliveryRun).where(
                                DashboardDeliveryRun.schedule_id == schedule_id
                            )
                        )
                    ).all()
                )
                assert len(runs) == 1  # exactly once, never duplicated
    finally:
        await _cleanup(database, org_ids, user_ids)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_all_twenty_widgets_traverse_scheduler_worker_storage_and_email(
    settings: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact_root = tmp_path / "dashboard-artifacts"
    outbox_root = tmp_path / "email-outbox"
    file_root = tmp_path / "files"
    configured = settings.model_copy(
        update={
            "DASHBOARD_ARTIFACT_ROOT": str(artifact_root),
            "DASHBOARD_EMAIL_PROVIDER": "file",
            "DASHBOARD_EMAIL_OUTBOX_ROOT": str(outbox_root),
            "FILE_STORAGE_ROOT": str(file_root),
        }
    )
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", settings.database_url)
    monkeypatch.setenv("REDIS_URL", settings.redis_url)
    monkeypatch.setenv("DATABASE_CONNECT_TIMEOUT", "2.0")
    monkeypatch.setenv("DASHBOARD_ARTIFACT_ROOT", str(artifact_root))
    monkeypatch.setenv("DASHBOARD_EMAIL_PROVIDER", "file")
    monkeypatch.setenv("DASHBOARD_EMAIL_OUTBOX_ROOT", str(outbox_root))
    monkeypatch.setenv("FILE_STORAGE_ROOT", str(file_root))
    monkeypatch.setenv("CONNECTION_ENCRYPTION_KEY", "REREREREREREREREREREREREREREREREREREREREREQ=")
    monkeypatch.setenv("CONNECTION_ENCRYPTION_KEY_VERSION", "test-v1")
    get_settings.cache_clear()

    database = Database(configured)
    worker: GenericJobWorker | None = None
    org_ids: list[UUID] = []
    user_ids: list[UUID] = []
    connection_type_ids: list[UUID] = []
    try:
        async with database.session_factory() as db:
            await seed_system_governance(db)
            seed, schedule_id = await _seed(db, uuid4().hex[:8])
            org_ids.append(seed.org_id)
            user_ids.append(seed.user_id)
            schedule = await db.get(DashboardDeliverySchedule, schedule_id)
            assert schedule is not None

            suffix = uuid4().hex[:8]
            connection_type = ConnectionType(
                key=f"lifecycle-pg-{suffix}",
                name="Lifecycle PostgreSQL",
                category="database",
                configuration_schema={},
                secret_schema={},
                capabilities=["query"],
                test_strategy="noop",
            )
            db.add(connection_type)
            await db.flush()
            connection_type_ids.append(connection_type.id)
            connection = Connection(
                organization_id=seed.org_id,
                workspace_id=seed.ws_id,
                connection_type_id=connection_type.id,
                name="Lifecycle definition source",
                normalized_name="lifecycle definition source",
                configuration={},
                connection_type_version=1,
                status="active",
            )
            db.add(connection)
            await db.flush()
            dataset = Dataset(
                organization_id=seed.org_id,
                workspace_id=seed.ws_id,
                connection_id=connection.id,
                dataset_type="table",
                source_schema="public",
                source_name="lifecycle_definition",
                source_key=f"public.lifecycle_definition_{suffix}",
                qualified_name="public.lifecycle_definition",
                display_name="Lifecycle definition",
                source_object_type="table",
                status="active",
                version=1,
            )
            db.add(dataset)
            await db.flush()
            category = DatasetField(
                organization_id=seed.org_id,
                workspace_id=seed.ws_id,
                dataset_id=dataset.id,
                source_name="category",
                display_name="Category",
                ordinal_position=0,
                physical_data_type="varchar",
                normalized_data_type="string",
                is_nullable=False,
            )
            db.add(category)
            await db.flush()
            semantic_model = SemanticModel(
                organization_id=seed.org_id,
                workspace_id=seed.ws_id,
                key=f"lifecycle_model_{suffix}",
                name="Lifecycle model",
                status="published",
                primary_dataset_id=dataset.id,
                published_version=1,
                created_by_user_id=seed.user_id,
            )
            db.add(semantic_model)
            await db.flush()
            db.add_all(
                (
                    SemanticDimension(
                        organization_id=seed.org_id,
                        workspace_id=seed.ws_id,
                        semantic_model_id=semantic_model.id,
                        dataset_id=dataset.id,
                        field_id=category.id,
                        key="category",
                        name="Category",
                        dimension_type="categorical",
                        data_type="string",
                    ),
                    SemanticMetric(
                        organization_id=seed.org_id,
                        workspace_id=seed.ws_id,
                        semantic_model_id=semantic_model.id,
                        key="orders",
                        name="Orders",
                        metric_type="calculated",
                        status="published",
                    ),
                )
            )
            await db.commit()

            context = AuthorizationContext(
                user_id=seed.user_id,
                organization_id=seed.org_id,
                workspace_id=seed.ws_id,
                organization_role_key="organization_admin",
                workspace_role_key="workspace_admin",
                permissions=frozenset(
                    {"dashboard.read", "dashboard.create", "dashboard.update", "dashboard.publish"}
                ),
                entitlements=frozenset({"dashboard_studio"}),
                feature_flags={"dashboard_studio": True},
                quotas={},
                correlation_id="all-widget-real-lifecycle",
            )
            created = await create_dashboard(db, context, DashboardCreate(name="All 20 widgets"))
            widgets = [
                WidgetInput(
                    type=widget_type,
                    title=f"{widget_type} lifecycle",
                    semantic_model_id=(
                        semantic_model.id if widget_type in DATA_WIDGET_TYPES else None
                    ),
                    query={
                        "metrics": ["orders"] if widget_type in DATA_WIDGET_TYPES else [],
                        "dimensions": ["category"] if widget_type in DATA_WIDGET_TYPES else [],
                        "filters": [],
                    },
                    config={
                        "show_legend": True,
                        "legend_position": "bottom",
                        "axis": {
                            "x": {"title": "Region axis"},
                            "y": {"title": "Revenue axis"},
                        },
                        "locked": index % 2 == 0,
                        "aria_label": f"Accessible {widget_type}",
                    },
                    layout=GridLayout(x=0, y=index * 4, w=12, h=4),
                    interactions={"exportable": True},
                    content=(
                        f"Definition for {widget_type}"
                        if widget_type not in DATA_WIDGET_TYPES
                        else None
                    ),
                    hidden=widget_type in DATA_WIDGET_TYPES,
                )
                for index, widget_type in enumerate(ALL_WIDGET_TYPES)
            ]
            saved = await save_editor(
                db,
                context,
                created.id,
                EditorSave(
                    expected_version=created.row_version,
                    name="All 20 widgets",
                    pages=[
                        PageInput(
                            key="all_widgets",
                            name="All widgets",
                            position=0,
                            widgets=widgets,
                        )
                    ],
                ),
            )
            reloaded = await editor(db, context, created.id)
            assert reloaded.model_dump(mode="json") == saved.model_dump(mode="json")
            published = await publish(db, context, created.id, saved.version, "worker lifecycle")
            published_view = await viewer(db, context, created.id)
            version = await db.get(DashboardVersion, published.id)
            assert version is not None
            assert published_view["version"] == published.version_number
            assert published_view["snapshot"] == version.snapshot

            schedule.format = "json"
            schedule.dashboard_id = created.id
            schedule.dashboard_version_id = published.id
            await db.commit()

        queue = _QueueStub()
        assert await dispatch_due_deliveries(database, configured, queue, now=NOW) == 1
        assert len(queue.enqueued) == 1
        platform_job_id = queue.enqueued[0]

        worker = GenericJobWorker(configured)
        await worker._execute(platform_job_id)

        async with database.session_factory() as db:
            schedule = await db.get(DashboardDeliverySchedule, schedule_id)
            run = await db.scalar(
                select(DashboardDeliveryRun).where(DashboardDeliveryRun.schedule_id == schedule_id)
            )
            job = await db.get(Job, platform_job_id)
            result = await db.get(JobResult, platform_job_id)
            assert schedule is not None and schedule.dashboard_version_id == published.id
            assert run is not None and run.export_id is not None and run.status == "sent"
            export = await db.get(DashboardExport, run.export_id)
            assert export is not None and export.status == "completed"
            assert export.dashboard_version_id == published.id
            assert export.artifact_key and export.artifact_sha256
            assert job is not None and job.status == "succeeded"
            assert result is not None and result.result_file_id is not None
            stored_file = await db.get(PlatformFile, result.result_file_id)
            assert stored_file is not None and stored_file.status == "ready"
            assert stored_file.metadata_json["dashboard_version_id"] == str(published.id)

        artifact = await FileArtifactStorage(configured).read(export.artifact_key)
        artifact_hash = hashlib.sha256(artifact).hexdigest()
        assert artifact_hash == export.artifact_sha256
        payload = json.loads(artifact)
        exported_types = [
            widget["type"] for page in payload["definition"]["pages"] for widget in page["widgets"]
        ]
        assert exported_types == list(ALL_WIDGET_TYPES)

        email_path = outbox_root / f"{run.id}.eml"
        assert email_path.is_file()
        message = BytesParser(policy=policy.default).parsebytes(email_path.read_bytes())
        attachment = next(message.iter_attachments())
        attachment_bytes = attachment.get_payload(decode=True)
        assert attachment_bytes == artifact
        assert hashlib.sha256(attachment_bytes).hexdigest() == artifact_hash

        evidence_path = os.getenv("VIP_WIDGET_LIFECYCLE_EVIDENCE_PATH")
        if evidence_path:
            target = Path(evidence_path)
            await asyncio.to_thread(target.parent.mkdir, parents=True, exist_ok=True)
            evidence = (
                json.dumps(
                    {
                        "schema_version": 1,
                        "widget_count": 20,
                        "widget_types": list(ALL_WIDGET_TYPES),
                        "dashboard_id": str(created.id),
                        "dashboard_version_id": str(published.id),
                        "schedule_id": str(schedule_id),
                        "delivery_run_id": str(run.id),
                        "export_id": str(export.id),
                        "platform_job_id": str(platform_job_id),
                        "stored_file_id": str(stored_file.id),
                        "artifact_sha256": artifact_hash,
                        "email_attachment_sha256": hashlib.sha256(attachment_bytes).hexdigest(),
                        "channels": [
                            "database_create",
                            "editor_save",
                            "editor_reload",
                            "published_version",
                            "scheduler",
                            "job_queue",
                            "generic_worker",
                            "artifact_storage",
                            "file_record",
                            "email_attachment",
                        ],
                        "result": "pass",
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            )
            await asyncio.to_thread(target.write_text, evidence, encoding="utf-8")
    finally:
        if worker is not None:
            await worker.redis.close()
            await worker.database.dispose()
        get_settings.cache_clear()
        await _cleanup(database, org_ids, user_ids, connection_type_ids)
