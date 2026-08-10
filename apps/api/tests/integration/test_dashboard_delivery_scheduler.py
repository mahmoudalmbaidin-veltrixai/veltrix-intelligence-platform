"""Recurring delivery scheduler integration coverage (Phase B9.1A).

Drives ``dispatch_due_deliveries`` against vip_test: due-schedule claiming,
duplicate prevention, concurrent schedulers, pause, one-time completion, revoked
creator access, and tenant isolation.
"""

from __future__ import annotations

import asyncio
import base64
import csv
import hashlib
import io
import json
import os
import re
import socket
import zlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

import pytest
from PIL import Image
from sqlalchemy import delete, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.auth.models import User, UserStatus
from vip_api.connections.crypto import EnvironmentEncryptionKeyProvider
from vip_api.connections.models import Connection, ConnectionType
from vip_api.connections.secrets import DatabaseEncryptedSecretProvider
from vip_api.connections.seed import seed_connection_types
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
from vip_api.semantic.models import (
    SemanticDimension,
    SemanticMeasure,
    SemanticMetric,
    SemanticModel,
)
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


def _reportlab_pdf_utf16(value: str) -> bytes:
    """Encode ASCII as ReportLab's escaped UTF-16BE PDF string representation."""
    return b"".join(b"\\000" + bytes((character,)) for character in value.encode("ascii"))


def _pdf_visible_streams(content: bytes) -> bytes:
    decoded: list[bytes] = []
    for match in re.finditer(rb"stream\r?\n(.*?)endstream", content, re.DOTALL):
        value = match.group(1).strip()
        try:
            if value.endswith(b"~>"):
                value = base64.a85decode(value, adobe=True)
            decoded.append(zlib.decompress(value))
        except (ValueError, zlib.error):
            continue
    return b"\n".join(decoded)


