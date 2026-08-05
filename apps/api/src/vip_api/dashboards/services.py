"""Transactional Dashboard aggregate, immutable versions, sharing, and snapshots."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.core.config import Settings
from vip_api.core.errors import ApplicationError
from vip_api.dashboards.models import (
    Dashboard,
    DashboardFilter,
    DashboardPage,
    DashboardShare,
    DashboardSnapshot,
    DashboardVersion,
    DashboardWidget,
)
from vip_api.dashboards.schemas import (
    DashboardCreate,
    DashboardDetail,
    DashboardFilterInput,
    DashboardSummary,
    EditorResponse,
    EditorSave,
    PageInput,
    ShareCreate,
    ShareResponse,
    SnapshotCreate,
    SnapshotResponse,
    VersionResponse,
    WidgetInput,
)
from vip_api.governance import resource_access_service
from vip_api.governance.audit import record_audit
from vip_api.governance.context import AuthorizationContext
from vip_api.governance.models import Role
from vip_api.semantic.models import SemanticDimension, SemanticMetric, SemanticModel
from vip_api.tenancy.models import MembershipStatus, OrganizationMembership, WorkspaceMembership


def _tenant(context: AuthorizationContext) -> tuple[UUID, UUID]:
    if context.workspace_id is None:
        raise ApplicationError(
            code="WORKSPACE_REQUIRED", message="Select a workspace to continue.", status_code=422
        )
    return context.organization_id, context.workspace_id


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")[:120]
    return normalized or f"dashboard-{uuid4().hex[:8]}"


def _not_found() -> ApplicationError:
    return ApplicationError(
        code="DASHBOARD_NOT_FOUND",
        message="The requested dashboard was not found.",
        status_code=404,
    )


async def get_dashboard(
    db: AsyncSession,
    context: AuthorizationContext,
    dashboard_id: UUID,
    *,
    include_archived: bool = False,
    lock: bool = False,
) -> Dashboard:
    org, ws = _tenant(context)
    statement = select(Dashboard).where(
        Dashboard.id == dashboard_id, Dashboard.organization_id == org, Dashboard.workspace_id == ws
    )
    if not include_archived:
        statement = statement.where(Dashboard.archived_at.is_(None))
    if lock:
        statement = statement.with_for_update()
    dashboard = await db.scalar(statement)
    if dashboard is None:
        raise _not_found()
    return dashboard


def _check_version(dashboard: Dashboard, expected: int) -> None:
    if dashboard.row_version != expected:
        raise ApplicationError(
            code="DASHBOARD_VERSION_CONFLICT",
            message="This dashboard was updated by another user. Reload before saving.",
            status_code=409,
        )


async def _counts(db: AsyncSession, dashboard_id: UUID) -> tuple[int, int]:
    pages = await db.scalar(
        select(func.count())
        .select_from(DashboardPage)
        .where(DashboardPage.dashboard_id == dashboard_id)
    )
    widgets = await db.scalar(
        select(func.count())
        .select_from(DashboardWidget)
        .where(DashboardWidget.dashboard_id == dashboard_id)
    )
    return int(pages or 0), int(widgets or 0)


async def _published_number(db: AsyncSession, dashboard: Dashboard) -> int | None:
    if dashboard.published_version_id is None:
        return None
    return cast(
        int | None,
        await db.scalar(
            select(DashboardVersion.version_number).where(
                DashboardVersion.id == dashboard.published_version_id
            )
        ),
    )


async def _access(
    db: AsyncSession, context: AuthorizationContext, dashboard: Dashboard
) -> dict[str, bool]:
    now = datetime.now(UTC)
    role_keys = {
        key
        for key in (context.organization_role_key, context.workspace_role_key)
        if key is not None
    }
    role_ids = list((await db.scalars(select(Role.id).where(Role.key.in_(role_keys)))).all())
    principal_match = [
        and_(
            DashboardShare.principal_type == "user",
            DashboardShare.principal_id == context.user_id,
        )
    ]
    if role_ids:
        principal_match.append(
            and_(
                DashboardShare.principal_type.in_(("workspace_role", "organization_role")),
                DashboardShare.principal_id.in_(role_ids),
            )
        )
    share = await db.scalar(
        select(DashboardShare).where(
            DashboardShare.dashboard_id == dashboard.id,
            DashboardShare.organization_id == context.organization_id,
            DashboardShare.workspace_id == context.workspace_id,
            or_(*principal_match),
            DashboardShare.revoked_at.is_(None),
            (DashboardShare.expires_at.is_(None) | (DashboardShare.expires_at > now)),
        )
    )
    level = share.permission_level if share else None
    can_view = "dashboard.read" in context.permissions or level in {
        "view",
        "interact",
        "edit",
        "manage",
    }
    can_edit = "dashboard.update" in context.permissions or level in {"edit", "manage"}
    can_interact = can_view and (
        "dashboard.query" in context.permissions
        or "semantic.query" in context.permissions
        or level in {"interact", "edit", "manage"}
    )
    can_manage_sharing = "dashboard.share" in context.permissions and level != "edit"

    # Resource-ACL overlay: ownership and explicit grants broaden access; an
    # explicit deny overrides inherited/role-derived access (see the resource
    # access engine precedence). This is additive to the RBAC + share decision.
    overlay = await resource_access_service.access_overlay(
        db,
        resource_type="dashboard",
        resource_id=dashboard.id,
        organization_id=context.organization_id,
        workspace_id=context.workspace_id,
        user_id=context.user_id,
        owner_user_id=dashboard.owner_user_id,
    )
    if overlay.is_owner:
        can_view = can_edit = can_interact = can_manage_sharing = True
    if overlay.allow_rank >= 0:
        can_view = True
    if overlay.allow_rank >= 1:
        can_interact = True
    if overlay.allow_rank >= 2:
        can_edit = True
    if overlay.allow_rank >= 3:
        can_manage_sharing = True
    if overlay.deny_rank is not None:
        if overlay.deny_rank <= 0:
            can_view = False
        if overlay.deny_rank <= 1:
            can_interact = False
        if overlay.deny_rank <= 2:
            can_edit = False
        if overlay.deny_rank <= 3:
            can_manage_sharing = False

    return {
        "can_view": can_view,
        "can_interact": can_interact,
        "can_edit": can_edit,
        "can_publish": "dashboard.publish" in context.permissions,
        "can_manage_sharing": can_manage_sharing,
        "can_snapshot": "dashboard.snapshot.create" in context.permissions,
    }


async def _summary(
    db: AsyncSession, context: AuthorizationContext, dashboard: Dashboard
) -> DashboardSummary:
    pages, widgets = await _counts(db, dashboard.id)
    return DashboardSummary(
        id=dashboard.id,
        slug=dashboard.slug,
        name=dashboard.name,
        description=dashboard.description,
        status=dashboard.status,
        owner_user_id=dashboard.owner_user_id,
        tags=dashboard.tags,
        row_version=dashboard.row_version,
        page_count=pages,
        widget_count=widgets,
        updated_at=dashboard.updated_at,
        published_version=await _published_number(db, dashboard),
    )


async def detail(
    db: AsyncSession, context: AuthorizationContext, dashboard: Dashboard
) -> DashboardDetail:
    summary = await _summary(db, context, dashboard)
    return DashboardDetail(
        **summary.model_dump(),
        created_at=dashboard.created_at,
        archived_at=dashboard.archived_at,
        access=await _access(db, context, dashboard),
    )


async def list_dashboards(
    db: AsyncSession,
    context: AuthorizationContext,
    *,
    search: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[DashboardSummary]:
    org, ws = _tenant(context)
    statement = select(Dashboard).where(
        Dashboard.organization_id == org,
        Dashboard.workspace_id == ws,
        Dashboard.archived_at.is_(None),
    )
    subjects = {context.user_id} | await resource_access_service.group_ids_for_user(
        db, org, context.user_id
    )
    allowed_ids, denied_ids = resource_access_service.collection_visibility_subqueries(
        "dashboard", subjects, now=datetime.now(UTC)
    )
    statement = statement.where(Dashboard.id.notin_(denied_ids))
    if resource_access_service.role_level("dashboard", context.permissions) is None:
        statement = statement.where(
            or_(Dashboard.owner_user_id == context.user_id, Dashboard.id.in_(allowed_ids))
        )
    if search:
        statement = statement.where(Dashboard.name.ilike(f"%{search[:100]}%"))
    if status:
        statement = statement.where(Dashboard.status == status)
    rows = (
        await db.scalars(
            statement.order_by(Dashboard.updated_at.desc()).limit(limit).offset(offset)
        )
    ).all()
    return [await _summary(db, context, item) for item in rows]


async def create_dashboard(
    db: AsyncSession, context: AuthorizationContext, payload: DashboardCreate
) -> DashboardDetail:
    org, ws = _tenant(context)
    dashboard = Dashboard(
        id=uuid4(),
        organization_id=org,
        workspace_id=ws,
        slug=_slug(payload.slug or payload.name),
        name=payload.name,
        description=payload.description,
        owner_user_id=context.user_id,
        created_by_user_id=context.user_id,
        updated_by_user_id=context.user_id,
        tags=payload.tags,
    )
    page = DashboardPage(
        id=uuid4(),
        organization_id=org,
        workspace_id=ws,
        dashboard_id=dashboard.id,
        page_key="page_1",
        name="Page 1",
        position=0,
    )
    dashboard.default_page_id = page.id
    db.add_all((dashboard, page))
    try:
        await record_audit(
            db,
            "dashboard.created",
            actor_user_id=context.user_id,
            organization_id=org,
            workspace_id=ws,
            resource_type="dashboard",
            resource_id=dashboard.id,
        )
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ApplicationError(
            code="DASHBOARD_SLUG_CONFLICT",
            message="A dashboard with this URL already exists.",
            status_code=409,
        ) from exc
    await db.refresh(dashboard)
    return await detail(db, context, dashboard)


async def _editor_parts(
    db: AsyncSession, dashboard: Dashboard
) -> tuple[list[PageInput], list[DashboardFilterInput]]:
    pages = (
        await db.scalars(
            select(DashboardPage)
            .where(DashboardPage.dashboard_id == dashboard.id)
            .order_by(DashboardPage.position)
        )
    ).all()
    widgets = (
        await db.scalars(
            select(DashboardWidget).where(DashboardWidget.dashboard_id == dashboard.id)
        )
    ).all()
    by_page: dict[UUID, list[WidgetInput]] = {}
    for widget in widgets:
        by_page.setdefault(widget.page_id, []).append(
            WidgetInput.model_validate(
                {
                    "id": widget.id,
                    "page_id": widget.page_id,
                    "type": widget.widget_type,
                    "title": widget.title,
                    "description": widget.description,
                    "semantic_model_id": widget.semantic_model_id,
                    "query": widget.query_definition,
                    "config": widget.visualization_config,
                    "layout": widget.layout,
                    "filters": widget.filters,
                    "interactions": widget.interactions,
                    "content": widget.content,
                    "hidden": widget.is_hidden,
                }
            )
        )
    page_contracts = [
        PageInput(
            id=page.id,
            key=page.page_key,
            name=page.name,
            description=page.description,
            position=page.position,
            canvas=page.canvas,
            widgets=by_page.get(page.id, []),
        )
        for page in pages
    ]
    filters = (
        await db.scalars(
            select(DashboardFilter)
            .where(DashboardFilter.dashboard_id == dashboard.id)
            .order_by(DashboardFilter.position)
        )
    ).all()
    filter_contracts = [
        DashboardFilterInput.model_validate(
            {
                "id": item.id,
                "key": item.filter_key,
                "label": item.label,
                "type": item.filter_type,
                "semantic_model_id": item.semantic_model_id,
                "dimension_key": item.dimension_key,
                "operator": item.operator,
                "default_value": item.default_value,
                "widget_ids": [UUID(value) for value in item.widget_ids],
                "position": item.position,
            }
        )
        for item in filters
    ]
    return page_contracts, filter_contracts


async def editor(
    db: AsyncSession, context: AuthorizationContext, dashboard_id: UUID
) -> EditorResponse:
    dashboard = await get_dashboard(db, context, dashboard_id)
    access = await _access(db, context, dashboard)
    if not access["can_edit"]:
        raise ApplicationError(
            code="DASHBOARD_ACCESS_DENIED",
            message="You do not have access to edit this dashboard.",
            status_code=403,
        )
    pages, filters = await _editor_parts(db, dashboard)
    return EditorResponse(
        dashboard=await detail(db, context, dashboard),
        pages=pages,
        filters=filters,
        version=dashboard.row_version,
        etag=f'"dashboard-{dashboard.row_version}"',
    )


async def _validate_semantics(
    db: AsyncSession,
    context: AuthorizationContext,
    pages: list[PageInput],
    filters: list[DashboardFilterInput],
) -> None:
    org, ws = _tenant(context)
    model_ids = {
        widget.semantic_model_id
        for page in pages
        for widget in page.widgets
        if widget.semantic_model_id
    } | {item.semantic_model_id for item in filters}
    if model_ids:
        found = set(
            (
                await db.scalars(
                    select(SemanticModel.id).where(
                        SemanticModel.id.in_(model_ids),
                        SemanticModel.organization_id == org,
                        SemanticModel.workspace_id == ws,
                        SemanticModel.status == "published",
                    )
                )
            ).all()
        )
        if found != model_ids:
            raise ApplicationError(
                code="DASHBOARD_SEMANTIC_MODEL_UNAVAILABLE",
                message="A referenced semantic model is unavailable.",
                status_code=422,
            )
    for page in pages:
        for widget in page.widgets:
            if widget.semantic_model_id is None:
                continue
            metric_keys = set(
                (
                    await db.scalars(
                        select(SemanticMetric.key).where(
                            SemanticMetric.semantic_model_id == widget.semantic_model_id,
                            SemanticMetric.organization_id == org,
                            SemanticMetric.workspace_id == ws,
                        )
                    )
                ).all()
            )
            dimension_keys = set(
                (
                    await db.scalars(
                        select(SemanticDimension.key).where(
                            SemanticDimension.semantic_model_id == widget.semantic_model_id,
                            SemanticDimension.organization_id == org,
                            SemanticDimension.workspace_id == ws,
                            SemanticDimension.is_hidden.is_(False),
                        )
                    )
                ).all()
            )
            if (
                not set(widget.query.metrics) <= metric_keys
                or not set(widget.query.dimensions) <= dimension_keys
            ):
                raise ApplicationError(
                    code="DASHBOARD_QUERY_INVALID",
                    message="A widget references an unavailable semantic field.",
                    status_code=422,
                )


async def save_editor(
    db: AsyncSession, context: AuthorizationContext, dashboard_id: UUID, payload: EditorSave
) -> EditorResponse:
    dashboard = await get_dashboard(db, context, dashboard_id, lock=True)
    access = await _access(db, context, dashboard)
    if not access["can_edit"]:
        raise ApplicationError(
            code="DASHBOARD_ACCESS_DENIED",
            message="You do not have access to edit this dashboard.",
            status_code=403,
        )
    _check_version(dashboard, payload.expected_version)
    await _validate_semantics(db, context, payload.pages, payload.filters)
    org, ws = _tenant(context)
    await db.execute(delete(DashboardFilter).where(DashboardFilter.dashboard_id == dashboard.id))
    await db.execute(delete(DashboardWidget).where(DashboardWidget.dashboard_id == dashboard.id))
    await db.execute(delete(DashboardPage).where(DashboardPage.dashboard_id == dashboard.id))
    all_widget_ids: set[UUID] = set()
    page_rows: list[DashboardPage] = []
    widget_rows: list[DashboardWidget] = []
    for page in payload.pages:
        page_id = page.id or uuid4()
        page_rows.append(
            DashboardPage(
                id=page_id,
                organization_id=org,
                workspace_id=ws,
                dashboard_id=dashboard.id,
                page_key=page.key,
                name=page.name,
                description=page.description,
                position=page.position,
                canvas=page.canvas,
            )
        )
        for widget in page.widgets:
            widget_id = widget.id or uuid4()
            all_widget_ids.add(widget_id)
            widget_rows.append(
                DashboardWidget(
                    id=widget_id,
                    organization_id=org,
                    workspace_id=ws,
                    dashboard_id=dashboard.id,
                    page_id=page_id,
                    widget_type=widget.type,
                    title=widget.title,
                    description=widget.description,
                    semantic_model_id=widget.semantic_model_id,
                    query_definition=widget.query.model_dump(mode="json"),
                    visualization_config=widget.config,
                    layout=widget.layout.model_dump(),
                    filters=[item.model_dump(mode="json") for item in widget.filters],
                    interactions=widget.interactions,
                    content=widget.content,
                    is_hidden=widget.hidden,
                )
            )
    filter_rows: list[DashboardFilter] = []
    for item in payload.filters:
        if not set(item.widget_ids) <= all_widget_ids:
            raise ApplicationError(
                code="DASHBOARD_FILTER_INVALID",
                message="A filter maps to an unknown widget.",
                status_code=422,
            )
        filter_rows.append(
            DashboardFilter(
                id=item.id or uuid4(),
                organization_id=org,
                workspace_id=ws,
                dashboard_id=dashboard.id,
                filter_key=item.key,
                label=item.label,
                filter_type=item.type,
                semantic_model_id=item.semantic_model_id,
                dimension_key=item.dimension_key,
                operator=item.operator,
                default_value=item.default_value,
                widget_ids=[str(value) for value in item.widget_ids],
                position=item.position,
            )
        )
    db.add_all(page_rows)
    db.add_all(widget_rows)
    db.add_all(filter_rows)
    dashboard.name, dashboard.description, dashboard.tags = (
        payload.name,
        payload.description,
        payload.tags,
    )
    dashboard.default_page_id = page_rows[0].id
    dashboard.updated_by_user_id = context.user_id
    dashboard.row_version += 1
    await record_audit(
        db,
        "dashboard.updated",
        actor_user_id=context.user_id,
        organization_id=org,
        workspace_id=ws,
        resource_type="dashboard",
        resource_id=dashboard.id,
        metadata={"dashboard_version": dashboard.row_version},
    )
    await db.commit()
    return await editor(db, context, dashboard.id)


async def aggregate_snapshot(
    db: AsyncSession, context: AuthorizationContext, dashboard: Dashboard
) -> dict[str, object]:
    pages, filters = await _editor_parts(db, dashboard)
    return {
        "schema_version": 1,
        "dashboard": {
            "id": str(dashboard.id),
            "slug": dashboard.slug,
            "name": dashboard.name,
            "description": dashboard.description,
            "tags": dashboard.tags,
        },
        "pages": [page.model_dump(mode="json") for page in pages],
        "filters": [item.model_dump(mode="json") for item in filters],
    }


async def publish(
    db: AsyncSession,
    context: AuthorizationContext,
    dashboard_id: UUID,
    expected_version: int,
    change_summary: str,
) -> VersionResponse:
    dashboard = await get_dashboard(db, context, dashboard_id, lock=True)
    _check_version(dashboard, expected_version)
    pages, filters = await _editor_parts(db, dashboard)
    await _validate_semantics(db, context, pages, filters)
    if not pages or not any(page.widgets for page in pages):
        raise ApplicationError(
            code="DASHBOARD_PUBLISH_VALIDATION_FAILED",
            message="Add at least one valid widget before publishing.",
            status_code=422,
        )
    number = (
        int(
            await db.scalar(
                select(func.coalesce(func.max(DashboardVersion.version_number), 0)).where(
                    DashboardVersion.dashboard_id == dashboard.id
                )
            )
            or 0
        )
        + 1
    )
    version = DashboardVersion(
        organization_id=dashboard.organization_id,
        workspace_id=dashboard.workspace_id,
        dashboard_id=dashboard.id,
        version_number=number,
        version_type="published",
        snapshot=await aggregate_snapshot(db, context, dashboard),
        created_by_user_id=context.user_id,
        published_at=datetime.now(UTC),
        change_summary=change_summary,
    )
    db.add(version)
    await db.flush()
    dashboard.published_version_id = version.id
    dashboard.status = "published"
    dashboard.row_version += 1
    await record_audit(
        db,
        "dashboard.published",
        actor_user_id=context.user_id,
        organization_id=dashboard.organization_id,
        workspace_id=dashboard.workspace_id,
        resource_type="dashboard",
        resource_id=dashboard.id,
        metadata={"dashboard_version": number},
    )
    await db.commit()
    return VersionResponse(
        id=version.id,
        version_number=number,
        version_type=version.version_type,
        created_by_user_id=version.created_by_user_id,
        created_at=version.created_at,
        published_at=version.published_at,
        change_summary=version.change_summary,
        current_published=True,
    )


async def versions(
    db: AsyncSession, context: AuthorizationContext, dashboard_id: UUID
) -> list[VersionResponse]:
    dashboard = await get_dashboard(db, context, dashboard_id)
    rows = (
        await db.scalars(
            select(DashboardVersion)
            .where(DashboardVersion.dashboard_id == dashboard.id)
            .order_by(DashboardVersion.version_number.desc())
            .limit(100)
        )
    ).all()
    return [
        VersionResponse(
            id=item.id,
            version_number=item.version_number,
            version_type=item.version_type,
            created_by_user_id=item.created_by_user_id,
            created_at=item.created_at,
            published_at=item.published_at,
            change_summary=item.change_summary,
            current_published=item.id == dashboard.published_version_id,
        )
        for item in rows
    ]


async def viewer(
    db: AsyncSession, context: AuthorizationContext, dashboard_id: UUID
) -> dict[str, object]:
    dashboard = await get_dashboard(db, context, dashboard_id)
    access = await _access(db, context, dashboard)
    if not access["can_view"] or dashboard.published_version_id is None:
        raise ApplicationError(
            code="DASHBOARD_NOT_PUBLISHED",
            message="The requested dashboard is unavailable.",
            status_code=404,
        )
    version = await db.scalar(
        select(DashboardVersion).where(
            DashboardVersion.id == dashboard.published_version_id,
            DashboardVersion.dashboard_id == dashboard.id,
        )
    )
    if version is None:
        raise _not_found()
    return {
        "dashboard": (await detail(db, context, dashboard)).model_dump(mode="json"),
        "version": version.version_number,
        "snapshot": version.snapshot,
        "access": access,
    }


async def restore(
    db: AsyncSession,
    context: AuthorizationContext,
    dashboard_id: UUID,
    version_id: UUID,
    expected_version: int,
) -> EditorResponse:
    dashboard = await get_dashboard(db, context, dashboard_id, lock=True)
    _check_version(dashboard, expected_version)
    version = await db.scalar(
        select(DashboardVersion).where(
            DashboardVersion.id == version_id,
            DashboardVersion.dashboard_id == dashboard.id,
            DashboardVersion.organization_id == dashboard.organization_id,
            DashboardVersion.workspace_id == dashboard.workspace_id,
        )
    )
    if version is None:
        raise ApplicationError(
            code="DASHBOARD_VERSION_NOT_FOUND",
            message="The requested dashboard version was not found.",
            status_code=404,
        )
    snapshot = version.snapshot
    page_values = cast(list[object], snapshot.get("pages", []))
    filter_values = cast(list[object], snapshot.get("filters", []))
    pages = [PageInput.model_validate(item) for item in page_values]
    filters = [DashboardFilterInput.model_validate(item) for item in filter_values]
    metadata = cast(dict[str, object], snapshot.get("dashboard", {}))
    payload = EditorSave(
        expected_version=expected_version,
        name=str(metadata.get("name", dashboard.name)),
        description=str(metadata.get("description", dashboard.description)),
        tags=cast(list[str], metadata.get("tags", [])),
        pages=pages,
        filters=filters,
        change_summary=f"Restored version {version.version_number}",
    )
    result = await save_editor(db, context, dashboard.id, payload)
    number = (
        int(
            await db.scalar(
                select(func.coalesce(func.max(DashboardVersion.version_number), 0)).where(
                    DashboardVersion.dashboard_id == dashboard.id
                )
            )
            or 0
        )
        + 1
    )
    db.add(
        DashboardVersion(
            organization_id=dashboard.organization_id,
            workspace_id=dashboard.workspace_id,
            dashboard_id=dashboard.id,
            version_number=number,
            version_type="restored",
            snapshot=version.snapshot,
            created_by_user_id=context.user_id,
            change_summary=payload.change_summary,
            source_version_id=version.id,
        )
    )
    await record_audit(
        db,
        "dashboard.version.restored",
        actor_user_id=context.user_id,
        organization_id=dashboard.organization_id,
        workspace_id=dashboard.workspace_id,
        resource_type="dashboard",
        resource_id=dashboard.id,
        metadata={"dashboard_version": number},
    )
    await db.commit()
    return result


async def archive(
    db: AsyncSession, context: AuthorizationContext, dashboard_id: UUID, expected_version: int
) -> None:
    dashboard = await get_dashboard(db, context, dashboard_id, lock=True)
    _check_version(dashboard, expected_version)
    dashboard.status, dashboard.archived_at, dashboard.row_version = (
        "archived",
        datetime.now(UTC),
        dashboard.row_version + 1,
    )
    await record_audit(
        db,
        "dashboard.archived",
        actor_user_id=context.user_id,
        organization_id=dashboard.organization_id,
        workspace_id=dashboard.workspace_id,
        resource_type="dashboard",
        resource_id=dashboard.id,
    )
    await db.commit()


async def list_shares(
    db: AsyncSession, context: AuthorizationContext, dashboard_id: UUID
) -> list[ShareResponse]:
    dashboard = await get_dashboard(db, context, dashboard_id)
    rows = (
        await db.scalars(
            select(DashboardShare)
            .where(DashboardShare.dashboard_id == dashboard.id)
            .order_by(DashboardShare.created_at.desc())
        )
    ).all()
    return [ShareResponse.model_validate(item, from_attributes=True) for item in rows]


async def create_share(
    db: AsyncSession, context: AuthorizationContext, dashboard_id: UUID, payload: ShareCreate
) -> ShareResponse:
    dashboard = await get_dashboard(db, context, dashboard_id, lock=True)
    _check_version(dashboard, payload.expected_version)
    org, ws = _tenant(context)
    if payload.principal_type == "user":
        org_member = await db.scalar(
            select(OrganizationMembership.id).where(
                OrganizationMembership.organization_id == org,
                OrganizationMembership.user_id == payload.principal_id,
                OrganizationMembership.status == MembershipStatus.ACTIVE,
            )
        )
        ws_member = await db.scalar(
            select(WorkspaceMembership.id).where(
                WorkspaceMembership.organization_id == org,
                WorkspaceMembership.workspace_id == ws,
                WorkspaceMembership.user_id == payload.principal_id,
                WorkspaceMembership.status == MembershipStatus.ACTIVE,
            )
        )
        if org_member is None or ws_member is None:
            raise ApplicationError(
                code="DASHBOARD_SHARE_INVALID",
                message="The share principal is not available in this workspace.",
                status_code=422,
            )
    else:
        expected_scope = (
            "workspace" if payload.principal_type == "workspace_role" else "organization"
        )
        role = await db.scalar(
            select(Role.id).where(Role.id == payload.principal_id, Role.scope == expected_scope)
        )
        if role is None:
            raise ApplicationError(
                code="DASHBOARD_SHARE_INVALID",
                message="The share role is not available at the requested scope.",
                status_code=422,
            )
    share = await db.scalar(
        select(DashboardShare).where(
            DashboardShare.dashboard_id == dashboard.id,
            DashboardShare.principal_type == payload.principal_type,
            DashboardShare.principal_id == payload.principal_id,
        )
    )
    if share is None:
        share = DashboardShare(
            organization_id=org,
            workspace_id=ws,
            dashboard_id=dashboard.id,
            principal_type=payload.principal_type,
            principal_id=payload.principal_id,
            permission_level=payload.permission_level,
            expires_at=payload.expires_at,
            created_by_user_id=context.user_id,
        )
        db.add(share)
    else:
        share.permission_level, share.expires_at, share.revoked_at = (
            payload.permission_level,
            payload.expires_at,
            None,
        )
    dashboard.row_version += 1
    await record_audit(
        db,
        "dashboard.share.created",
        actor_user_id=context.user_id,
        organization_id=org,
        workspace_id=ws,
        resource_type="dashboard",
        resource_id=dashboard.id,
        metadata={
            "share_level": payload.permission_level,
            "principal_type": payload.principal_type,
        },
    )
    await db.commit()
    await db.refresh(share)
    return ShareResponse.model_validate(share, from_attributes=True)


async def revoke_share(
    db: AsyncSession,
    context: AuthorizationContext,
    dashboard_id: UUID,
    share_id: UUID,
    expected_version: int,
) -> None:
    dashboard = await get_dashboard(db, context, dashboard_id, lock=True)
    _check_version(dashboard, expected_version)
    share = await db.scalar(
        select(DashboardShare).where(
            DashboardShare.id == share_id,
            DashboardShare.dashboard_id == dashboard.id,
            DashboardShare.organization_id == dashboard.organization_id,
            DashboardShare.workspace_id == dashboard.workspace_id,
        )
    )
    if share is None:
        raise ApplicationError(
            code="DASHBOARD_SHARE_INVALID",
            message="The requested share was not found.",
            status_code=404,
        )
    share.revoked_at, dashboard.row_version = datetime.now(UTC), dashboard.row_version + 1
    await record_audit(
        db,
        "dashboard.share.revoked",
        actor_user_id=context.user_id,
        organization_id=dashboard.organization_id,
        workspace_id=dashboard.workspace_id,
        resource_type="dashboard",
        resource_id=dashboard.id,
    )
    await db.commit()


async def list_snapshots(
    db: AsyncSession, context: AuthorizationContext, dashboard_id: UUID
) -> list[SnapshotResponse]:
    dashboard = await get_dashboard(db, context, dashboard_id)
    rows = (
        await db.scalars(
            select(DashboardSnapshot)
            .where(DashboardSnapshot.dashboard_id == dashboard.id)
            .order_by(DashboardSnapshot.created_at.desc())
            .limit(100)
        )
    ).all()
    return [SnapshotResponse.model_validate(item, from_attributes=True) for item in rows]


async def create_snapshot(
    db: AsyncSession,
    context: AuthorizationContext,
    dashboard_id: UUID,
    payload: SnapshotCreate,
    settings: Settings,
    data_snapshot: dict[str, object],
) -> SnapshotResponse:
    dashboard = await get_dashboard(db, context, dashboard_id)
    if dashboard.published_version_id is None:
        raise ApplicationError(
            code="DASHBOARD_NOT_PUBLISHED",
            message="Publish the dashboard before creating a snapshot.",
            status_code=422,
        )
    snapshot = DashboardSnapshot(
        organization_id=dashboard.organization_id,
        workspace_id=dashboard.workspace_id,
        dashboard_id=dashboard.id,
        dashboard_version_id=dashboard.published_version_id,
        name=payload.name,
        description=payload.description,
        filter_state=payload.filter_state,
        data_snapshot=data_snapshot,
        status="ready",
        created_by_user_id=context.user_id,
        expires_at=datetime.now(UTC) + timedelta(days=settings.DASHBOARD_SNAPSHOT_RETENTION_DAYS),
    )
    db.add(snapshot)
    await record_audit(
        db,
        "dashboard.snapshot.created",
        actor_user_id=context.user_id,
        organization_id=dashboard.organization_id,
        workspace_id=dashboard.workspace_id,
        resource_type="dashboard",
        resource_id=dashboard.id,
    )
    await db.commit()
    await db.refresh(snapshot)
    return SnapshotResponse.model_validate(snapshot, from_attributes=True)
