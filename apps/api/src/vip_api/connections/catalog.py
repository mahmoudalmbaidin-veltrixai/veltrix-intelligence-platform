"""Deterministic, typed, server-authoritative connection-type definitions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, TypeAdapter


class PostgreSQLConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    host: str = Field(min_length=1, max_length=253, pattern=r"^[A-Za-z0-9._:-]+$")
    port: int = Field(default=5432, ge=1, le=65535)
    database: str = Field(min_length=1, max_length=128, pattern=r"^[^/\\\x00]+$")
    username: str = Field(min_length=1, max_length=128)
    ssl_mode: Literal["disable", "prefer", "require", "verify-ca", "verify-full"] = "require"
    connect_timeout_seconds: int = Field(default=10, ge=1, le=30)


class PasswordCredentials(BaseModel):
    model_config = ConfigDict(extra="forbid")
    password: str = Field(min_length=1, max_length=4096)


class RestApiConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    base_url: AnyHttpUrl
    auth_type: Literal["none", "bearer", "api_key"] = "none"
    health_path: str = Field(default="/", pattern=r"^/[^\r\n]*$", max_length=500)
    timeout_seconds: int = Field(default=15, ge=1, le=30)
    verify_tls: Literal[True] = True
    api_key_header: Literal["X-API-Key", "Api-Key"] = "X-API-Key"


class RestApiCredentials(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str | None = Field(default=None, min_length=1, max_length=8192)
    api_key: str | None = Field(default=None, min_length=1, max_length=8192)


@dataclass(frozen=True, slots=True)
class ConnectionTypeDefinition:
    key: str
    name: str
    description: str
    category: str
    capabilities: tuple[str, ...]
    test_strategy: str
    enabled: bool
    version: int
    configuration_adapter: TypeAdapter[object] | None
    credentials_adapter: TypeAdapter[object] | None
    configuration_schema: dict[str, object]
    secret_schema: dict[str, object]


def _definition(
    key: str,
    name: str,
    category: str,
    *,
    enabled: bool = False,
    config: type[BaseModel] | None = None,
    secrets: type[BaseModel] | None = None,
    strategy: str = "unsupported",
    capabilities: tuple[str, ...] | None = None,
) -> ConnectionTypeDefinition:
    return ConnectionTypeDefinition(
        key=key,
        name=name,
        description=f"{name} connection",
        category=category,
        capabilities=capabilities
        if capabilities is not None
        else (("test", "read") if enabled else ()),
        test_strategy=strategy,
        enabled=enabled,
        version=1,
        configuration_adapter=TypeAdapter(config) if config else None,
        credentials_adapter=TypeAdapter(secrets) if secrets else None,
        configuration_schema=config.model_json_schema()
        if config
        else {"type": "object", "properties": {}},
        secret_schema=secrets.model_json_schema()
        if secrets
        else {"type": "object", "properties": {}},
    )


CONNECTION_TYPES: tuple[ConnectionTypeDefinition, ...] = (
    _definition(
        "postgresql",
        "PostgreSQL",
        "database",
        enabled=True,
        config=PostgreSQLConfiguration,
        secrets=PasswordCredentials,
        strategy="postgresql_ping",
        capabilities=("test", "read", "metadata_discovery", "read_only_analytics"),
    ),
    _definition(
        "rest_api",
        "REST API",
        "api",
        enabled=True,
        config=RestApiConfiguration,
        secrets=RestApiCredentials,
        strategy="rest_head",
    ),
    _definition("mysql", "MySQL", "database"),
    _definition("mssql", "Microsoft SQL Server", "database"),
    _definition("oracle", "Oracle", "database"),
    _definition("snowflake", "Snowflake", "warehouse"),
    _definition("bigquery", "BigQuery", "warehouse"),
    _definition("redshift", "Amazon Redshift", "warehouse"),
    _definition("mongodb", "MongoDB", "database"),
    _definition("sftp", "SFTP", "file"),
    _definition("smtp", "SMTP", "email"),
)
CONNECTION_TYPE_BY_KEY = {item.key: item for item in CONNECTION_TYPES}


def validate_configuration(type_key: str, value: dict[str, object]) -> dict[str, object]:
    definition = CONNECTION_TYPE_BY_KEY.get(type_key)
    if definition is None or definition.configuration_adapter is None:
        raise ValueError("Unknown or unsupported connection type")
    model = definition.configuration_adapter.validate_python(value)
    assert isinstance(model, BaseModel)
    return model.model_dump(mode="json")


def validate_credentials(type_key: str, value: dict[str, object]) -> dict[str, str | None]:
    definition = CONNECTION_TYPE_BY_KEY.get(type_key)
    if definition is None or definition.credentials_adapter is None:
        raise ValueError("Unknown or unsupported connection type")
    model = definition.credentials_adapter.validate_python(value)
    assert isinstance(model, BaseModel)
    result = model.model_dump(mode="json", exclude_none=True)
    if type_key == "rest_api":
        # Required credential varies with the safe configuration and is checked by service.
        return {str(key): str(item) for key, item in result.items()}
    return {str(key): str(item) for key, item in result.items()}