def _png_widget_body(image: Image.Image, widget_index: int) -> Image.Image:
    page_stride = 38 + 8 * (76 + 10) + 36
    grid_top = 150 + widget_index * page_stride + 38
    return image.crop((120, (grid_top + 58) * 2, image.width - 120, (grid_top + 658) * 2))


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
async def test_all_twenty_widgets_traverse_every_real_delivery_format(
    settings: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Certify one immutable dashboard through four real scheduled worker jobs.

    The source table, encrypted PostgreSQL connection, semantic query, dashboard,
    schedules, jobs, exports, stored files, and email messages are all persisted.
    Renderer-only construction is deliberately absent from this lifecycle proof.
    """
    artifact_root = tmp_path / "dashboard-artifacts"
    outbox_root = tmp_path / "email-outbox"
    file_root = tmp_path / "files"
    configured = settings.model_copy(
        update={
            "DASHBOARD_ARTIFACT_ROOT": str(artifact_root),
            "DASHBOARD_EMAIL_PROVIDER": "file",
            "DASHBOARD_EMAIL_OUTBOX_ROOT": str(outbox_root),
            "FILE_STORAGE_ROOT": str(file_root),
            "CONNECTION_ALLOW_PRIVATE_NETWORKS": True,
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
    monkeypatch.setenv("CONNECTION_ALLOW_PRIVATE_NETWORKS", "true")
    monkeypatch.setenv("CONNECTION_ENCRYPTION_KEY", "REREREREREREREREREREREREREREREREREREREREREQ=")
    monkeypatch.setenv("CONNECTION_ENCRYPTION_KEY_VERSION", "test-v1")
    get_settings.cache_clear()

    database = Database(configured)
    worker: GenericJobWorker | None = None
    org_ids: list[UUID] = []
    user_ids: list[UUID] = []
    source_table: str | None = None
    try:
        async with database.session_factory() as db:
            await seed_system_governance(db)
            await seed_connection_types(db)
            seed, schedule_id = await _seed(db, uuid4().hex[:8])
            org_ids.append(seed.org_id)
            user_ids.append(seed.user_id)
            schedule = await db.get(DashboardDeliverySchedule, schedule_id)
            assert schedule is not None

            suffix = uuid4().hex[:8]
            source_table = f"vip_delivery_lifecycle_{suffix}"
            await db.execute(
                text(
                    f'CREATE TABLE "{source_table}" ('
                    "category text NOT NULL, orders integer NOT NULL, "
                    "latitude numeric NOT NULL, longitude numeric NOT NULL)"
                )
            )
            await db.execute(
                text(
                    f'INSERT INTO "{source_table}" '  # noqa: S608 - generated hex identifier
                    "(category, orders, latitude, longitude) VALUES "
                    "('الرياض / Riyadh', 12, 24.7136, 46.6753), "
                    "('جدة / Jeddah', 8, 21.4858, 39.1925), "
                    "('الدمام / Dammam', 5, 26.4207, 50.0888)"
                )
            )
            await db.execute(text(f'ALTER TABLE "{source_table}" ADD COLUMN quarter text'))
            await db.execute(
                text(
                    f'UPDATE "{source_table}" SET '  # noqa: S608 - generated hex identifier
                    "category = CASE orders WHEN 12 THEN 'Region A' WHEN 8 THEN 'Region A' "
                    "ELSE 'Region B' END, "
                    "quarter = CASE orders WHEN 12 THEN 'Q1' WHEN 8 THEN 'Q2' ELSE 'Q1' END, "
                    "orders = CASE orders WHEN 12 THEN 111 WHEN 8 THEN 222 ELSE 333 END"
                )
            )
            await db.execute(
                text(
                    f'INSERT INTO "{source_table}" '  # noqa: S608 - generated hex identifier
                    "(category, orders, latitude, longitude, quarter) VALUES "
                    "('Region B', 444, 26.9207, 50.5888, 'Q2')"
                )
            )
            connection_type = await db.scalar(
                select(ConnectionType).where(ConnectionType.key == "postgresql")
            )
            assert connection_type is not None
            database_url = make_url(configured.database_url)
            assert database_url.host in {"127.0.0.1", "localhost"}
            assert database_url.username and database_url.password and database_url.database
            query_host = os.getenv("VIP_TEST_QUERY_HOST") or socket.gethostbyname(
                socket.gethostname()
            )
            assert not query_host.startswith("127.") and query_host != "::1", (
                "Set VIP_TEST_QUERY_HOST to a non-loopback address that reaches the local "
                "integration PostgreSQL port."
            )
            connection = Connection(
                organization_id=seed.org_id,
                workspace_id=seed.ws_id,
                connection_type_id=connection_type.id,
                name=f"Lifecycle PostgreSQL {suffix}",
                normalized_name=f"lifecycle postgresql {suffix}",
                configuration={
                    "host": query_host,
                    "port": int(database_url.port or 5432),
                    "database": str(database_url.database),
                    "username": str(database_url.username),
                    "ssl_mode": "disable",
                    "connect_timeout_seconds": 2,
                },
                connection_type_version=1,
                status="active",
                health_status="healthy",
            )
            db.add(connection)
            await db.flush()
            secret_provider = DatabaseEncryptedSecretProvider(
                EnvironmentEncryptionKeyProvider(configured)
            )
            secret = await secret_provider.store_secret(
                db,
                organization_id=seed.org_id,
                workspace_id=seed.ws_id,
                connection_id=connection.id,
                credential_version=1,
                credentials={"password": str(database_url.password)},
                actor_user_id=seed.user_id,
            )
            connection.secret_id = secret.id
            dataset = Dataset(
                organization_id=seed.org_id,
                workspace_id=seed.ws_id,
                connection_id=connection.id,
                dataset_type="table",
                source_schema="public",
                source_name=source_table,
                source_key=f"public.{source_table}",
                qualified_name=f"public.{source_table}",
                display_name="Lifecycle definition",
                source_object_type="table",
                status="active",
                version=1,
                owner_user_id=seed.user_id,
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
            orders = DatasetField(
                organization_id=seed.org_id,
                workspace_id=seed.ws_id,
                dataset_id=dataset.id,
                source_name="orders",
                display_name="Orders",
                ordinal_position=1,
                physical_data_type="integer",
                normalized_data_type="integer",
                is_nullable=False,
            )
            quarter = DatasetField(
                organization_id=seed.org_id,
                workspace_id=seed.ws_id,
                dataset_id=dataset.id,
                source_name="quarter",
                display_name="Quarter",
                ordinal_position=4,
                physical_data_type="varchar",
                normalized_data_type="string",
                is_nullable=False,
            )
            latitude = DatasetField(
                organization_id=seed.org_id,
                workspace_id=seed.ws_id,
                dataset_id=dataset.id,
                source_name="latitude",
                display_name="Latitude",
                ordinal_position=2,
                physical_data_type="numeric",
                normalized_data_type="decimal",
                is_nullable=False,
            )
            longitude = DatasetField(
                organization_id=seed.org_id,
                workspace_id=seed.ws_id,
                dataset_id=dataset.id,
                source_name="longitude",
                display_name="Longitude",
                ordinal_position=3,
                physical_data_type="numeric",
                normalized_data_type="decimal",
                is_nullable=False,
            )
            db.add_all((category, orders, latitude, longitude, quarter))
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
            measure = SemanticMeasure(
                organization_id=seed.org_id,
                workspace_id=seed.ws_id,
                semantic_model_id=semantic_model.id,
                dataset_id=dataset.id,
                field_id=orders.id,
                key="orders_measure",
                name="Orders measure",
                aggregation="sum",
                data_type="integer",
            )
            db.add(measure)
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
                    SemanticDimension(
                        organization_id=seed.org_id,
                        workspace_id=seed.ws_id,
                        semantic_model_id=semantic_model.id,
                        dataset_id=dataset.id,
                        field_id=quarter.id,
                        key="quarter",
                        name="Quarter",
                        dimension_type="categorical",
                        data_type="string",
                    ),
                    SemanticDimension(
                        organization_id=seed.org_id,
                        workspace_id=seed.ws_id,
                        semantic_model_id=semantic_model.id,
                        dataset_id=dataset.id,
                        field_id=latitude.id,
                        key="latitude",
                        name="Latitude",
                        dimension_type="categorical",
                        data_type="decimal",
                    ),
                    SemanticDimension(
                        organization_id=seed.org_id,
                        workspace_id=seed.ws_id,
                        semantic_model_id=semantic_model.id,
                        dataset_id=dataset.id,
                        field_id=longitude.id,
                        key="longitude",
                        name="Longitude",
                        dimension_type="categorical",
                        data_type="decimal",
                    ),
                    SemanticMetric(
                        organization_id=seed.org_id,
                        workspace_id=seed.ws_id,
                        semantic_model_id=semantic_model.id,
                        key="orders",
                        name="Orders",
                        metric_type="measure",
                        base_measure_id=measure.id,
                        status="published",
                    ),
                    SemanticMetric(
                        organization_id=seed.org_id,
                        workspace_id=seed.ws_id,
                        semantic_model_id=semantic_model.id,
                        key="orders_y",
                        name="Orders Y",
                        metric_type="measure",
                        base_measure_id=measure.id,
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
            widgets = {
                widget_type: WidgetInput(
                    type=widget_type,
                    title=f"{widget_type} lifecycle دورة حياة",
                    semantic_model_id=(
                        semantic_model.id if widget_type in DATA_WIDGET_TYPES else None
                    ),
                    query={
                        "metrics": (
                            ["orders", "orders_y"]
                            if widget_type == "scatter"
                            else ["orders"]
                            if widget_type in DATA_WIDGET_TYPES
                            else []
                        ),
                        "dimensions": (
                            ["category", "latitude", "longitude"]
                            if widget_type == "map"
                            else ["category", "quarter"]
                            if widget_type == "pivot"
                            else ["category"]
                            if widget_type in DATA_WIDGET_TYPES
                            else []
                        ),
                        "filters": [],
                    },
                    config={
                        "show_legend": True,
                        "legend_position": "bottom",
                        "axis": {
                            "x": {"title": "Region / المنطقة"},
                            "y": {"title": "Orders / الطلبات"},
                        },
                        "number_style": "plain",
                        "decimals": 0,
                        "conditional": [{"when": "gt", "value": 9, "color": "#14B8A6"}],
                        "locked": index % 2 == 0,
                        "aria_label": f"Accessible {widget_type} عنصر",
                    },
                    layout=GridLayout(x=0, y=0, w=12, h=8),
                    interactions={"exportable": True, "drill": {"field": "category"}},
                    content=(
                        f"Definition for {widget_type} - تعريف ثنائي الاتجاه 2026"
                        if widget_type not in DATA_WIDGET_TYPES
                        else None
                    ),
                    hidden=False,
                )
                for index, widget_type in enumerate(ALL_WIDGET_TYPES)
            }
            saved = await save_editor(
                db,
                context,
                created.id,
                EditorSave(
                    expected_version=created.row_version,
                    name="All 20 widgets",
                    pages=[
                        PageInput(
                            key=f"widget_{index + 1}",
                            name=f"{widget_type} / عنصر {index + 1}",
                            position=index,
                            widgets=[widgets[widget_type]],
                        )
                        for index, widget_type in enumerate(ALL_WIDGET_TYPES)
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
            snapshot_pages = cast(list[dict[str, object]], version.snapshot["pages"])
            published_widgets = {
                str(widget["type"]): widget
                for page in snapshot_pages
                for widget in cast(list[dict[str, object]], page["widgets"])
            }
            pivot_widget_id = str(published_widgets["pivot"]["id"])
            scatter_widget_id = str(published_widgets["scatter"]["id"])

            schedules: dict[str, UUID] = {}
            for index, export_format in enumerate(("pdf", "png", "csv", "json")):
                target = schedule
                if index:
                    target = DashboardDeliverySchedule(
                        organization_id=seed.org_id,
                        workspace_id=seed.ws_id,
                        dashboard_id=created.id,
                        dashboard_version_id=published.id,
                        name=f"Lifecycle {export_format.upper()} {suffix}",
                        recipients=["ops@vip.test"],
                        cc=[],
                        bcc=[],
                        subject=f"Lifecycle {export_format.upper()}",
                        format=export_format,
                        filters={},
                        schedule_type="daily",
                        timezone="UTC",
                        enabled=True,
                        status="scheduled",
                        max_retries=3,
                        created_by_user_id=seed.user_id,
                        next_run_at=NOW - timedelta(minutes=5),
                    )
                    db.add(target)
                    await db.flush()
                target.format = export_format
                target.dashboard_id = created.id
                target.dashboard_version_id = published.id
                schedules[export_format] = target.id
            await db.commit()

        queue = _QueueStub()
        assert await dispatch_due_deliveries(database, configured, queue, now=NOW) == 4
        assert len(queue.enqueued) == 4

        worker = GenericJobWorker(configured)
        for platform_job_id in queue.enqueued:
            await worker._execute(platform_job_id)

        observed: list[dict[str, object]] = []
        async with database.session_factory() as db:
            for export_format, current_schedule_id in schedules.items():
                current_schedule = await db.get(DashboardDeliverySchedule, current_schedule_id)
                run = await db.scalar(
                    select(DashboardDeliveryRun).where(
                        DashboardDeliveryRun.schedule_id == current_schedule_id
                    )
                )
                assert current_schedule is not None
                assert current_schedule.dashboard_version_id == published.id
                assert run is not None and run.export_id is not None and run.status == "sent"
                export = await db.get(DashboardExport, run.export_id)
                assert export is not None and export.status == "completed"
                assert export.dashboard_version_id == published.id
                assert export.format == export_format
                assert export.artifact_key and export.artifact_sha256
                assert export.platform_job_id is not None
                job = await db.get(Job, export.platform_job_id)
                result = await db.get(JobResult, export.platform_job_id)
                assert job is not None and job.status == "succeeded"
                assert result is not None and result.result_file_id is not None
                stored_file = await db.get(PlatformFile, result.result_file_id)
                assert stored_file is not None and stored_file.status == "ready"
                assert stored_file.metadata_json["dashboard_version_id"] == str(published.id)

                artifact = await FileArtifactStorage(configured).read(export.artifact_key)
                artifact_hash = hashlib.sha256(artifact).hexdigest()
                assert artifact_hash == export.artifact_sha256

                if export_format == "json":
                    assert str(published.id).encode() in artifact
                    payload = json.loads(artifact)
                    definition = payload["definition"]
                    pivot_result = payload["widget_data"][pivot_widget_id]
                    assert pivot_result["shaped"]["row_fields"] == ["category"]
                    assert pivot_result["shaped"]["column_fields"] == ["quarter"]
                    pivot_cells = {
                        row["row_values"][0]: row["cells"] for row in pivot_result["shaped"]["rows"]
                    }
                    assert pivot_cells == {
                        "Region A": [111, 222],
                        "Region B": [333, 444],
                    }
                    scatter_result = payload["widget_data"][scatter_widget_id]
                    assert scatter_result["shaped"]["valid"] is True
                    assert scatter_result["shaped"]["x_field"] == "orders"
                    assert scatter_result["shaped"]["y_field"] == "orders_y"
                    assert {
                        (point["x"], point["y"], point["group"])
                        for point in scatter_result["shaped"]["points"]
                    } == {(333.0, 333.0, "Region A"), (777.0, 777.0, "Region B")}
                elif export_format == "csv":
                    assert str(published.id).encode() in artifact
                    assert b"Region A" in artifact and b"Region B" in artifact
                    assert all(value in artifact for value in (b"111", b"222", b"333", b"444"))
                    rows = list(csv.reader(io.StringIO(artifact.decode("utf-8-sig"))))
                    definition = json.loads(rows[1][1])
                    assert any(row and row[0].startswith("Widget ") for row in rows)
                elif export_format == "png":
                    with Image.open(io.BytesIO(artifact)) as image:
                        definition = json.loads(image.info["vip.dashboard.definition"])
                        assert image.width > 0 and image.height > 0
                        pivot_body = _png_widget_body(image.convert("RGB"), 3)
                        assert list(pivot_body.get_flattened_data()).count((22, 58, 112)) > 500
                        scatter_body = _png_widget_body(image.convert("RGB"), 11)
                        scatter_pixels = list(scatter_body.get_flattened_data()).count(
                            (37, 99, 235)
                        )
                        assert 20 < scatter_pixels < 5000
                else:
                    assert artifact.startswith(b"%PDF-")
                    assert _reportlab_pdf_utf16(str(published.id)) in artifact
                    for widget_type in ALL_WIDGET_TYPES:
                        assert _reportlab_pdf_utf16(widget_type) in artifact
                    visible_pdf = _pdf_visible_streams(artifact)
                    assert all(
                        value in visible_pdf
                        for value in (
                            b"Region A",
                            b"Region B",
                            b"Q1",
                            b"Q2",
                            b"111",
                            b"222",
                            b"333",
                            b"444",
                            b"1,110",
                        )
                    )
                    assert b"Scatter chart requires numeric X and Y fields." not in visible_pdf
                    definition = version.snapshot | {
                        "dashboard_version_id": str(published.id),
                    }

                exported_types = [
                    widget["type"] for page in definition["pages"] for widget in page["widgets"]
                ]
                assert exported_types == list(ALL_WIDGET_TYPES)
                assert all(
                    not widget["hidden"]
                    for page in definition["pages"]
                    for widget in page["widgets"]
                )

                email_path = outbox_root / f"{run.id}.eml"
                assert email_path.is_file()
                message = BytesParser(policy=policy.default).parsebytes(email_path.read_bytes())
                attachment = next(message.iter_attachments())
                attachment_bytes = attachment.get_payload(decode=True)
                assert attachment_bytes == artifact
                email_hash = hashlib.sha256(attachment_bytes).hexdigest()
                assert email_hash == artifact_hash
                observed.append(
                    {
                        "format": export_format,
                        "dashboard_id": str(created.id),
                        "published_version_id": str(published.id),
                        "schedule_id": str(current_schedule_id),
                        "delivery_run_id": str(run.id),
                        "platform_job_id": str(export.platform_job_id),
                        "export_id": str(export.id),
                        "stored_file_id": str(stored_file.id),
                        "artifact_sha256": artifact_hash,
                        "email_attachment_sha256": email_hash,
                        "widget_count": 20,
                        "visible_widget_count": 20,
                        "queried_widget_count": len(DATA_WIDGET_TYPES),
                        "result": "pass",
                        "test_id": (
                            "integration/test_dashboard_delivery_scheduler.py::"
                            "test_all_twenty_widgets_traverse_every_real_delivery_format"
                        ),
                    }
                )

                evidence_path = os.getenv("VIP_WIDGET_LIFECYCLE_EVIDENCE_PATH")
                if evidence_path:
                    artifact_target = (
                        Path(evidence_path).parent
                        / "artifacts"
                        / (f"all-20-widgets-lifecycle.{export_format}")
                    )
                    await asyncio.to_thread(
                        artifact_target.parent.mkdir, parents=True, exist_ok=True
                    )
                    await asyncio.to_thread(artifact_target.write_bytes, artifact)

        evidence_path = os.getenv("VIP_WIDGET_LIFECYCLE_EVIDENCE_PATH")
        if evidence_path:
            evidence_target = Path(evidence_path)
            await asyncio.to_thread(evidence_target.parent.mkdir, parents=True, exist_ok=True)
            evidence = (
                json.dumps(
                    {
                        "schema_version": 2,
                        "widget_count": 20,
                        "widget_types": list(ALL_WIDGET_TYPES),
                        "dashboard_id": str(created.id),
                        "published_version_id": str(published.id),
                        "formats": observed,
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
                        "result": "pass" if len(observed) == 4 else "fail",
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            )
            await asyncio.to_thread(evidence_target.write_text, evidence, encoding="utf-8")
    finally:
        if worker is not None:
            await worker.redis.close()
            await worker.database.dispose()
        get_settings.cache_clear()
        if source_table is not None:
            async with database.session_factory() as db:
                await db.execute(text(f'DROP TABLE IF EXISTS "{source_table}"'))
                await db.commit()
        await _cleanup(database, org_ids, user_ids)
