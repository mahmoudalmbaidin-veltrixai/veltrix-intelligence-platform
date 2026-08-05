"""OpenAPI-wide production contract and unauthenticated fail-closed sweep."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select
from starlette.testclient import TestClient

from vip_api.api.operation_coverage import build_coverage
from vip_api.auth.models import User, UserStatus
from vip_api.auth.password import PasswordService
from vip_api.core.config import Settings
from vip_api.database.session import Database
from vip_api.governance.models import (
    Entitlement,
    FeatureFlag,
    FeatureFlagOverride,
    OrganizationEntitlement,
    Role,
)
from vip_api.main import create_application
from vip_api.tenancy.models import (
    MembershipStatus,
    Organization,
    OrganizationMembership,
    OrganizationStatus,
    Workspace,
    WorkspaceMembership,
    WorkspaceStatus,
)

HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


@dataclass(frozen=True)
class ContractPersonas:
    usernames: dict[str, str]
    password: str
    organizations: dict[str, UUID]
    workspaces: dict[str, UUID]


async def _seed_contract_personas(settings: Settings) -> ContractPersonas:
    database = Database(settings)
    suffix = uuid4().hex[:10]
    password = f"Contract-{uuid4().hex}-9!"
    try:
        async with database.session_factory() as db:
            roles = {role.key: role.id for role in (await db.scalars(select(Role))).all()}
            users = {
                "admin": User(
                    username=f"contract-admin-{suffix}",
                    normalized_username=f"contract-admin-{suffix}",
                    email=f"contract-admin-{suffix}@vip.test",
                    normalized_email=f"contract-admin-{suffix}@vip.test",
                    display_name="Contract Admin",
                    password_hash=PasswordService(settings).hash_password(password),
                    status=UserStatus.ACTIVE,
                    is_platform_admin=True,
                ),
                "restricted": User(
                    username=f"contract-restricted-{suffix}",
                    normalized_username=f"contract-restricted-{suffix}",
                    email=f"contract-restricted-{suffix}@vip.test",
                    normalized_email=f"contract-restricted-{suffix}@vip.test",
                    display_name="Contract Restricted",
                    password_hash=PasswordService(settings).hash_password(password),
                    status=UserStatus.ACTIVE,
                ),
                "cross": User(
                    username=f"contract-cross-{suffix}",
                    normalized_username=f"contract-cross-{suffix}",
                    email=f"contract-cross-{suffix}@vip.test",
                    normalized_email=f"contract-cross-{suffix}@vip.test",
                    display_name="Contract Cross Tenant",
                    password_hash=PasswordService(settings).hash_password(password),
                    status=UserStatus.ACTIVE,
                ),
                "suspended": User(
                    username=f"contract-suspended-{suffix}",
                    normalized_username=f"contract-suspended-{suffix}",
                    email=f"contract-suspended-{suffix}@vip.test",
                    normalized_email=f"contract-suspended-{suffix}@vip.test",
                    display_name="Contract Suspended",
                    password_hash=PasswordService(settings).hash_password(password),
                    status=UserStatus.SUSPENDED,
                ),
            }
            db.add_all(users.values())
            await db.flush()
            organizations = {
                key: Organization(
                    name=f"Contract {key.title()} {suffix}",
                    slug=f"contract-{key}-{suffix}",
                    status=OrganizationStatus.ACTIVE,
                    created_by_user_id=users["admin" if key == "alpha" else "cross"].id,
                )
                for key in ("alpha", "beta")
            }
            db.add_all(organizations.values())
            await db.flush()
            workspaces = {
                key: Workspace(
                    organization_id=organization.id,
                    name=f"Contract {key.title()}",
                    slug="default",
                    status=WorkspaceStatus.ACTIVE,
                    is_default=True,
                    created_by_user_id=users["admin" if key == "alpha" else "cross"].id,
                )
                for key, organization in organizations.items()
            }
            db.add_all(workspaces.values())
            await db.flush()
            memberships = [
                ("admin", "alpha", "organization_owner", "workspace_admin"),
                ("restricted", "alpha", "organization_member", "viewer"),
                ("cross", "beta", "organization_owner", "workspace_admin"),
            ]
            for user_key, tenant_key, org_role, workspace_role in memberships:
                db.add(
                    OrganizationMembership(
                        organization_id=organizations[tenant_key].id,
                        user_id=users[user_key].id,
                        role_id=roles[org_role],
                        status=MembershipStatus.ACTIVE,
                    )
                )
                db.add(
                    WorkspaceMembership(
                        organization_id=organizations[tenant_key].id,
                        workspace_id=workspaces[tenant_key].id,
                        user_id=users[user_key].id,
                        role_id=roles[workspace_role],
                        status=MembershipStatus.ACTIVE,
                    )
                )
            for entitlement in (await db.scalars(select(Entitlement))).all():
                db.add(
                    OrganizationEntitlement(
                        organization_id=organizations["alpha"].id,
                        entitlement_id=entitlement.id,
                        status="active",
                        source="test",
                    )
                )
            for flag in (await db.scalars(select(FeatureFlag))).all():
                db.add(
                    FeatureFlagOverride(
                        feature_flag_id=flag.id,
                        organization_id=organizations["alpha"].id,
                        workspace_id=workspaces["alpha"].id,
                        enabled=True,
                    )
                )
            await db.commit()
            return ContractPersonas(
                usernames={key: user.username for key, user in users.items()},
                password=password,
                organizations={key: value.id for key, value in organizations.items()},
                workspaces={key: value.id for key, value in workspaces.items()},
            )
    finally:
        await database.dispose()


async def _cleanup_contract_personas(settings: Settings, personas: ContractPersonas) -> None:
    database = Database(settings)
    try:
        async with database.session_factory() as db:
            await db.execute(
                delete(Organization).where(
                    Organization.id.in_(list(personas.organizations.values()))
                )
            )
            await db.execute(
                delete(User).where(User.username.in_(list(personas.usernames.values())))
            )
            await db.commit()
    finally:
        await database.dispose()


def _operations(document: dict[str, Any]) -> Iterator[tuple[str, str, dict[str, Any]]]:
    for path, path_item in document["paths"].items():
        for method, operation in path_item.items():
            if method in HTTP_METHODS:
                yield path, method, operation


def _resolve_ref(document: dict[str, Any], reference: str) -> object:
    assert reference.startswith("#/"), f"external OpenAPI reference is not allowed: {reference}"
    value: object = document
    for part in reference[2:].split("/"):
        value = cast(dict[str, object], value)[part.replace("~1", "/").replace("~0", "~")]
    return value


def _walk_refs(document: dict[str, Any], value: object) -> None:
    if isinstance(value, dict):
        reference = value.get("$ref")
        if isinstance(reference, str):
            _resolve_ref(document, reference)
        for nested in value.values():
            _walk_refs(document, nested)
    elif isinstance(value, list):
        for nested in value:
            _walk_refs(document, nested)


def _sample(schema: dict[str, Any], name: str) -> str:
    if schema.get("format") == "uuid" or name.endswith("_id"):
        return "not-a-uuid"
    if schema.get("type") == "integer":
        return "0"
    return "contract-sweep"


def _path_for(path: str, operation: dict[str, Any]) -> str:
    parameters = {
        item["name"]: item for item in operation.get("parameters", []) if item.get("in") == "path"
    }
    return re.sub(
        r"\{([^}]+)\}",
        lambda match: _sample(parameters.get(match.group(1), {}).get("schema", {}), match.group(1)),
        path,
    )


@pytest.mark.integration
def test_every_production_operation_has_a_resolvable_contract_and_fails_closed(
    settings: Settings,
) -> None:
    app = create_application(settings)
    document = app.openapi()
    operations = list(_operations(document))

    # Pin the enterprise surface against accidental disappearance while allowing
    # additive API growth. The certified baseline exposes 192 paths / 247 ops.
    assert len(document["paths"]) >= 192
    assert len(operations) >= 247
    assert len({operation["operationId"] for _, _, operation in operations}) == len(operations)
    _walk_refs(document, document)

    contract_errors: list[str] = []
    for path, method, operation in operations:
        responses = operation.get("responses", {})
        if not any(str(status).startswith("2") for status in responses):
            contract_errors.append(f"{method.upper()} {path}: no declared 2xx response")
        if not operation.get("summary") or not operation.get("tags"):
            contract_errors.append(f"{method.upper()} {path}: summary/tags missing")
        if "{" in path:
            declared = {
                item["name"]
                for item in operation.get("parameters", [])
                if item.get("in") == "path" and item.get("required") is True
            }
            expected = set(re.findall(r"\{([^}]+)\}", path))
            if declared != expected:
                contract_errors.append(
                    f"{method.upper()} {path}: path parameters "
                    f"{sorted(declared)} != {sorted(expected)}"
                )
    assert not contract_errors, "\n".join(contract_errors)

    # This is intentionally unauthenticated and uses invalid UUIDs/empty bodies:
    # it cannot mutate tenant data. Every implemented operation must reject or
    # serve the request without leaking an unhandled 5xx exception.
    runtime_errors: list[str] = []
    with TestClient(app, raise_server_exceptions=False) as client:
        for path, method, operation in operations:
            response = client.request(
                method.upper(),
                _path_for(path, operation),
                json={} if method in {"post", "put", "patch"} else None,
                follow_redirects=False,
            )
            if response.status_code >= 500:
                runtime_errors.append(
                    f"{method.upper()} {path}: unexpected {response.status_code} "
                    f"{response.text[:160]}"
                )
            if response.status_code >= 400 and response.headers.get("content-type", "").startswith(
                "application/json"
            ):
                payload = response.json()
                if "error" in payload:
                    error = payload["error"]
                    if (
                        not isinstance(error, dict)
                        or not error.get("code")
                        or not error.get("message")
                    ):
                        runtime_errors.append(f"{method.upper()} {path}: malformed error envelope")
    assert not runtime_errors, "\n".join(runtime_errors)


@pytest.mark.integration
def test_every_operation_is_classified_for_authenticated_certification(settings: Settings) -> None:
    document = create_application(settings).openapi()
    coverage = build_coverage(document)
    operations = cast(list[dict[str, object]], coverage["operations"])
    assert coverage["operation_count"] == 247
    assert coverage["classified_count"] == 247
    assert len({item["operation_id"] for item in operations}) == 247
    for item in operations:
        assert item["test_ids"]
        assert item["personas"]
        dimensions = cast(list[str], item["security_dimensions"])
        assert {"declared_response_schema", "error_envelope", "status_code"} <= set(dimensions)
        if item["authentication_level"] != "public":
            assert {"unauthenticated", "suspended_user"} <= set(dimensions)
        if item["authentication_level"] == "workspace":
            assert {"forbidden", "cross_tenant", "acl_denial"} <= set(dimensions)


def _login(client: TestClient, username: str, password: str) -> None:
    response = client.post("/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text


def _tenant_headers(
    client: TestClient, settings: Settings, organization_id: UUID, workspace_id: UUID
) -> dict[str, str]:
    csrf = client.cookies.get(settings.AUTH_CSRF_COOKIE_NAME)
    assert csrf
    return {
        settings.TENANCY_ORGANIZATION_HEADER: str(organization_id),
        settings.TENANCY_WORKSPACE_HEADER: str(workspace_id),
        settings.AUTH_CSRF_HEADER_NAME: csrf,
        "Origin": settings.CORS_ALLOWED_ORIGINS[0],
    }


def _assert_safe_contract_response(
    response: Any, path: str, method: str, operation: dict[str, Any]
) -> None:
    assert response.status_code < 500, f"{method.upper()} {path}: {response.text[:200]}"
    if response.status_code >= 400 and response.headers.get("content-type", "").startswith(
        "application/json"
    ):
        payload = response.json()
        if "error" in payload:
            assert payload["error"].get("code")
            assert payload["error"].get("message")
    if 200 <= response.status_code < 300:
        responses = operation.get("responses", {})
        assert str(response.status_code) in responses or "default" in responses


@pytest.mark.integration
def test_authenticated_personas_exercise_every_protected_operation(settings: Settings) -> None:
    """Use real cookie sessions and real tenant memberships for the surface sweep.

    Domain integration files in the generated map provide happy-path resources.
    This test guarantees the operation-wide layer reaches authenticated tenancy
    and authorization dependencies instead of stopping at anonymous rejection.
    """
    personas = asyncio.run(_seed_contract_personas(settings))
    app = create_application(settings)
    document = app.openapi()
    coverage = build_coverage(document)
    scopes = {
        str(item["operation_id"]): str(item["authentication_level"])
        for item in cast(list[dict[str, object]], coverage["operations"])
    }
    operations = [
        (path, method, operation)
        for path, method, operation in _operations(document)
        if not path.startswith("/auth/")
        and path != "/api/v1/events/stream"
        and scopes[operation["operationId"]] != "public"
    ]
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            _login(client, personas.usernames["admin"], personas.password)
            headers = _tenant_headers(
                client,
                settings,
                personas.organizations["alpha"],
                personas.workspaces["alpha"],
            )
            for path, method, operation in operations:
                response = client.request(
                    method.upper(),
                    _path_for(path, operation),
                    headers=headers,
                    json={} if method in {"post", "put", "patch"} else None,
                    follow_redirects=False,
                )
                assert response.status_code != 401
                _assert_safe_contract_response(response, path, method, operation)

        with TestClient(app, raise_server_exceptions=False) as client:
            _login(client, personas.usernames["restricted"], personas.password)
            headers = _tenant_headers(
                client,
                settings,
                personas.organizations["alpha"],
                personas.workspaces["alpha"],
            )
            restricted_denials = 0
            for path, method, operation in operations:
                if scopes[operation["operationId"]] != "workspace":
                    continue
                response = client.request(
                    method.upper(),
                    _path_for(path, operation),
                    headers=headers,
                    json={} if method in {"post", "put", "patch"} else None,
                    follow_redirects=False,
                )
                assert response.status_code != 401
                restricted_denials += response.status_code == 403
                _assert_safe_contract_response(response, path, method, operation)
            assert restricted_denials > 0

        with TestClient(app, raise_server_exceptions=False) as client:
            _login(client, personas.usernames["cross"], personas.password)
            manipulated_headers = _tenant_headers(
                client,
                settings,
                personas.organizations["alpha"],
                personas.workspaces["alpha"],
            )
            for path, method, operation in operations:
                if scopes[operation["operationId"]] != "workspace":
                    continue
                response = client.request(
                    method.upper(),
                    _path_for(path, operation),
                    headers=manipulated_headers,
                    json={} if method in {"post", "put", "patch"} else None,
                    follow_redirects=False,
                )
                if response.status_code < 300:
                    # Tenant-neutral discovery endpoints may return the caller's
                    # own Beta resources, but a forged Alpha header must never
                    # disclose Alpha's organization or workspace identifiers.
                    assert str(personas.organizations["alpha"]) not in response.text
                    assert str(personas.workspaces["alpha"]) not in response.text
                elif "{" in path:
                    assert response.status_code in {403, 404, 422}
                _assert_safe_contract_response(response, path, method, operation)

        with TestClient(app, raise_server_exceptions=False) as client:
            suspended = client.post(
                "/auth/login",
                json={
                    "username": personas.usernames["suspended"],
                    "password": personas.password,
                },
            )
            assert suspended.status_code in {401, 403}
            assert settings.AUTH_ACCESS_COOKIE_NAME not in suspended.cookies
    finally:
        asyncio.run(_cleanup_contract_personas(settings, personas))
