"""Governance-covered connection and write-only credential APIs."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from vip_api.auth.dependencies import require_csrf
from vip_api.connections.dependencies import (
    RequireConnectionGovernance,
    get_secret_provider,
    get_tester_registry,
)
from vip_api.connections.schemas import (
    ConnectionCreateRequest,
    ConnectionListResponse,
    ConnectionResponse,
    ConnectionTestResponse,
    ConnectionTypeResponse,
    ConnectionUpdateRequest,
    CredentialReplaceRequest,
    CredentialReplaceResponse,
)
from vip_api.connections.secrets import DatabaseEncryptedSecretProvider
from vip_api.connections.services import (
    archive_connection,
    create_connection,
    get_connection,
    list_connection_types,
    list_connections,
    replace_credentials,
    test_connection,
    update_connection,
)
from vip_api.connections.testers import ConnectionTesterRegistry
from vip_api.core.config import Settings, get_settings
from vip_api.database.session import get_db_session
from vip_api.governance.context import AuthorizationContext

router = APIRouter(prefix="/connections", tags=["connections"])


def _policy(permission: str, *, quota: str | None = None) -> object:
    return RequireConnectionGovernance(permission, quota=quota)


@router.get("/types", response_model=list[ConnectionTypeResponse])
async def get_connection_types(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(_policy("connection.types.read"))],
) -> list[ConnectionTypeResponse]:
    return await list_connection_types(db, context)


@router.get("", response_model=ConnectionListResponse, response_model_exclude_none=True)
async def get_connections(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(_policy("connection.read"))],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> ConnectionListResponse:
    return await list_connections(db, context, page=page, page_size=page_size)


@router.post(
    "",
    response_model=ConnectionResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def post_connection(
    payload: ConnectionCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[
        AuthorizationContext, Depends(_policy("connection.create", quota="connections.max"))
    ],
    settings: Annotated[Settings, Depends(get_settings)],
    secret_provider: Annotated[DatabaseEncryptedSecretProvider, Depends(get_secret_provider)],
) -> ConnectionResponse:
    return await create_connection(db, context, payload, settings, secret_provider)


@router.get("/{connection_id}", response_model=ConnectionResponse)
async def get_connection_detail(
    connection_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(_policy("connection.read"))],
) -> ConnectionResponse:
    return await get_connection(db, context, connection_id)


@router.patch(
    "/{connection_id}",
    response_model=ConnectionResponse,
    dependencies=[Depends(require_csrf)],
)
async def patch_connection(
    connection_id: UUID,
    payload: ConnectionUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(_policy("connection.update"))],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ConnectionResponse:
    return await update_connection(db, context, connection_id, payload, settings)


@router.post(
    "/{connection_id}/archive",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
async def post_archive_connection(
    connection_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(_policy("connection.archive"))],
) -> Response:
    await archive_connection(db, context, connection_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/{connection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
async def delete_connection(
    connection_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(_policy("connection.delete"))],
) -> Response:
    await archive_connection(
        db,
        context,
        connection_id,
        permission="connection.delete",
        audit_event="connection.deleted",
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put(
    "/{connection_id}/credentials",
    response_model=CredentialReplaceResponse,
    dependencies=[Depends(require_csrf)],
)
async def put_credentials(
    connection_id: UUID,
    payload: CredentialReplaceRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(_policy("connection.credentials.update"))],
    settings: Annotated[Settings, Depends(get_settings)],
    secret_provider: Annotated[DatabaseEncryptedSecretProvider, Depends(get_secret_provider)],
) -> CredentialReplaceResponse:
    return await replace_credentials(db, context, connection_id, payload, settings, secret_provider)


@router.post(
    "/{connection_id}/credentials/rotate",
    response_model=CredentialReplaceResponse,
    dependencies=[Depends(require_csrf)],
)
async def post_rotate_credentials(
    connection_id: UUID,
    payload: CredentialReplaceRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(_policy("connection.credentials.rotate"))],
    settings: Annotated[Settings, Depends(get_settings)],
    secret_provider: Annotated[DatabaseEncryptedSecretProvider, Depends(get_secret_provider)],
) -> CredentialReplaceResponse:
    return await replace_credentials(
        db, context, connection_id, payload, settings, secret_provider, rotated=True
    )


@router.post(
    "/{connection_id}/test",
    response_model=ConnectionTestResponse,
    dependencies=[Depends(require_csrf)],
)
async def post_test_connection(
    connection_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[AuthorizationContext, Depends(_policy("connection.test"))],
    secret_provider: Annotated[DatabaseEncryptedSecretProvider, Depends(get_secret_provider)],
    testers: Annotated[ConnectionTesterRegistry, Depends(get_tester_registry)],
) -> ConnectionTestResponse:
    return await test_connection(db, context, connection_id, secret_provider, testers)
