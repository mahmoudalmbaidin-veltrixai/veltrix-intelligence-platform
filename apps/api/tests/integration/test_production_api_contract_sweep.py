"""OpenAPI-wide production contract and unauthenticated fail-closed sweep."""

from __future__ import annotations

import asyncio
import json
import os
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select
from starlette.testclient import TestClient

from vip_api.api.operation_coverage import build_coverage
from vip_api.auth.models import User, UserStatus
from vip_api.auth.password import PasswordService
from vip_api.core.config import AppEnvironment, Settings
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
_ANONYMOUS_EXECUTED_OPERATION_IDS: set[str] = set()


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


async def _configure_ai_gates(
    settings: Settings,
    personas: ContractPersonas,
    *,
    flag_enabled: bool,
    entitlement_enabled: bool,
) -> None:
    database = Database(settings)
    try:
        async with database.session_factory() as db:
            feature = await db.scalar(select(FeatureFlag).where(FeatureFlag.key == "ai_studio"))
            entitlement = await db.scalar(select(Entitlement).where(Entitlement.key == "ai_studio"))
            assert feature is not None and entitlement is not None
            await db.execute(
                delete(FeatureFlagOverride).where(
                    FeatureFlagOverride.feature_flag_id == feature.id,
                    FeatureFlagOverride.organization_id == personas.organizations["alpha"],
                )
            )
            await db.execute(
                delete(OrganizationEntitlement).where(
                    OrganizationEntitlement.organization_id == personas.organizations["alpha"],
                    OrganizationEntitlement.entitlement_id == entitlement.id,
                )
            )
            db.add(
                FeatureFlagOverride(
                    feature_flag_id=feature.id,
                    organization_id=personas.organizations["alpha"],
                    workspace_id=personas.workspaces["alpha"],
                    enabled=flag_enabled,
                )
            )
            if entitlement_enabled:
                db.add(
                    OrganizationEntitlement(
                        organization_id=personas.organizations["alpha"],
                        entitlement_id=entitlement.id,
                        status="active",
                        source="test",
                    )
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
    _ANONYMOUS_EXECUTED_OPERATION_IDS.update(
        str(operation["operationId"]) for _, _, operation in operations
    )


@pytest.mark.integration
def test_every_operation_is_classified_for_authenticated_certification(settings: Settings) -> None:
    document = create_application(settings).openapi()
    coverage = build_coverage(document)
    operations = cast(list[dict[str, object]], coverage["operations"])
    assert coverage["operation_count"] == 247
    assert coverage["classified_count"] == 247
    assert coverage["test_mapped_count"] == 247
    assert coverage["executed_count"] == 0
    assert len({item["operation_id"] for item in operations}) == 247
    for item in operations:
        assert item["test_evidence"]
        assert item["personas"]
        dimensions = cast(list[str], item["claimed_dimensions"])
        assert "openapi_contract" in dimensions
        if item["authentication_level"] == "public":
            assert "public_probe" in dimensions
        else:
            assert {"unauthenticated_probe", "authenticated_probe"} <= set(dimensions)
        if item["authentication_level"] == "workspace":
            assert {"restricted_role_probe", "cross_tenant_header_probe"} <= set(dimensions)


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


def _runtime_path(path: str, operation: dict[str, Any]) -> str:
    resolved = _path_for(path, operation)
    if path == "/api/v1/events/stream":
        return f"{resolved}?cursor=invalid-contract-cursor"
    return resolved


def _validate_json_schema(document: dict[str, Any], schema: object, value: object) -> None:
    """Validate the OpenAPI shapes exercised by successful contract probes."""
    if not isinstance(schema, dict):
        return
    reference = schema.get("$ref")
    if isinstance(reference, str):
        _validate_json_schema(document, _resolve_ref(document, reference), value)
        return
    alternatives = schema.get("anyOf") or schema.get("oneOf")
    if isinstance(alternatives, list):
        errors: list[AssertionError] = []
        for alternative in alternatives:
            try:
                _validate_json_schema(document, alternative, value)
                return
            except AssertionError as exc:
                errors.append(exc)
        raise AssertionError(f"response matched no schema alternative: {errors}")
    if value is None and schema.get("nullable") is True:
        return
    expected = schema.get("type")
    if expected == "object" or "properties" in schema:
        assert isinstance(value, dict), f"expected object, got {type(value).__name__}"
        required = schema.get("required", [])
        assert all(key in value for key in required), f"missing required response keys: {required}"
        properties = schema.get("properties", {})
        if isinstance(properties, dict):
            for key, nested in properties.items():
                if key in value:
                    _validate_json_schema(document, nested, value[key])
    elif expected == "array":
        assert isinstance(value, list), f"expected array, got {type(value).__name__}"
        for item in value:
            _validate_json_schema(document, schema.get("items", {}), item)
    elif expected == "string":
        assert isinstance(value, str), f"expected string, got {type(value).__name__}"
    elif expected == "integer":
        assert isinstance(value, int) and not isinstance(value, bool)
    elif expected == "number":
        assert isinstance(value, int | float) and not isinstance(value, bool)
    elif expected == "boolean":
        assert isinstance(value, bool)
    enum = schema.get("enum")
    if isinstance(enum, list):
        assert value in enum, f"response value {value!r} is outside enum"


def _validate_success_schema(
    document: dict[str, Any], operation: dict[str, Any], response: Any
) -> bool:
    if not 200 <= response.status_code < 300 or response.status_code == 204:
        return False
    declaration = operation.get("responses", {}).get(str(response.status_code), {})
    content = declaration.get("content", {}) if isinstance(declaration, dict) else {}
    media = next(
        (
            item
            for key, item in content.items()
            if key == "application/json" or key.endswith("+json")
        ),
        None,
    )
    if not isinstance(media, dict) or "schema" not in media:
        return False
    _validate_json_schema(document, media["schema"], response.json())
    return True


def _new_record(operation_id: str, probes: list[str]) -> dict[str, object]:
    return {
        "operation_id": operation_id,
        "executed_dimensions": ["openapi_contract"],
        "required_probes": probes,
        "observations": {},
        "result": "pending",
    }


def _add_dimension(record: dict[str, object], dimension: str) -> None:
    dimensions = cast(list[str], record["executed_dimensions"])
    if dimension not in dimensions:
        dimensions.append(dimension)


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
    operations = list(_operations(document))
    operation_ids = {str(operation["operationId"]) for _, _, operation in operations}
    assert operation_ids == _ANONYMOUS_EXECUTED_OPERATION_IDS, (
        "Anonymous contract execution evidence is absent. Run the complete contract-sweep "
        "module so classification, anonymous probes, and authenticated probes share one run."
    )
    coverage_by_id = {
        str(item["operation_id"]): item
        for item in cast(list[dict[str, object]], coverage["operations"])
    }
    records = {
        operation["operationId"]: _new_record(
            operation["operationId"],
            cast(list[str], coverage_by_id[operation["operationId"]]["claimed_dimensions"]),
        )
        for _, _, operation in operations
    }
    for path, method, operation in operations:
        record = records[operation["operationId"]]
        scope = scopes[operation["operationId"]]
        _add_dimension(record, "public_probe" if scope == "public" else "unauthenticated_probe")
        if "{" in path:
            _add_dimension(record, "invalid_uuid_probe")
        if method in {"post", "put", "patch"}:
            _add_dimension(record, "empty_payload_probe")
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
                operation_id = operation["operationId"]
                if scopes[operation_id] == "public" or path.startswith("/auth/"):
                    continue
                response = client.request(
                    method.upper(),
                    _runtime_path(path, operation),
                    headers=headers,
                    json={} if method in {"post", "put", "patch"} else None,
                    follow_redirects=False,
                )
                assert response.status_code != 401
                _assert_safe_contract_response(response, path, method, operation)
                record = records[operation_id]
                cast(dict[str, object], record["observations"])["authenticated"] = (
                    response.status_code
                )
                _add_dimension(record, "authenticated_probe")
                if 200 <= response.status_code < 300:
                    _add_dimension(record, "authenticated_success")
                if _validate_success_schema(document, operation, response):
                    _add_dimension(record, "response_schema_validated")

        # Authentication endpoints get isolated sessions so logout/password
        # actions cannot invalidate the remaining operation probes.
        for path, method, operation in operations:
            operation_id = operation["operationId"]
            if scopes[operation_id] == "public" or not path.startswith("/auth/"):
                continue
            with TestClient(app, raise_server_exceptions=False) as client:
                _login(client, personas.usernames["admin"], personas.password)
                headers = _tenant_headers(
                    client,
                    settings,
                    personas.organizations["alpha"],
                    personas.workspaces["alpha"],
                )
                response = client.request(
                    method.upper(),
                    _runtime_path(path, operation),
                    headers=headers,
                    json={} if method in {"post", "put", "patch"} else None,
                    follow_redirects=False,
                )
                _assert_safe_contract_response(response, path, method, operation)
                record = records[operation_id]
                cast(dict[str, object], record["observations"])["authenticated"] = (
                    response.status_code
                )
                _add_dimension(record, "authenticated_probe")
                if 200 <= response.status_code < 300:
                    _add_dimension(record, "authenticated_success")
                if _validate_success_schema(document, operation, response):
                    _add_dimension(record, "response_schema_validated")

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
                operation_id = operation["operationId"]
                if scopes[operation_id] != "workspace":
                    continue
                response = client.request(
                    method.upper(),
                    _runtime_path(path, operation),
                    headers=headers,
                    json={} if method in {"post", "put", "patch"} else None,
                    follow_redirects=False,
                )
                assert response.status_code != 401
                restricted_denials += response.status_code == 403
                _assert_safe_contract_response(response, path, method, operation)
                record = records[operation_id]
                cast(dict[str, object], record["observations"])["restricted"] = response.status_code
                _add_dimension(record, "restricted_role_probe")
                if response.status_code == 403:
                    _add_dimension(record, "forbidden_observed")
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
                operation_id = operation["operationId"]
                if scopes[operation_id] != "workspace":
                    continue
                response = client.request(
                    method.upper(),
                    _runtime_path(path, operation),
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
                record = records[operation_id]
                cast(dict[str, object], record["observations"])["cross_tenant"] = (
                    response.status_code
                )
                _add_dimension(record, "cross_tenant_header_probe")
                _add_dimension(record, "cross_tenant_isolated")

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

        for record in records.values():
            required = set(cast(list[str], record.pop("required_probes")))
            executed = set(cast(list[str], record["executed_dimensions"]))
            assert required <= executed, (
                f"{record['operation_id']} missing executed probes: {sorted(required - executed)}"
            )
            record["result"] = "pass"
        execution = {str(key): value for key, value in records.items()}
        verified = build_coverage(document, execution)
        assert verified["executed_count"] == 247
        assert verified["passed_count"] == 247
        report_path = os.getenv("VIP_API_OPERATION_EVIDENCE_PATH")
        if report_path:
            target = Path(report_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "operation_count": 247,
                        "executed_count": 247,
                        "passed_count": 247,
                        "operations": sorted(
                            records.values(), key=lambda item: str(item["operation_id"])
                        ),
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
    finally:
        asyncio.run(_cleanup_contract_personas(settings, personas))


@pytest.mark.integration
def test_ai_catalog_direct_api_fails_closed_in_live_mode(settings: Settings) -> None:
    personas = asyncio.run(_seed_contract_personas(settings))
    routes = (
        "/api/v1/ai/knowledge",
        "/api/v1/ai/assistants",
        "/api/v1/ai/agents",
        "/api/v1/ai/conversations",
        "/api/v1/ai/agent-runs",
    )
    try:
        for flag_enabled, entitlement_enabled in (
            (False, False),
            (True, False),
            (False, True),
            (True, True),
        ):
            asyncio.run(
                _configure_ai_gates(
                    settings,
                    personas,
                    flag_enabled=flag_enabled,
                    entitlement_enabled=entitlement_enabled,
                )
            )
            live = settings.model_copy(
                update={
                    "APP_ENV": AppEnvironment.PRODUCTION,
                    "AI_CAPABILITIES_PRODUCTION_READY": False,
                    "AI_DEVELOPMENT_MOCK_MODE": False,
                }
            )
            with TestClient(create_application(live), raise_server_exceptions=False) as client:
                _login(client, personas.usernames["admin"], personas.password)
                headers = _tenant_headers(
                    client,
                    live,
                    personas.organizations["alpha"],
                    personas.workspaces["alpha"],
                )
                for route in routes:
                    response = client.get(route, headers=headers)
                    assert response.status_code in {403, 404}
                    error = response.json()["error"]
                    assert error["code"] in {
                        "FEATURE_DISABLED",
                        "ENTITLEMENT_REQUIRED",
                        "AI_CAPABILITY_UNAVAILABLE",
                    }

        # A configuration claim cannot expose an empty production placeholder
        # until the implementation readiness constant is changed with the real
        # capability itself.
        configured_ready = settings.model_copy(
            update={
                "APP_ENV": AppEnvironment.PRODUCTION,
                "AI_CAPABILITIES_PRODUCTION_READY": True,
                "AI_DEVELOPMENT_MOCK_MODE": False,
            }
        )
        with TestClient(
            create_application(configured_ready), raise_server_exceptions=False
        ) as client:
            _login(client, personas.usernames["admin"], personas.password)
            headers = _tenant_headers(
                client,
                configured_ready,
                personas.organizations["alpha"],
                personas.workspaces["alpha"],
            )
            for route in routes:
                response = client.get(route, headers=headers)
                assert response.status_code == 404
                assert response.json()["error"]["code"] == "AI_CAPABILITY_UNAVAILABLE"

        asyncio.run(
            _configure_ai_gates(
                settings,
                personas,
                flag_enabled=True,
                entitlement_enabled=True,
            )
        )
        development_mock = settings.model_copy(
            update={
                "APP_ENV": AppEnvironment.DEVELOPMENT,
                "AI_CAPABILITIES_PRODUCTION_READY": False,
                "AI_DEVELOPMENT_MOCK_MODE": True,
            }
        )
        with TestClient(
            create_application(development_mock), raise_server_exceptions=False
        ) as client:
            _login(client, personas.usernames["admin"], personas.password)
            headers = _tenant_headers(
                client,
                development_mock,
                personas.organizations["alpha"],
                personas.workspaces["alpha"],
            )
            for route in routes:
                response = client.get(route, headers=headers)
                assert response.status_code == 200
                assert response.json() == []
    finally:
        asyncio.run(_cleanup_contract_personas(settings, personas))
