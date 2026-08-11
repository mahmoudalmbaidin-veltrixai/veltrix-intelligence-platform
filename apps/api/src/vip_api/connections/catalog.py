"""Deterministic, typed, server-authoritative connection-type definitions.

The registry is code-owned and server-authoritative. Each entry carries an honest
``implementation_status`` so the frontend never presents a planned connector as if it
were fully operational. Only ``available`` connectors expose a real configuration and
credential schema and a working test strategy; ``beta`` connectors are functional but
not yet certified; every other status is catalog metadata only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, TypeAdapter

ImplementationStatus = Literal[
    "available",
    "beta",
    "planned",
    "requires_agent",
    "requires_driver",
    "disabled",
]
Deployment = Literal["cloud", "on_prem", "hybrid"]


# --- Configuration / credential schemas for connectors that are actually wired ---


class PostgreSQLConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    host: str = Field(min_length=1, max_length=253, pattern=r"^[A-Za-z0-9._:-]+$")
    port: int = Field(default=5432, ge=1, le=65535)
    database: str = Field(min_length=1, max_length=128, pattern=r"^[^/\\\x00]+$")
    username: str = Field(min_length=1, max_length=128)
    ssl_mode: Literal["disable", "prefer", "require", "verify-ca", "verify-full"] = "require"
    connect_timeout_seconds: int = Field(default=10, ge=1, le=30)


class MySQLConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    host: str = Field(min_length=1, max_length=253, pattern=r"^[A-Za-z0-9._:-]+$")
    port: int = Field(default=3306, ge=1, le=65535)
    database: str = Field(min_length=1, max_length=128, pattern=r"^[^/\\\x00]+$")
    username: str = Field(min_length=1, max_length=128)
    ssl_mode: Literal["disable", "require", "verify-ca", "verify-full"] = "require"
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


class MSSQLConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    host: str = Field(min_length=1, max_length=253, pattern=r"^[A-Za-z0-9._:-]+$")
    port: int = Field(default=1433, ge=1, le=65535)
    database: str = Field(min_length=1, max_length=128, pattern=r"^[^/\\\x00]+$")
    username: str = Field(min_length=1, max_length=128)
    encrypt: Literal[True] = True
    connect_timeout_seconds: int = Field(default=10, ge=1, le=30)


class SnowflakeConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    account: str = Field(min_length=1, max_length=255, pattern=r"^[A-Za-z0-9._-]+$")
    username: str = Field(min_length=1, max_length=255)
    warehouse: str = Field(min_length=1, max_length=255)
    database: str = Field(min_length=1, max_length=255)
    schema_name: str = Field(default="PUBLIC", min_length=1, max_length=255)
    role: str | None = Field(default=None, max_length=255)
    connect_timeout_seconds: int = Field(default=15, ge=1, le=30)


class SnowflakeCredentials(BaseModel):
    model_config = ConfigDict(extra="forbid")
    password: str = Field(min_length=1, max_length=4096)


class BigQueryConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    project_id: str = Field(min_length=1, max_length=255, pattern=r"^[A-Za-z0-9._:-]+$")
    location: str = Field(default="US", min_length=1, max_length=64, pattern=r"^[A-Za-z0-9-]+$")
    dataset: str | None = Field(default=None, max_length=1024)
    connect_timeout_seconds: int = Field(default=15, ge=1, le=30)


class BigQueryCredentials(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # A Google service-account key JSON document, stored write-only + encrypted.
    service_account_json: str = Field(min_length=2, max_length=32768)


class S3Configuration(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    bucket: str = Field(min_length=3, max_length=255, pattern=r"^[a-z0-9.\-]+$")
    region: str = Field(
        default="us-east-1", min_length=1, max_length=64, pattern=r"^[A-Za-z0-9-]+$"
    )
    prefix: str = Field(default="", max_length=1024)
    # Optional S3-compatible endpoint (e.g. MinIO); HTTPS + SSRF validated at test time.
    endpoint_url: AnyHttpUrl | None = None
    connect_timeout_seconds: int = Field(default=15, ge=1, le=30)


class S3Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid")
    access_key_id: str = Field(min_length=1, max_length=512)
    secret_access_key: str = Field(min_length=1, max_length=1024)
    session_token: str | None = Field(default=None, min_length=1, max_length=8192)


@dataclass(frozen=True, slots=True)
class ConnectionTypeDefinition:
    key: str
    name: str
    description: str
    category: str
    subcategory: str
    vendor: str
    implementation_status: ImplementationStatus
    capabilities: tuple[str, ...]
    auth_methods: tuple[str, ...]
    deployment: Deployment
    test_strategy: str
    version: int
    configuration_adapter: TypeAdapter[object] | None
    credentials_adapter: TypeAdapter[object] | None
    configuration_schema: dict[str, object]
    secret_schema: dict[str, object]
    documentation_reference: str | None
    requirements: tuple[str, ...]
    feature_flag: str | None = None
    beta: bool = field(default=False)

    @property
    def enabled(self) -> bool:
        """True only when a real, usable adapter + test strategy exists."""
        return self.implementation_status in ("available", "beta")


def _definition(
    key: str,
    name: str,
    category: str,
    *,
    status: ImplementationStatus = "planned",
    vendor: str = "",
    subcategory: str = "",
    config: type[BaseModel] | None = None,
    secrets: type[BaseModel] | None = None,
    strategy: str = "unsupported",
    capabilities: tuple[str, ...] | None = None,
    auth_methods: tuple[str, ...] = ("username_password",),
    deployment: Deployment = "cloud",
    docs: str | None = None,
    requirements: tuple[str, ...] = (),
    description: str | None = None,
) -> ConnectionTypeDefinition:
    usable = status in ("available", "beta")
    return ConnectionTypeDefinition(
        key=key,
        name=name,
        description=description or f"{name} connector.",
        category=category,
        subcategory=subcategory,
        vendor=vendor or name,
        implementation_status=status,
        capabilities=(
            capabilities if capabilities is not None else (("test", "read") if usable else ())
        ),
        auth_methods=auth_methods,
        deployment=deployment,
        test_strategy=strategy,
        version=1,
        configuration_adapter=TypeAdapter(config) if config else None,
        credentials_adapter=TypeAdapter(secrets) if secrets else None,
        configuration_schema=(
            config.model_json_schema() if config else {"type": "object", "properties": {}}
        ),
        secret_schema=(
            secrets.model_json_schema() if secrets else {"type": "object", "properties": {}}
        ),
        documentation_reference=docs,
        requirements=requirements,
        beta=status == "beta",
    )


# Reusable requirement lines.
_DB_REQ = (
    "Network reachability from VIP to the database host/port (public endpoint, VPN, "
    "private link, or SSH tunnel).",
    "A least-privilege, read-only database user is recommended.",
    "TLS is enforced by default; provide a CA when using verify-ca/verify-full.",
)
_WAREHOUSE_REQ = (
    "A dedicated warehouse/compute resource and a read-only role.",
    "Outbound HTTPS to the vendor endpoint; some vendors require IP allow-listing.",
)
_OBJECT_STORE_REQ = (
    "A bucket/container and read-only credentials (prefer short-lived/role-based).",
    "Restrict the connector to a path prefix; server-side encryption recommended.",
)
_SAAS_OAUTH_REQ = (
    "A registered OAuth application (client id/secret) in the vendor console.",
    "Least-privilege scopes; refresh-token rotation where supported.",
    "Respect vendor API rate limits.",
)
_AGENT_REQ = (
    "On-premise systems require the VIP secure agent (outbound-only tunnel) or a "
    "customer-managed gateway; VIP does not open inbound access to your network.",
)


CONNECTION_TYPES: tuple[ConnectionTypeDefinition, ...] = (
    # ---- Relational databases -------------------------------------------------
    _definition(
        "postgresql",
        "PostgreSQL",
        "database",
        subcategory="relational",
        vendor="PostgreSQL",
        status="available",
        config=PostgreSQLConfiguration,
        secrets=PasswordCredentials,
        strategy="postgresql_ping",
        capabilities=("test", "read", "metadata_discovery", "read_only_analytics"),
        auth_methods=("username_password",),
        deployment="hybrid",
        requirements=_DB_REQ,
        description="Connect to PostgreSQL and Postgres-compatible databases for governed "
        "read-only analytics and schema discovery.",
    ),
    _definition(
        "mysql",
        "MySQL",
        "database",
        subcategory="relational",
        vendor="Oracle",
        status="beta",
        config=MySQLConfiguration,
        secrets=PasswordCredentials,
        strategy="mysql_ping",
        capabilities=("test", "read", "metadata_discovery"),
        auth_methods=("username_password",),
        deployment="hybrid",
        requirements=_DB_REQ,
        description="Connect to MySQL and compatible engines for read-only analytics and "
        "schema discovery. Beta: functional and tested, pending broader certification.",
    ),
    _definition(
        "mariadb",
        "MariaDB",
        "database",
        subcategory="relational",
        vendor="MariaDB",
        status="planned",
        deployment="hybrid",
        requirements=_DB_REQ,
    ),
    _definition(
        "mssql",
        "Microsoft SQL Server",
        "database",
        subcategory="relational",
        vendor="Microsoft",
        status="beta",
        config=MSSQLConfiguration,
        secrets=PasswordCredentials,
        strategy="mssql_ping",
        capabilities=("test", "read"),
        deployment="hybrid",
        auth_methods=("username_password",),
        requirements=_DB_REQ,
        description="Microsoft SQL Server (beta). Encrypted TLS connection with a "
        "least-privilege SQL login; the pytds driver is provisioned in the connector runtime.",
    ),
    _definition(
        "oracle",
        "Oracle Database",
        "database",
        subcategory="relational",
        vendor="Oracle",
        status="requires_driver",
        deployment="hybrid",
        requirements=_DB_REQ,
        description="Oracle Database. Requires the Oracle client libraries.",
    ),
    _definition(
        "db2",
        "IBM Db2",
        "database",
        subcategory="relational",
        vendor="IBM",
        status="requires_driver",
        deployment="hybrid",
        requirements=_DB_REQ,
    ),
    _definition(
        "sqlite",
        "SQLite",
        "database",
        subcategory="embedded",
        vendor="SQLite",
        status="planned",
        deployment="on_prem",
        auth_methods=("none",),
    ),
    _definition(
        "cockroachdb",
        "CockroachDB",
        "database",
        subcategory="distributed_sql",
        vendor="Cockroach Labs",
        status="planned",
        deployment="hybrid",
        requirements=_DB_REQ,
    ),
    _definition(
        "yugabytedb",
        "YugabyteDB",
        "database",
        subcategory="distributed_sql",
        vendor="Yugabyte",
        status="planned",
        deployment="hybrid",
        requirements=_DB_REQ,
    ),
    _definition(
        "singlestore",
        "SingleStore",
        "database",
        subcategory="distributed_sql",
        vendor="SingleStore",
        status="planned",
        deployment="hybrid",
        requirements=_DB_REQ,
    ),
    _definition(
        "tidb",
        "TiDB",
        "database",
        subcategory="distributed_sql",
        vendor="PingCAP",
        status="planned",
        deployment="hybrid",
        requirements=_DB_REQ,
    ),
    _definition(
        "teradata",
        "Teradata",
        "database",
        subcategory="mpp",
        vendor="Teradata",
        status="requires_driver",
        deployment="hybrid",
        requirements=_DB_REQ,
    ),
    _definition(
        "saphana",
        "SAP HANA",
        "database",
        subcategory="in_memory",
        vendor="SAP",
        status="requires_driver",
        deployment="hybrid",
        requirements=_DB_REQ,
    ),
    _definition(
        "vertica",
        "Vertica",
        "database",
        subcategory="mpp",
        vendor="OpenText",
        status="planned",
        deployment="hybrid",
        requirements=_DB_REQ,
    ),
    _definition(
        "mongodb",
        "MongoDB",
        "database",
        subcategory="document",
        vendor="MongoDB",
        status="planned",
        deployment="hybrid",
        requirements=_DB_REQ,
    ),
    # ---- Cloud warehouses / analytical engines --------------------------------
    _definition(
        "snowflake",
        "Snowflake",
        "warehouse",
        subcategory="cloud_dw",
        vendor="Snowflake",
        status="beta",
        config=SnowflakeConfiguration,
        secrets=SnowflakeCredentials,
        strategy="snowflake_ping",
        deployment="cloud",
        auth_methods=("username_password",),
        capabilities=("test", "read"),
        requirements=_WAREHOUSE_REQ,
        description="Snowflake Data Cloud (beta). Username/password auth over the "
        "official Snowflake connector; key-pair and OAuth are planned.",
    ),
    _definition(
        "bigquery",
        "Google BigQuery",
        "warehouse",
        subcategory="cloud_dw",
        vendor="Google",
        status="beta",
        config=BigQueryConfiguration,
        secrets=BigQueryCredentials,
        strategy="bigquery_ping",
        deployment="cloud",
        auth_methods=("service_account",),
        capabilities=("test", "read"),
        requirements=_WAREHOUSE_REQ,
        description="Google BigQuery (beta). Authenticates with a service-account key "
        "JSON (stored write-only, encrypted at rest).",
    ),
    _definition(
        "redshift",
        "Amazon Redshift",
        "warehouse",
        subcategory="cloud_dw",
        vendor="AWS",
        status="planned",
        deployment="cloud",
        auth_methods=("username_password", "iam"),
        requirements=_WAREHOUSE_REQ,
    ),
    _definition(
        "synapse",
        "Azure Synapse Analytics",
        "warehouse",
        subcategory="cloud_dw",
        vendor="Microsoft",
        status="planned",
        deployment="cloud",
        auth_methods=("username_password", "service_principal", "managed_identity"),
        requirements=_WAREHOUSE_REQ,
    ),
    _definition(
        "databricks",
        "Databricks SQL",
        "warehouse",
        subcategory="lakehouse",
        vendor="Databricks",
        status="planned",
        deployment="cloud",
        auth_methods=("personal_access_token", "oauth_m2m", "service_principal"),
        capabilities=("test", "read", "metadata_discovery"),
        requirements=_WAREHOUSE_REQ,
    ),
    _definition(
        "clickhouse",
        "ClickHouse",
        "warehouse",
        subcategory="olap",
        vendor="ClickHouse",
        status="planned",
        deployment="hybrid",
        requirements=_WAREHOUSE_REQ,
    ),
    _definition(
        "trino",
        "Trino",
        "warehouse",
        subcategory="query_engine",
        vendor="Trino",
        status="planned",
        deployment="hybrid",
        requirements=_WAREHOUSE_REQ,
    ),
    _definition(
        "presto",
        "Presto",
        "warehouse",
        subcategory="query_engine",
        vendor="Presto",
        status="planned",
        deployment="hybrid",
        requirements=_WAREHOUSE_REQ,
    ),
    _definition(
        "duckdb",
        "DuckDB",
        "warehouse",
        subcategory="embedded_olap",
        vendor="DuckDB",
        status="planned",
        deployment="on_prem",
        auth_methods=("none",),
    ),
    _definition(
        "druid",
        "Apache Druid",
        "warehouse",
        subcategory="olap",
        vendor="Apache",
        status="planned",
        deployment="hybrid",
        requirements=_WAREHOUSE_REQ,
    ),
    # ---- Data lakes / object storage ------------------------------------------
    _definition(
        "s3",
        "Amazon S3",
        "object_storage",
        subcategory="object_store",
        vendor="AWS",
        status="beta",
        config=S3Configuration,
        secrets=S3Credentials,
        strategy="s3_head",
        deployment="cloud",
        auth_methods=("access_key", "session_token"),
        capabilities=("test", "read"),
        requirements=_OBJECT_STORE_REQ,
        description="Amazon S3 (and S3-compatible) object storage (beta). Access-key or "
        "temporary session-token auth; validates bucket reachability via head-bucket.",
    ),
    _definition(
        "minio",
        "MinIO / S3-compatible",
        "object_storage",
        subcategory="object_store",
        vendor="MinIO",
        status="planned",
        deployment="hybrid",
        auth_methods=("access_key",),
        capabilities=("test", "read", "file_discovery"),
        requirements=_OBJECT_STORE_REQ,
        description="MinIO and any S3-compatible object storage (Cloudflare R2, Wasabi, "
        "DigitalOcean Spaces, Ceph).",
    ),
    _definition(
        "azure_blob",
        "Azure Blob Storage",
        "object_storage",
        subcategory="object_store",
        vendor="Microsoft",
        status="planned",
        deployment="cloud",
        auth_methods=("access_key", "service_principal", "managed_identity"),
        requirements=_OBJECT_STORE_REQ,
    ),
    _definition(
        "adls_gen2",
        "Azure Data Lake Storage Gen2",
        "object_storage",
        subcategory="data_lake",
        vendor="Microsoft",
        status="planned",
        deployment="cloud",
        auth_methods=("service_principal", "managed_identity"),
        requirements=_OBJECT_STORE_REQ,
    ),
    _definition(
        "gcs",
        "Google Cloud Storage",
        "object_storage",
        subcategory="object_store",
        vendor="Google",
        status="planned",
        deployment="cloud",
        auth_methods=("service_account", "workload_identity"),
        requirements=_OBJECT_STORE_REQ,
    ),
    _definition(
        "iceberg",
        "Apache Iceberg",
        "object_storage",
        subcategory="table_format",
        vendor="Apache",
        status="planned",
        deployment="hybrid",
        requirements=_OBJECT_STORE_REQ,
    ),
    _definition(
        "delta_lake",
        "Delta Lake",
        "object_storage",
        subcategory="table_format",
        vendor="Databricks",
        status="planned",
        deployment="hybrid",
        requirements=_OBJECT_STORE_REQ,
    ),
    _definition(
        "hdfs",
        "Hadoop HDFS",
        "object_storage",
        subcategory="data_lake",
        vendor="Apache",
        status="requires_agent",
        deployment="on_prem",
        requirements=_AGENT_REQ,
    ),
    # ---- Files & transfer protocols -------------------------------------------
    _definition(
        "local_file",
        "Local file upload",
        "file",
        subcategory="upload",
        vendor="VIP",
        status="available",
        strategy="none",
        auth_methods=("none",),
        capabilities=("upload", "read", "malware_scan"),
        deployment="cloud",
        description=(
            "Upload CSV/XLSX/JSON files directly from your device. "
            "Validated and malware-scanned server-side. "
            "Dataset registration supports CSV and XLSX (first sheet)."
        ),
        requirements=("No network setup; files are validated, size-limited and scanned.",),
    ),
    _definition(
        "sftp",
        "SFTP",
        "file",
        subcategory="transfer",
        vendor="SSH",
        status="planned",
        deployment="hybrid",
        auth_methods=("password", "private_key"),
        capabilities=("test", "read", "file_discovery"),
        requirements=(
            "Reachable SFTP host; host-key verification is enforced.",
            "A restricted base path; path traversal is blocked.",
        ),
    ),
    _definition(
        "ftps",
        "FTPS",
        "file",
        subcategory="transfer",
        vendor="FTP",
        status="planned",
        deployment="hybrid",
        auth_methods=("password",),
    ),
    _definition(
        "smb",
        "SMB / CIFS",
        "file",
        subcategory="transfer",
        vendor="Microsoft",
        status="requires_agent",
        deployment="on_prem",
        requirements=_AGENT_REQ,
    ),
    _definition(
        "sharepoint",
        "Microsoft SharePoint",
        "file",
        subcategory="content",
        vendor="Microsoft",
        status="planned",
        deployment="cloud",
        auth_methods=("oauth",),
        requirements=_SAAS_OAUTH_REQ,
    ),
    _definition(
        "google_drive",
        "Google Drive",
        "file",
        subcategory="content",
        vendor="Google",
        status="planned",
        deployment="cloud",
        auth_methods=("oauth",),
        requirements=_SAAS_OAUTH_REQ,
    ),
    _definition(
        "onedrive",
        "OneDrive",
        "file",
        subcategory="content",
        vendor="Microsoft",
        status="planned",
        deployment="cloud",
        auth_methods=("oauth",),
        requirements=_SAAS_OAUTH_REQ,
    ),
    _definition(
        "dropbox",
        "Dropbox",
        "file",
        subcategory="content",
        vendor="Dropbox",
        status="planned",
        deployment="cloud",
        auth_methods=("oauth",),
        requirements=_SAAS_OAUTH_REQ,
    ),
    # ---- APIs & integration ---------------------------------------------------
    _definition(
        "rest_api",
        "REST API",
        "api",
        subcategory="http",
        vendor="Generic",
        # Beta per capability matrix 01b (PARTIAL_NON_BLOCKING): market as beta
        # only until customer-validated. SSRF/TLS guards are production-grade.
        status="beta",
        config=RestApiConfiguration,
        secrets=RestApiCredentials,
        strategy="rest_head",
        capabilities=("test", "read"),
        auth_methods=("none", "bearer", "api_key"),
        deployment="cloud",
        requirements=(
            "A reachable HTTPS base URL. TLS verification is enforced.",
            "SSRF protection blocks private/link-local/metadata endpoints.",
        ),
        description="Generic REST/HTTP source with SSRF protection, TLS enforcement and "
        "bearer/API-key auth.",
    ),
    _definition(
        "graphql",
        "GraphQL",
        "api",
        subcategory="http",
        vendor="Generic",
        status="planned",
        deployment="cloud",
        auth_methods=("bearer", "api_key"),
    ),
    _definition(
        "odata",
        "OData",
        "api",
        subcategory="http",
        vendor="Generic",
        status="planned",
        deployment="cloud",
        auth_methods=("basic", "oauth"),
    ),
    _definition(
        "soap",
        "SOAP",
        "api",
        subcategory="http",
        vendor="Generic",
        status="planned",
        deployment="cloud",
        auth_methods=("basic", "ws_security"),
    ),
    _definition(
        "webhook",
        "Webhook source",
        "api",
        subcategory="event",
        vendor="Generic",
        status="planned",
        deployment="cloud",
        auth_methods=("hmac",),
    ),
    # ---- ERP ------------------------------------------------------------------
    _definition(
        "sap_s4hana",
        "SAP S/4HANA",
        "erp",
        subcategory="erp",
        vendor="SAP",
        status="requires_agent",
        deployment="hybrid",
        auth_methods=("oauth", "basic", "certificate"),
        requirements=(*_AGENT_REQ, "OData/API services enabled; or RFC/BAPI via agent."),
        description="SAP S/4HANA via OData/REST or RFC/BAPI. On-premise systems require "
        "the secure agent.",
    ),
    _definition(
        "sap_ecc",
        "SAP ECC",
        "erp",
        subcategory="erp",
        vendor="SAP",
        status="requires_agent",
        deployment="on_prem",
        requirements=_AGENT_REQ,
    ),
    _definition(
        "sap_datasphere",
        "SAP Datasphere",
        "erp",
        subcategory="data_platform",
        vendor="SAP",
        status="planned",
        deployment="cloud",
        auth_methods=("oauth",),
        requirements=_SAAS_OAUTH_REQ,
    ),
    _definition(
        "oracle_fusion_erp",
        "Oracle Fusion Cloud ERP",
        "erp",
        subcategory="erp",
        vendor="Oracle",
        status="planned",
        deployment="cloud",
        auth_methods=("oauth", "basic"),
        requirements=_SAAS_OAUTH_REQ,
    ),
    _definition(
        "netsuite",
        "Oracle NetSuite",
        "erp",
        subcategory="erp",
        vendor="Oracle",
        status="planned",
        deployment="cloud",
        auth_methods=("oauth", "token"),
        requirements=_SAAS_OAUTH_REQ,
    ),
    _definition(
        "dynamics365_fo",
        "Dynamics 365 Finance & Operations",
        "erp",
        subcategory="erp",
        vendor="Microsoft",
        status="planned",
        deployment="cloud",
        auth_methods=("oauth", "service_principal"),
        requirements=_SAAS_OAUTH_REQ,
    ),
    _definition(
        "dynamics365_bc",
        "Dynamics 365 Business Central",
        "erp",
        subcategory="erp",
        vendor="Microsoft",
        status="planned",
        deployment="cloud",
        auth_methods=("oauth",),
        requirements=_SAAS_OAUTH_REQ,
    ),
    _definition(
        "odoo",
        "Odoo",
        "erp",
        subcategory="erp",
        vendor="Odoo",
        status="planned",
        deployment="hybrid",
        auth_methods=("api_key", "username_password"),
    ),
    _definition(
        "infor",
        "Infor CloudSuite",
        "erp",
        subcategory="erp",
        vendor="Infor",
        status="planned",
        deployment="cloud",
        auth_methods=("oauth",),
        requirements=_SAAS_OAUTH_REQ,
    ),
    _definition(
        "sage_intacct",
        "Sage Intacct",
        "erp",
        subcategory="finance",
        vendor="Sage",
        status="planned",
        deployment="cloud",
        auth_methods=("oauth", "token"),
    ),
    _definition(
        "workday",
        "Workday",
        "erp",
        subcategory="hcm_fin",
        vendor="Workday",
        status="planned",
        deployment="cloud",
        auth_methods=("oauth",),
        requirements=_SAAS_OAUTH_REQ,
    ),
    # ---- CRM & customer platforms ---------------------------------------------
    _definition(
        "salesforce",
        "Salesforce",
        "crm",
        subcategory="crm",
        vendor="Salesforce",
        status="planned",
        deployment="cloud",
        auth_methods=("oauth", "username_password"),
        capabilities=("test", "read", "object_discovery"),
        requirements=_SAAS_OAUTH_REQ,
        description="Salesforce CRM. Discovers sObjects and fields; incremental extraction.",
    ),
    _definition(
        "dynamics365_sales",
        "Dynamics 365 Sales",
        "crm",
        subcategory="crm",
        vendor="Microsoft",
        status="planned",
        deployment="cloud",
        auth_methods=("oauth",),
        requirements=_SAAS_OAUTH_REQ,
    ),
    _definition(
        "hubspot",
        "HubSpot",
        "crm",
        subcategory="crm",
        vendor="HubSpot",
        status="planned",
        deployment="cloud",
        auth_methods=("oauth", "api_key"),
        requirements=_SAAS_OAUTH_REQ,
    ),
    _definition(
        "zoho_crm",
        "Zoho CRM",
        "crm",
        subcategory="crm",
        vendor="Zoho",
        status="planned",
        deployment="cloud",
        auth_methods=("oauth",),
        requirements=_SAAS_OAUTH_REQ,
    ),
    _definition(
        "pipedrive",
        "Pipedrive",
        "crm",
        subcategory="crm",
        vendor="Pipedrive",
        status="planned",
        deployment="cloud",
        auth_methods=("api_key", "oauth"),
    ),
    # ---- Marketing / advertising / e-commerce ---------------------------------
    _definition(
        "ga4",
        "Google Analytics 4",
        "marketing",
        subcategory="analytics",
        vendor="Google",
        status="planned",
        deployment="cloud",
        auth_methods=("oauth",),
        requirements=_SAAS_OAUTH_REQ,
    ),
    _definition(
        "google_ads",
        "Google Ads",
        "marketing",
        subcategory="advertising",
        vendor="Google",
        status="planned",
        deployment="cloud",
        auth_methods=("oauth",),
        requirements=_SAAS_OAUTH_REQ,
    ),
    _definition(
        "meta_ads",
        "Meta Ads",
        "marketing",
        subcategory="advertising",
        vendor="Meta",
        status="planned",
        deployment="cloud",
        auth_methods=("oauth",),
        requirements=_SAAS_OAUTH_REQ,
    ),
    _definition(
        "linkedin_ads",
        "LinkedIn Ads",
        "marketing",
        subcategory="advertising",
        vendor="LinkedIn",
        status="planned",
        deployment="cloud",
        auth_methods=("oauth",),
        requirements=_SAAS_OAUTH_REQ,
    ),
    _definition(
        "shopify",
        "Shopify",
        "marketing",
        subcategory="ecommerce",
        vendor="Shopify",
        status="planned",
        deployment="cloud",
        auth_methods=("oauth", "api_key"),
        requirements=_SAAS_OAUTH_REQ,
    ),
    _definition(
        "stripe",
        "Stripe",
        "marketing",
        subcategory="payments",
        vendor="Stripe",
        status="planned",
        deployment="cloud",
        auth_methods=("api_key",),
        requirements=("A restricted (read-only) Stripe API key.",),
    ),
    _definition(
        "klaviyo",
        "Klaviyo",
        "marketing",
        subcategory="email",
        vendor="Klaviyo",
        status="planned",
        deployment="cloud",
        auth_methods=("api_key",),
    ),
    # ---- Streaming / messaging ------------------------------------------------
    _definition(
        "kafka",
        "Apache Kafka",
        "streaming",
        subcategory="event_stream",
        vendor="Apache",
        status="planned",
        deployment="hybrid",
        auth_methods=("sasl_plain", "sasl_scram", "mtls"),
        capabilities=("test", "topic_discovery", "batch_read"),
        requirements=(
            "Reachable brokers; SASL/mTLS credentials.",
            "Optional schema-registry URL and credentials.",
        ),
    ),
    _definition(
        "confluent",
        "Confluent Cloud",
        "streaming",
        subcategory="event_stream",
        vendor="Confluent",
        status="planned",
        deployment="cloud",
        auth_methods=("api_key",),
        requirements=_SAAS_OAUTH_REQ,
    ),
    _definition(
        "event_hubs",
        "Azure Event Hubs",
        "streaming",
        subcategory="event_stream",
        vendor="Microsoft",
        status="planned",
        deployment="cloud",
        auth_methods=("connection_string", "managed_identity"),
    ),
    _definition(
        "pubsub",
        "Google Pub/Sub",
        "streaming",
        subcategory="event_stream",
        vendor="Google",
        status="planned",
        deployment="cloud",
        auth_methods=("service_account",),
    ),
    _definition(
        "kinesis",
        "Amazon Kinesis",
        "streaming",
        subcategory="event_stream",
        vendor="AWS",
        status="planned",
        deployment="cloud",
        auth_methods=("access_key", "role_arn"),
    ),
    _definition(
        "rabbitmq",
        "RabbitMQ",
        "streaming",
        subcategory="message_queue",
        vendor="Broadcom",
        status="planned",
        deployment="hybrid",
        auth_methods=("username_password",),
    ),
    # ---- BI & analytics platforms ---------------------------------------------
    _definition(
        "powerbi",
        "Microsoft Power BI",
        "bi",
        subcategory="bi",
        vendor="Microsoft",
        status="planned",
        deployment="cloud",
        auth_methods=("oauth", "service_principal"),
        capabilities=("metadata_discovery", "refresh_trigger"),
        requirements=_SAAS_OAUTH_REQ,
        description="Power BI metadata: workspaces, datasets and reports; refresh triggers. "
        "Not a raw-data extraction source.",
    ),
    _definition(
        "tableau",
        "Tableau",
        "bi",
        subcategory="bi",
        vendor="Salesforce",
        status="planned",
        deployment="hybrid",
        auth_methods=("personal_access_token",),
        capabilities=("metadata_discovery",),
    ),
    _definition(
        "looker",
        "Looker",
        "bi",
        subcategory="bi",
        vendor="Google",
        status="planned",
        deployment="cloud",
        auth_methods=("api_key",),
        capabilities=("metadata_discovery",),
    ),
    _definition(
        "thoughtspot",
        "ThoughtSpot",
        "bi",
        subcategory="bi",
        vendor="ThoughtSpot",
        status="planned",
        deployment="cloud",
        auth_methods=("oauth", "api_key"),
    ),
    # ---- Collaboration & business apps ----------------------------------------
    _definition(
        "jira",
        "Jira",
        "collaboration",
        subcategory="itsm",
        vendor="Atlassian",
        status="planned",
        deployment="cloud",
        auth_methods=("oauth", "api_token"),
        capabilities=("test", "read", "object_discovery"),
        requirements=_SAAS_OAUTH_REQ,
        description="Jira issues, projects, users, worklogs and sprints.",
    ),
    _definition(
        "confluence",
        "Confluence",
        "collaboration",
        subcategory="content",
        vendor="Atlassian",
        status="planned",
        deployment="cloud",
        auth_methods=("oauth", "api_token"),
    ),
    _definition(
        "servicenow",
        "ServiceNow",
        "collaboration",
        subcategory="itsm",
        vendor="ServiceNow",
        status="planned",
        deployment="cloud",
        auth_methods=("oauth", "basic"),
        requirements=_SAAS_OAUTH_REQ,
        description="ServiceNow incidents, requests, changes and CMDB tables.",
    ),
    _definition(
        "zendesk",
        "Zendesk",
        "collaboration",
        subcategory="support",
        vendor="Zendesk",
        status="planned",
        deployment="cloud",
        auth_methods=("oauth", "api_token"),
    ),
    _definition(
        "github",
        "GitHub",
        "collaboration",
        subcategory="devops",
        vendor="GitHub",
        status="planned",
        deployment="cloud",
        auth_methods=("oauth", "pat"),
        capabilities=("test", "read", "object_discovery"),
        description="GitHub repositories, issues, pull requests and Actions.",
    ),
    _definition(
        "gitlab",
        "GitLab",
        "collaboration",
        subcategory="devops",
        vendor="GitLab",
        status="planned",
        deployment="hybrid",
        auth_methods=("oauth", "pat"),
    ),
    _definition(
        "slack",
        "Slack",
        "collaboration",
        subcategory="messaging",
        vendor="Salesforce",
        status="planned",
        deployment="cloud",
        auth_methods=("oauth",),
        requirements=_SAAS_OAUTH_REQ,
    ),
    _definition(
        "notion",
        "Notion",
        "collaboration",
        subcategory="content",
        vendor="Notion",
        status="planned",
        deployment="cloud",
        auth_methods=("oauth", "api_token"),
    ),
    # ---- HR / finance / identity ----------------------------------------------
    _definition(
        "successfactors",
        "SAP SuccessFactors",
        "hr_finance",
        subcategory="hcm",
        vendor="SAP",
        status="planned",
        deployment="cloud",
        auth_methods=("oauth",),
        requirements=_SAAS_OAUTH_REQ,
    ),
    _definition(
        "bamboohr",
        "BambooHR",
        "hr_finance",
        subcategory="hcm",
        vendor="BambooHR",
        status="planned",
        deployment="cloud",
        auth_methods=("api_key",),
    ),
    _definition(
        "quickbooks",
        "QuickBooks Online",
        "hr_finance",
        subcategory="accounting",
        vendor="Intuit",
        status="planned",
        deployment="cloud",
        auth_methods=("oauth",),
        requirements=_SAAS_OAUTH_REQ,
    ),
    _definition(
        "xero",
        "Xero",
        "hr_finance",
        subcategory="accounting",
        vendor="Xero",
        status="planned",
        deployment="cloud",
        auth_methods=("oauth",),
        requirements=_SAAS_OAUTH_REQ,
    ),
    _definition(
        "okta",
        "Okta",
        "hr_finance",
        subcategory="identity",
        vendor="Okta",
        status="planned",
        deployment="cloud",
        auth_methods=("api_token", "oauth"),
    ),
    _definition(
        "entra_id",
        "Microsoft Entra ID",
        "hr_finance",
        subcategory="identity",
        vendor="Microsoft",
        status="planned",
        deployment="cloud",
        auth_methods=("oauth", "service_principal"),
    ),
    # ---- Observability & infrastructure ---------------------------------------
    _definition(
        "elasticsearch",
        "Elasticsearch",
        "observability",
        subcategory="search",
        vendor="Elastic",
        status="planned",
        deployment="hybrid",
        auth_methods=("api_key", "basic"),
        capabilities=("test", "read", "index_discovery"),
    ),
    _definition(
        "opensearch",
        "OpenSearch",
        "observability",
        subcategory="search",
        vendor="OpenSearch",
        status="planned",
        deployment="hybrid",
        auth_methods=("basic", "api_key"),
    ),
    _definition(
        "splunk",
        "Splunk",
        "observability",
        subcategory="logs",
        vendor="Splunk",
        status="planned",
        deployment="hybrid",
        auth_methods=("token", "basic"),
    ),
    _definition(
        "datadog",
        "Datadog",
        "observability",
        subcategory="metrics",
        vendor="Datadog",
        status="planned",
        deployment="cloud",
        auth_methods=("api_key",),
    ),
    _definition(
        "prometheus",
        "Prometheus",
        "observability",
        subcategory="metrics",
        vendor="Prometheus",
        status="planned",
        deployment="hybrid",
        auth_methods=("none", "basic"),
    ),
    _definition(
        "snowplow",
        "InfluxDB",
        "observability",
        subcategory="timeseries",
        vendor="InfluxData",
        status="planned",
        deployment="hybrid",
        auth_methods=("token",),
        description="InfluxDB time-series database.",
    ),
    # ---- Email (operational) --------------------------------------------------
    _definition(
        "smtp",
        "SMTP",
        "email",
        subcategory="delivery",
        vendor="SMTP",
        status="planned",
        deployment="hybrid",
        auth_methods=("username_password",),
        description="Outbound SMTP for operational delivery (managed separately by the "
        "delivery subsystem).",
    ),
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
    return {str(key): str(item) for key, item in result.items()}
