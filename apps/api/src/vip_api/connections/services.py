"""Governance-enforced connection lifecycle and secret-resolution services."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.auth.models import utc_now
from vip_api.connections.catalog import (
    CONNECTION_TYPE_BY_KEY,
    validate_configuration,
    validate_credentials,
)
from vip_api.connections.models import Connection, ConnectionType
from vip_api.connections.network import UnsafeDestinationError
from vip_api.connections.repositories import ConnectionRepository
from vip_api.connections.schemas import (
    ConnectionCreateRequest,
    ConnectionListResponse,
    ConnectionResponse,
    ConnectionTestError,
    ConnectionTestResponse,
    ConnectionTypeResponse,
    ConnectionTypeSummary,
    ConnectionUpdateRequest,
    CredentialReplaceRequest,
    CredentialReplaceResponse,
    SecretFieldState,
)
from vip_api.connections.secrets import SecretProvider, SecretProviderError
from vip_api.connections.testers import ConnectionTesterRegistry, TesterResult
from vip_api.core.config import Settings
from vip_api.core.context import get_correlation_id
from vip_api.core.errors import ApplicationError
from vip_api.governance.audit import record_audit
from vip_api.governance.context import AuthorizationContext
from vip_api.governance.services import (
    GovernanceRequirement,
    authorize,
    consume_quota,
    release_quota,
)

logger = logging.getLogger("vip_api.connections")

_FEATURE = "connection_studio"
_ENTITLEMENT = "connection_studio"


def requirement(permission: str, *, quota: str | None = None) -> GovernanceRequirement:
    return GovernanceRequirement(
        permission, feature=_FEATURE, entitlement=_ENTITLEMENT, quota=quota
    )


def _workspace(context: AuthorizationContext) -> UUID:
    if context.workspace_id is None:
        raise ApplicationError(
            code="WORKSPACE_CONTEXT_REQUIRED",
            message="A workspace context is required.",
            status_code=400,
        )
    return context.workspace_id


def _normalize_name(name: str) -> str:
    return " ".join(name.split()).casefold()


def _safe_credentials(payload: Mapping[str, object]) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in payload.items():
        get_secret_value = getattr(value, "get_secret_value", None)
        result[key] = str(get_secret_value() if callable(get_secret_value) else value)
    return result


def _validate_payload_size(value: object, limit: int, code: str) -> None:
    if len(json.dumps(value, default=lambda _value: "<secret>").encode()) > limit:
        raise ApplicationError(
            code=code, message="The submitted data is too large.", status_code=422
        )


def _validate_type_payload(
    type_key: str,
    configuration: dict[str, object],
    credentials: dict[str, str],
    settings: Settings,
) -> tuple[dict[str, object], dict[str, str]]:
    _validate_payload_size(
        configuration,
        settings.CONNECTION_MAX_CONFIGURATION_BYTES,
        "CONNECTION_CONFIGURATION_INVALID",
    )
    _validate_payload_size(
        {key: "<secret>" for key in credentials},
        settings.CONNECTION_MAX_SECRET_BYTES,
        "CONNECTION_CREDENTIALS_INVALID",
    )
    if (
        sum(len(value.encode()) for value in credentials.values())
        > settings.CONNECTION_MAX_SECRET_BYTES
    ):
        raise ApplicationError(
            code="CONNECTION_CREDENTIALS_INVALID",
            message="The submitted credentials are too large.",
            status_code=422,
        )
    try:
        safe_config = validate_configuration(type_key, configuration)
        safe_credentials = {
            key: value
            for key, value in validate_credentials(type_key, dict(credentials)).items()
            if value is not None
        }
    except (ValidationError, ValueError) as exc:
        raise ApplicationError(
            code="CONNECTION_CONFIGURATION_INVALID",
            message="The connection configuration or credentials are invalid.",
            status_code=422,
        ) from exc
    if type_key == "rest_api":
        auth_type = safe_config["auth_type"]
        required = {"bearer": "token", "api_key": "api_key"}.get(str(auth_type))
        if required and required not in safe_credentials:
            raise ApplicationError(
                code="CONNECTION_CREDENTIALS_REQUIRED",
                message="Credentials are required for this connection.",
                status_code=422,
            )
        if auth_type == "none":
            safe_credentials = {}
    return safe_config, safe_credentials


def serialize_connection(
    connection: Connection, connection_type: ConnectionType, *, detail: bool
) -> ConnectionResponse:
    properties = connection_type.secret_schema.get("properties", {})
    property_names = properties.keys() if isinstance(properties, dict) else ()
    fields = {
        key: SecretFieldState(configured=connection.secret_id is not None) for key in property_names
    }
    return ConnectionResponse(
        id=connection.id,
        name=connection.name,
        description=connection.description,
        type=ConnectionTypeSummary(key=connection_type.key, name=connection_type.name),
        status=connection.status,
        health_status=connection.health_status,
        configuration=connection.configuration if detail else None,
        credentials_configured=connection.secret_id is not None,
        secret_fields=fields,
        credential_version=connection.credential_version,
        last_tested_at=connection.last_tested_at,
        last_test_status=connection.last_test_status,
        last_test_error_code=connection.last_test_error_code,
        last_test_latency_ms=connection.last_test_latency_ms,
        last_healthy_at=connection.last_healthy_at,
        created_at=connection.created_at,
        updated_at=connection.updated_at,
        version=connection.version,
    )


def serialize_type(item: ConnectionType) -> ConnectionTypeResponse:
    # Enterprise metadata (implementation status, vendor, auth methods, network
    # requirements) is code-authoritative and served from the checked-in catalog.
    definition = CONNECTION_TYPE_BY_KEY.get(item.key)
    if definition is not None:
        status = definition.implementation_status
    else:
        status = "available" if item.is_enabled else "planned"
    return ConnectionTypeResponse(
        key=item.key,
        name=item.name,
        description=item.description,
        category=item.category,
        subcategory=definition.subcategory if definition else "",
        vendor=definition.vendor if definition else item.name,
        implementation_status=status,
        deployment=definition.deployment if definition else "cloud",
        auth_methods=list(definition.auth_methods) if definition else [],
        documentation_reference=definition.documentation_reference if definition else None,
        requirements=list(definition.requirements) if definition else [],
        feature_flag=definition.feature_flag if definition else None,
        beta=definition.beta if definition else False,
        configuration_schema=item.configuration_schema,
        secret_schema=item.secret_schema,
        capabilities=item.capabilities,
        test_strategy=item.test_strategy,
        is_enabled=item.is_enabled,
        version=item.version,
    )


async def list_connection_types(
    db: AsyncSession, context: AuthorizationContext
) -> list[ConnectionTypeResponse]:
    await authorize(db, context, requirement("connection.types.read"))
    return [serialize_type(item) for item in await ConnectionRepository(db).list_types()]


async def list_connections(
    db: AsyncSession,
    context: AuthorizationContext,
    *,
    page: int,
    page_size: int,
) -> ConnectionListResponse:
    await authorize(db, context, requirement("connection.read"))
    rows, total = await ConnectionRepository(db).list_scoped(
        context.organization_id, _workspace(context), page=page, page_size=page_size
    )
    return ConnectionListResponse(
        items=[serialize_connection(*row, detail=False) for row in rows],
        page=page,
        page_size=page_size,
        total=total,
    )


async def create_connection(
    db: AsyncSession,
    context: AuthorizationContext,
    payload: ConnectionCreateRequest,
    settings: Settings,
    secret_provider: SecretProvider,
) -> ConnectionResponse:
    await authorize(db, context, requirement("connection.create", quota="connections.max"))
    workspace_id = _workspace(context)
    repository = ConnectionRepository(db)
    connection_type = await repository.get_type(payload.connection_type)
    if connection_type is None:
        raise ApplicationError(
            code="CONNECTION_TYPE_NOT_FOUND",
            message="The connection type was not found.",
            status_code=404,
        )
    if not connection_type.is_enabled:
        raise ApplicationError(
            code="CONNECTION_TYPE_DISABLED",
            message="The connection type is disabled.",
            status_code=409,
        )
    normalized_name = _normalize_name(payload.name)
    if await repository.name_exists(context.organization_id, workspace_id, normalized_name):
        raise ApplicationError(
            code="CONNECTION_NAME_CONFLICT",
            message="A connection with that name already exists.",
            status_code=409,
        )
    credentials = _safe_credentials(payload.credentials)
    configuration, credentials = _validate_type_payload(
        connection_type.key, payload.configuration, credentials, settings
    )
    await consume_quota(db, context, "connections.max")
    connection = Connection(
        organization_id=context.organization_id,
        workspace_id=workspace_id,
        connection_type_id=connection_type.id,
        connection_type_version=connection_type.version,
        name=" ".join(payload.name.split()),
        normalized_name=normalized_name,
        description=payload.description.strip(),
        configuration=configuration,
        created_by_user_id=context.user_id,
        updated_by_user_id=context.user_id,
    )
    db.add(connection)
    await db.flush()
    if credentials:
        secret = await secret_provider.store_secret(
            db,
            organization_id=context.organization_id,
            workspace_id=workspace_id,
            connection_id=connection.id,
            credential_version=1,
            credentials=credentials,
            actor_user_id=context.user_id,
        )
        connection.secret_id = secret.id
        connection.credential_version = 1
        await record_audit(
            db,
            "connection.credentials.configured",
            actor_user_id=context.user_id,
            organization_id=context.organization_id,
            workspace_id=workspace_id,
            resource_type="connection",
            resource_id=connection.id,
            metadata={"provider": secret.provider, "credential_version": 1},
        )
    await record_audit(
        db,
        "connection.created",
        actor_user_id=context.user_id,
        organization_id=context.organization_id,
        workspace_id=workspace_id,
        resource_type="connection",
        resource_id=connection.id,
        metadata={"connection_type": connection_type.key},
    )
    await db.commit()
    logger.info(
        "Connection created",
        extra={
            "connection_id": str(connection.id),
            "connection_type": connection_type.key,
            "organization_id": str(context.organization_id),
            "workspace_id": str(workspace_id),
            "actor_user_id": str(context.user_id),
        },
    )
    return serialize_connection(connection, connection_type, detail=True)


async def get_connection(
    db: AsyncSession, context: AuthorizationContext, connection_id: UUID
) -> ConnectionResponse:
    await authorize(db, context, requirement("connection.read"))
    row = await ConnectionRepository(db).get_scoped(
        context.organization_id, _workspace(context), connection_id
    )
    if row is None:
        raise ApplicationError(
            code="CONNECTION_NOT_FOUND", message="The connection was not found.", status_code=404
        )
    return serialize_connection(*row, detail=True)


async def update_connection(
    db: AsyncSession,
    context: AuthorizationContext,
    connection_id: UUID,
    payload: ConnectionUpdateRequest,
    settings: Settings,
) -> ConnectionResponse:
    await authorize(db, context, requirement("connection.update"))
    workspace_id = _workspace(context)
    repository = ConnectionRepository(db)
    row = await repository.get_scoped(
        context.organization_id, workspace_id, connection_id, for_update=True
    )
    if row is None:
        raise ApplicationError(
            code="CONNECTION_NOT_FOUND", message="The connection was not found.", status_code=404
        )
    connection, connection_type = row
    if connection.version != payload.version:
        raise ApplicationError(
            code="CONNECTION_VERSION_CONFLICT",
            message="The connection was modified by another request.",
            status_code=409,
        )
    if payload.name is not None:
        normalized = _normalize_name(payload.name)
        if await repository.name_exists(
            context.organization_id, workspace_id, normalized, excluding_id=connection.id
        ):
            raise ApplicationError(
                code="CONNECTION_NAME_CONFLICT",
                message="A connection with that name already exists.",
                status_code=409,
            )
        connection.name = " ".join(payload.name.split())
        connection.normalized_name = normalized
    if payload.description is not None:
        connection.description = payload.description.strip()
    if payload.status is not None:
        connection.status = payload.status
    if payload.configuration is not None:
        _validate_payload_size(
            payload.configuration,
            settings.CONNECTION_MAX_CONFIGURATION_BYTES,
            "CONNECTION_CONFIGURATION_INVALID",
        )
        try:
            connection.configuration = validate_configuration(
                connection_type.key, payload.configuration
            )
        except (ValidationError, ValueError) as exc:
            raise ApplicationError(
                code="CONNECTION_CONFIGURATION_INVALID",
                message="The connection configuration is invalid.",
                status_code=422,
            ) from exc
        _reset_health(connection)
    connection.version += 1
    connection.updated_by_user_id = context.user_id
    await record_audit(
        db,
        "connection.updated",
        actor_user_id=context.user_id,
        organization_id=context.organization_id,
        workspace_id=workspace_id,
        resource_type="connection",
        resource_id=connection.id,
        metadata={"connection_type": connection_type.key},
    )
    await db.commit()
    return serialize_connection(connection, connection_type, detail=True)


async def archive_connection(
    db: AsyncSession,
    context: AuthorizationContext,
    connection_id: UUID,
    *,
    permission: str = "connection.archive",
    audit_event: str = "connection.archived",
) -> None:
    await authorize(db, context, requirement(permission))
    workspace_id = _workspace(context)
    row = await ConnectionRepository(db).get_scoped(
        context.organization_id, workspace_id, connection_id, for_update=True
    )
    if row is None:
        raise ApplicationError(
            code="CONNECTION_NOT_FOUND", message="The connection was not found.", status_code=404
        )
    connection, connection_type = row
    was_active = connection.status != "archived"
    connection.status = "archived"
    connection.archived_at = utc_now()
    connection.version += 1
    connection.updated_by_user_id = context.user_id
    await record_audit(
        db,
        audit_event,
        actor_user_id=context.user_id,
        organization_id=context.organization_id,
        workspace_id=workspace_id,
        resource_type="connection",
        resource_id=connection.id,
        metadata={"connection_type": connection_type.key},
    )
    if was_active:
        await release_quota(db, context, "connections.max")
    await db.commit()


async def replace_credentials(
    db: AsyncSession,
    context: AuthorizationContext,
    connection_id: UUID,
    payload: CredentialReplaceRequest,
    settings: Settings,
    secret_provider: SecretProvider,
    *,
    rotated: bool = False,
) -> CredentialReplaceResponse:
    permission = "connection.credentials.rotate" if rotated else "connection.credentials.update"
    await authorize(db, context, requirement(permission))
    workspace_id = _workspace(context)
    row = await ConnectionRepository(db).get_scoped(
        context.organization_id, workspace_id, connection_id, for_update=True
    )
    if row is None:
        raise ApplicationError(
            code="CONNECTION_NOT_FOUND", message="The connection was not found.", status_code=404
        )
    connection, connection_type = row
    if connection.version != payload.expected_version:
        raise ApplicationError(
            code="CONNECTION_VERSION_CONFLICT",
            message="The connection was modified by another request.",
            status_code=409,
        )
    raw = _safe_credentials(payload.credentials)
    _, credentials = _validate_type_payload(
        connection_type.key, connection.configuration, raw, settings
    )
    if not credentials:
        raise ApplicationError(
            code="CONNECTION_CREDENTIALS_REQUIRED",
            message="Credentials are required for this connection.",
            status_code=422,
        )
    old_secret_id = connection.secret_id
    new_version = connection.credential_version + 1
    new_secret = await secret_provider.store_secret(
        db,
        organization_id=context.organization_id,
        workspace_id=workspace_id,
        connection_id=connection.id,
        credential_version=new_version,
        credentials=credentials,
        actor_user_id=context.user_id,
    )
    connection.secret_id = new_secret.id
    connection.credential_version = new_version
    connection.version += 1
    connection.updated_by_user_id = context.user_id
    _reset_health(connection)
    if old_secret_id is not None:
        await secret_provider.revoke_secret(
            db,
            organization_id=context.organization_id,
            workspace_id=workspace_id,
            secret_id=old_secret_id,
        )
    event = "connection.credentials.rotated" if rotated else "connection.credentials.replaced"
    await record_audit(
        db,
        event,
        actor_user_id=context.user_id,
        organization_id=context.organization_id,
        workspace_id=workspace_id,
        resource_type="connection",
        resource_id=connection.id,
        metadata={
            "provider": new_secret.provider,
            "credential_version": new_version,
            "rotation_reason_recorded": bool(payload.rotation_reason),
        },
    )
    await db.commit()
    return CredentialReplaceResponse(connection_id=connection.id, credential_version=new_version)


async def test_connection(
    db: AsyncSession,
    context: AuthorizationContext,
    connection_id: UUID,
    secret_provider: SecretProvider,
    testers: ConnectionTesterRegistry,
) -> ConnectionTestResponse:
    await authorize(db, context, requirement("connection.test"))
    workspace_id = _workspace(context)
    row = await ConnectionRepository(db).get_scoped(
        context.organization_id, workspace_id, connection_id, for_update=True
    )
    if row is None:
        raise ApplicationError(
            code="CONNECTION_NOT_FOUND", message="The connection was not found.", status_code=404
        )
    connection, connection_type = row
    if connection.status == "archived":
        raise ApplicationError(
            code="CONNECTION_ARCHIVED",
            message="Archived connections cannot be tested.",
            status_code=409,
        )
    credentials_required = (
        connection_type.key != "rest_api" or connection.configuration.get("auth_type") != "none"
    )
    if connection.secret_id is None and credentials_required:
        raise ApplicationError(
            code="CONNECTION_CREDENTIALS_NOT_CONFIGURED",
            message="Connection credentials are not configured.",
            status_code=409,
        )
    credentials: dict[str, str] = {}
    try:
        if connection.secret_id is not None:
            credentials = await secret_provider.read_secret(
                db,
                organization_id=context.organization_id,
                workspace_id=workspace_id,
                connection_id=connection.id,
                secret_id=connection.secret_id,
            )
        result = await testers.get(connection_type.key).test(connection.configuration, credentials)
    except UnsafeDestinationError:
        result = _failed_result("CONNECTION_DESTINATION_BLOCKED")
    except (SecretProviderError, LookupError, KeyError):
        await record_audit(
            db,
            "connection.secret.resolve.failed",
            actor_user_id=context.user_id,
            organization_id=context.organization_id,
            workspace_id=workspace_id,
            outcome="failed",
            reason_code="CONNECTION_SECRET_UNAVAILABLE",
            resource_type="connection",
            resource_id=connection.id,
        )
        result = _failed_result("CONNECTION_SECRET_UNAVAILABLE")
    tested_at = utc_now()
    connection.last_tested_at = tested_at
    connection.last_test_latency_ms = result.latency_ms
    connection.last_test_status = "success" if result.success else "failed"
    connection.last_test_error_code = result.error_code
    connection.health_status = result.health_status
    if result.success:
        connection.last_healthy_at = tested_at
        connection.consecutive_failures = 0
    else:
        connection.consecutive_failures += 1
    event = "connection.test.succeeded" if result.success else "connection.test.failed"
    await record_audit(
        db,
        event,
        actor_user_id=context.user_id,
        organization_id=context.organization_id,
        workspace_id=workspace_id,
        outcome="success" if result.success else "failed",
        reason_code=result.error_code,
        resource_type="connection",
        resource_id=connection.id,
        metadata={
            "connection_type": connection_type.key,
            "health_status": result.health_status,
            "latency_bucket": _latency_bucket(result.latency_ms),
        },
    )
    await db.commit()
    logger.info(
        "Connection test completed",
        extra={
            "connection_id": str(connection.id),
            "connection_type": connection_type.key,
            "organization_id": str(context.organization_id),
            "workspace_id": str(workspace_id),
            "actor_user_id": str(context.user_id),
            "health_status": result.health_status,
            "test_outcome": connection.last_test_status,
            "error_code": result.error_code,
            "latency_ms": result.latency_ms,
        },
    )
    return ConnectionTestResponse(
        connection_id=connection.id,
        status="success" if result.success else "failed",
        health_status=result.health_status,
        tested_at=tested_at,
        latency_ms=result.latency_ms,
        message="Connection established successfully." if result.success else None,
        error=None
        if result.success
        else ConnectionTestError(
            code=result.error_code or "CONNECTION_TEST_FAILED",
            message=_error_message(result.error_code),
        ),
        correlation_id=get_correlation_id(),
    )


def _failed_result(code: str) -> TesterResult:
    return TesterResult(False, "unhealthy", 0, code)


def _reset_health(connection: Connection) -> None:
    connection.health_status = "unknown"
    connection.last_test_status = None
    connection.last_test_error_code = None
    connection.last_test_latency_ms = None


def _latency_bucket(value: int) -> str:
    if value < 100:
        return "lt_100ms"
    if value < 1000:
        return "100ms_1s"
    return "gte_1s"


def _error_message(code: str | None) -> str:
    return {
        "CONNECTION_AUTHENTICATION_FAILED": "The connection could not be authenticated.",
        "CONNECTION_TIMEOUT": "The connection test timed out.",
        "CONNECTION_TLS_FAILED": "The secure connection could not be established.",
        "CONNECTION_DESTINATION_BLOCKED": "The destination is blocked by network policy.",
        "CONNECTION_SECRET_UNAVAILABLE": "Connection credentials are unavailable.",
    }.get(code or "", "The connection test failed.")
