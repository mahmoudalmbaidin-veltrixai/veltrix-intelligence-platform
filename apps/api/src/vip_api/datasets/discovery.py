"""Read-only, bounded PostgreSQL and MySQL metadata discovery adapters."""

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


def normalize_mysql_type(value: str) -> str:
    value = value.lower()
    if value in {"tinyint", "smallint", "mediumint", "int", "integer", "bigint", "year"}:
        return "integer"
    if value in {"decimal", "numeric", "float", "double", "real", "dec", "fixed"}:
        return "decimal"
    if value in {"bit", "bool", "boolean"}:
        return "boolean"
    if value == "date":
        return "date"
    if value in {"datetime", "timestamp"}:
        return "datetime"
    if value == "time":
        return "time"
    if value in {"binary", "varbinary", "blob", "tinyblob", "mediumblob", "longblob"}:
        return "binary"
    if value == "json":
        return "json"
    if value in {
        "char",
        "varchar",
        "text",
        "tinytext",
        "mediumtext",
        "longtext",
        "enum",
        "set",
    }:
        return "string"
    return "unknown"


_MYSQL_TABLES_SQL = (
    "SELECT table_catalog, table_schema, table_name, table_type "
    "FROM information_schema.tables "
    "WHERE table_schema IN ({placeholders}) "
    "ORDER BY table_schema, table_name LIMIT %s"
)


class MySQLDiscoveryAdapter:
    """Read-only, bounded MySQL metadata discovery mirroring the PostgreSQL adapter.

    Uses ``information_schema`` (MySQL-compatible), the same object/field caps,
    timeouts, and SSRF host validation. MySQL has no separate schema/catalog, so
    the database name is the schema; analytics (preview/profile/query) remain
    PostgreSQL-only by design (MySQL lacks the ``read_only_analytics`` capability).
    """

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
        try:
            import aiomysql  # type: ignore
        except ImportError as exc:
            raise ApplicationError(
                code="DISCOVERY_DRIVER_UNAVAILABLE",
                message="The MySQL driver is not available for metadata discovery.",
                status_code=422,
            ) from exc
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
        database = str(configuration["database"])
        # MySQL "schema" == database; default to the connection's database.
        effective_schemas = schemas or [database]
        ssl_mode = str(configuration.get("ssl_mode", "require"))
        timeout = self.settings.METADATA_DISCOVERY_TIMEOUT_SECONDS
        pool = None
        try:
            pool = await asyncio.wait_for(
                aiomysql.create_pool(
                    host=host,
                    port=port,
                    db=database,
                    user=str(configuration["username"]),
                    password=credentials["password"],
                    ssl=ssl_mode != "disable",
                    connect_timeout=timeout,
                    minsize=1,
                    maxsize=1,
                    program_name="vip-metadata-discovery",
                ),
                timeout=timeout,
            )
            async with pool.acquire() as connection, connection.cursor() as cursor:
                # Only a fixed count of "%s" placeholders is interpolated; every
                # value (schema names + limit) is passed as a bound parameter.
                placeholders = ",".join(["%s"] * len(effective_schemas))
                tables_query = _MYSQL_TABLES_SQL.format(placeholders=placeholders)
                await asyncio.wait_for(
                    cursor.execute(
                        tables_query,
                        (*effective_schemas, self.settings.METADATA_DISCOVERY_MAX_OBJECTS + 1),
                    ),
                    timeout,
                )
                rows = await cursor.fetchall()
                selected = [
                    row
                    for row in rows
                    if self._allowed(row[2], row[3], object_types, include_names, exclude_names)
                ]
                truncated = len(selected) > self.settings.METADATA_DISCOVERY_MAX_OBJECTS
                selected = selected[: self.settings.METADATA_DISCOVERY_MAX_OBJECTS]
                result: list[DiscoveredObject] = []
                for row in selected:
                    await asyncio.wait_for(
                        cursor.execute(
                            "SELECT column_name, ordinal_position, data_type, is_nullable, "
                            "character_maximum_length, numeric_precision, numeric_scale "
                            "FROM information_schema.columns "
                            "WHERE table_schema=%s AND table_name=%s "
                            "ORDER BY ordinal_position LIMIT %s",
                            (
                                row[1],
                                row[2],
                                self.settings.METADATA_DISCOVERY_MAX_FIELDS_PER_OBJECT,
                            ),
                        ),
                        timeout,
                    )
                    field_rows = await cursor.fetchall()
                    fields = tuple(
                        DiscoveredField(
                            name=str(item[0]),
                            ordinal_position=int(item[1]),
                            physical_type=str(item[2]),
                            normalized_type=normalize_mysql_type(str(item[2])),
                            nullable=item[3] == "YES",
                            max_length=int(item[4]) if item[4] is not None else None,
                            precision=int(item[5]) if item[5] is not None else None,
                            scale=int(item[6]) if item[6] is not None else None,
                        )
                        for item in field_rows
                    )
                    result.append(
                        DiscoveredObject(
                            catalog=catalog or str(row[1]),
                            schema=str(row[1]),
                            name=str(row[2]),
                            object_type="view" if row[3] == "VIEW" else "table",
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
        except (OSError, aiomysql.Error) as exc:
            raise ApplicationError(
                code="DISCOVERY_FAILED",
                message="Metadata discovery could not be completed.",
                status_code=502,
            ) from exc
        finally:
            if pool is not None:
                pool.close()
                await pool.wait_closed()

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
            "postgresql": PostgreSQLDiscoveryAdapter(settings),
            "mysql": MySQLDiscoveryAdapter(settings),
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
