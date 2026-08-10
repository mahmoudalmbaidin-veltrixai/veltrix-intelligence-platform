"""Deterministic, transaction-rolled-back Phase 1 dataset scale measurement."""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import event, func, select

from vip_api.auth.models import User, UserStatus
from vip_api.connections.models import Connection, ConnectionType
from vip_api.core.config import Settings
from vip_api.database.session import Database
from vip_api.datasets.models import Dataset, DatasetQualityEvaluation
from vip_api.datasets.services import list_datasets
from vip_api.governance.context import AuthorizationContext
from vip_api.governance.models import Role
from vip_api.jobs import models as _job_models  # noqa: F401 - register FK metadata
from vip_api.tenancy.models import (
    Organization,
    OrganizationStatus,
    Workspace,
    WorkspaceStatus,
)


async def measure(output: Path) -> None:
    settings = Settings()
    database = Database(settings)
    prefix = f"qa-phase1-scale-{uuid4().hex[:10]}"
    results: list[dict[str, object]] = []
    try:
        async with database.session_factory() as db:
            user = User(
                username=prefix,
                normalized_username=prefix,
                email=f"{prefix}@vip.test",
                normalized_email=f"{prefix}@vip.test",
                display_name="Phase 1 Scale",
                password_hash="unused",
                status=UserStatus.ACTIVE,
            )
            db.add(user)
            await db.flush()
            organization = Organization(
                name="Phase 1 Scale",
                slug=prefix,
                status=OrganizationStatus.ACTIVE,
                created_by_user_id=user.id,
            )
            db.add(organization)
            await db.flush()
            connection_type = ConnectionType(
                key=prefix,
                name="Phase 1 Scale PostgreSQL",
                category="database",
                configuration_schema={},
                secret_schema={},
                capabilities=["discover"],
                test_strategy="noop",
            )
            db.add(connection_type)
            await db.flush()
            role_id = await db.scalar(select(Role.id).where(Role.key == "organization_member"))
            assert role_id is not None

            workspaces: list[tuple[int, Workspace]] = []
            for count in (10, 100, 250, 1000):
                workspace = Workspace(
                    organization_id=organization.id,
                    name=f"Scale {count}",
                    slug=f"scale-{count}",
                    status=WorkspaceStatus.ACTIVE,
                    is_default=count == 10,
                    created_by_user_id=user.id,
                )
                db.add(workspace)
                await db.flush()
                connection = Connection(
                    organization_id=organization.id,
                    workspace_id=workspace.id,
                    connection_type_id=connection_type.id,
                    name=f"Scale {count}",
                    normalized_name=f"scale-{count}",
                    configuration={},
                    connection_type_version=1,
                    status="active",
                )
                db.add(connection)
                await db.flush()
                datasets = [
                    Dataset(
                        organization_id=organization.id,
                        workspace_id=workspace.id,
                        connection_id=connection.id,
                        dataset_type="table",
                        source_schema="public",
                        source_name=f"dataset_{index:04d}",
                        source_key=f"{prefix}:{count}:{index:04d}",
                        qualified_name=f"public.dataset_{index:04d}",
                        display_name=f"{prefix}-{index:04d}",
                        source_object_type="table",
                        status="active",
                        owner_user_id=user.id,
                        version=1,
                    )
                    for index in range(count)
                ]
                db.add_all(datasets)
                await db.flush()
                now = datetime.now(UTC)
                db.add_all(
                    DatasetQualityEvaluation(
                        organization_id=organization.id,
                        workspace_id=workspace.id,
                        dataset_id=dataset.id,
                        status="completed",
                        score=90 + (index % 10),
                        total_rules=1,
                        passing=1,
                        completed_at=now,
                    )
                    for index, dataset in enumerate(datasets)
                )
                await db.flush()
                workspaces.append((count, workspace))

            for count, workspace in workspaces:
                context = AuthorizationContext(
                    user_id=user.id,
                    organization_id=organization.id,
                    workspace_id=workspace.id,
                    organization_role_key="organization_admin",
                    workspace_role_key="workspace_admin",
                    permissions=frozenset({"dataset.read"}),
                    entitlements=frozenset(),
                    feature_flags={},
                    quotas={},
                    correlation_id=prefix,
                )
                statements = 0

                def count_statement(*_args: object) -> None:
                    nonlocal statements
                    statements += 1

                event.listen(database.engine.sync_engine, "before_cursor_execute", count_statement)
                started = time.perf_counter()
                page = await list_datasets(
                    db, context, page=1, page_size=50, search=prefix, status="active"
                )
                elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
                event.remove(database.engine.sync_engine, "before_cursor_execute", count_statement)
                assert page.total == count
                assert all(item.quality_score is not None for item in page.items)
                results.append(
                    {
                        "dataset_count": count,
                        "returned_page_items": len(page.items),
                        "http_requests": 1,
                        "quality_http_requests": 0,
                        "database_statements": statements,
                        "backend_ms": elapsed_ms,
                    }
                )

            await db.rollback()

        async with database.session_factory() as verification_db:
            remaining = int(
                await verification_db.scalar(
                    select(func.count()).select_from(Dataset).where(Dataset.source_key.like(f"{prefix}%"))
                )
                or 0
            )
            assert remaining == 0
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(
                {
                    "measured_at": datetime.now(UTC).isoformat(),
                    "fixture_prefix": prefix,
                    "transaction_rolled_back": True,
                    "remaining_fixture_datasets": 0,
                    "measurements": results,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    finally:
        await database.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    asyncio.run(measure(args.output))
