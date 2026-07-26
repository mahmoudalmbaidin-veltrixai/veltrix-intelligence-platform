"""Read-only, bounded PostgreSQL metadata discovery adapters."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from fnmatch import fnmatchcase
from typing import Protocol, cast

import asyncpg  # type: ignore[import-untyped]

from vip_api.connections.network import UnsafeDestinationError, validate_host
from vip_api.core.config import Settings
from vip_api.core.errors import ApplicationError


@dataclass(frozen=True, slots=True)
class DiscoveredField:
    name: str
    ordinal_position: int
    physical_type: str
    normalized_type: str
    nullable: bool
    max_length: int | None
    precision: int | None
    scale: int | None


@dataclass(frozen=True, slots=True)
class DiscoveredObject:
    catalog: str
    schema: str
    name: str
    object_type: str
    estimated_row_count: int | None
    estimated_size_bytes: int | None
    fields: tuple[DiscoveredField, ...]


class MetadataDiscoveryAdapter(Protocol):
    async def discover(
        self,
        configuration: dict[str, object],
        credentials: dict[str, str],
        *,
        catalog: str | None,
        schemas: list[str],
        object_types: list[str],
        include_names: list[str],
        exclude_names: list[str],
    ) -> tuple[list[DiscoveredObject], bool]: ...


def normalize_postgresql_type(value: str) -> str:
    value = value.lower()
    if value in {"smallint", "integer", "bigint"}:
        return "integer"
    if value in {"numeric", "decimal", "real", "double precision", "money"}:
        return "decimal"
    if value in {"boolean"}:
        return "boolean"
    if value == "date":
        return "date"
    if "timestamp" in value:
        return "datetime"
    if value.startswith("time"):
        return "time"
    if value in {"bytea"}:
        return "binary"
    if value in {"json", "jsonb"}:
        return "json"
    if value in {"array"} or value.startswith("_"):
        return "array"
    if value in {"character varying", "character", "text", "uuid", "name", "inet", "citext"}:
        return "string"
    return "unknown"


class PostgreSQLDiscoveryAdapter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def discover(
        self,
        configuration: dict[str, object],
        credentials: dict[str, str],
        *,
        catalog: str | None,
        schemas: list[str],
        object_types: list[str],
        include_names: list[str],
        exclude_names: list[str],
    ) -> tuple[list[DiscoveredObject], bool]:
        host = str(configuration["host"])
        port = cast(int, configuration["port"])
        try:
            await validate_host(host, port, self.settings)
        except UnsafeDestinationError as exc:
            raise ApplicationError(
                code="DISCOVERY_DESTINATION_BLOCKED",
                message="The connection destination is not allowed.",
                status_code=422,
            ) from exc
        connection: asyncpg.Connection[asyncpg.Record] | None = None
        try:
            connection = await asyncio.wait_for(
                asyncpg.connect(
                    host=host,
                    port=port,
                    database=str(configuration["database"]),
                    user=str(configuration["username"]),
                    password=credentials["password"],
                    ssl=str(configuration["ssl_mode"]),
                    command_timeout=self.settings.METADATA_DISCOVERY_TIMEOUT_SECONDS,
                    server_settings={"application_name": "vip-metadata-discovery"},
                ),
                self.settings.METADATA_DISCOVERY_TIMEOUT_SECONDS,
            )
            assert connection is not None
            async with connection.transaction(readonly=True):
                rows = await connection.fetch(
                    """
                    SELECT table_catalog, table_schema, table_name, table_type
                    FROM information_schema.tables
                    WHERE table_schema = ANY($1::text[])
                    ORDER BY table_schema, table_name
                    LIMIT $2
                    """,
                    schemas,
                    self.settings.METADATA_DISCOVERY_MAX_OBJECTS + 1,
                )
                selected = [
                    row
                    for row in rows
                    if self._allowed(
                        row["table_name"],
                        row["table_type"],
                        object_types,
                        include_names,
                        exclude_names,
                    )
                ]
                truncated = len(selected) > self.settings.METADATA_DISCOVERY_MAX_OBJECTS
                selected = selected[: self.settings.METADATA_DISCOVERY_MAX_OBJECTS]
                result: list[DiscoveredObject] = []
                for row in selected:
                    field_rows = await connection.fetch(
                        """
                        SELECT column_name, ordinal_position, data_type, is_nullable,
                               character_maximum_length, numeric_precision, numeric_scale
                        FROM information_schema.columns
                        WHERE table_catalog=$1 AND table_schema=$2 AND table_name=$3
                        ORDER BY ordinal_position LIMIT $4
                        """,
                        row["table_catalog"],
                        row["table_schema"],
                        row["table_name"],
                        self.settings.METADATA_DISCOVERY_MAX_FIELDS_PER_OBJECT,
                    )
                    fields = tuple(
                        DiscoveredField(
                            name=item["column_name"],
                            ordinal_position=item["ordinal_position"],
                            physical_type=item["data_type"],
                            normalized_type=normalize_postgresql_type(item["data_type"]),
                            nullable=item["is_nullable"] == "YES",
                            max_length=item["character_maximum_length"],
                            precision=item["numeric_precision"],
                            scale=item["numeric_scale"],
                        )
                        for item in field_rows
                    )
                    result.append(
                        DiscoveredObject(
                            catalog=catalog or row["table_catalog"],
                            schema=row["table_schema"],
                            name=row["table_name"],
                            object_type="view" if row["table_type"] == "VIEW" else "table",
                            estimated_row_count=None,
                            estimated_size_bytes=None,
                            fields=fields,
                        )
                    )
                return result, truncated
        except TimeoutError as exc:
            raise ApplicationError(
                code="DISCOVERY_TIMEOUT", message="Metadata discovery timed out.", status_code=504
            ) from exc
        except (OSError, asyncpg.PostgresError) as exc:
            raise ApplicationError(
                code="DISCOVERY_FAILED",
                message="Metadata discovery could not be completed.",
                status_code=502,
            ) from exc
        finally:
            if connection is not None:
                await connection.close(timeout=2)

    @staticmethod
    def _allowed(
        name: str,
        table_type: str,
        object_types: list[str],
        includes: list[str],
        excludes: list[str],
    ) -> bool:
        kind = "view" if table_type == "VIEW" else "table"
        return (
            kind in object_types
            and any(fnmatchcase(name, pattern) for pattern in includes)
            and not any(fnmatchcase(name, pattern) for pattern in excludes)
        )


class MetadataDiscoveryAdapterRegistry:
    def __init__(self, settings: Settings) -> None:
        self._adapters: dict[str, MetadataDiscoveryAdapter] = {
            "postgresql": PostgreSQLDiscoveryAdapter(settings)
        }

    def get(self, type_key: str) -> MetadataDiscoveryAdapter:
        try:
            return self._adapters[type_key]
        except KeyError as exc:
            raise ApplicationError(
                code="DISCOVERY_UNSUPPORTED",
                message="Metadata discovery is not supported for this connection type.",
                status_code=422,
            ) from exc

    def replace(self, type_key: str, adapter: MetadataDiscoveryAdapter) -> None:
        self._adapters[type_key] = adapter
