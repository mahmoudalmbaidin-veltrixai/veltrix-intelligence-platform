"""Typed environment configuration for the API process."""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from typing import Annotated, Any, Literal

from pydantic import BeforeValidator, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class AppEnvironment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


def _split_csv(value: Any) -> Any:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return value


CsvList = Annotated[list[str], NoDecode, BeforeValidator(_split_csv)]


class Settings(BaseSettings):
    """Settings loaded from process environment and an optional local .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    APP_NAME: str = "VIP API"
    APP_ENV: AppEnvironment = AppEnvironment.DEVELOPMENT
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    SERVICE_NAME: str = "vip-api"
    ENABLE_DOCS: bool | None = None

    API_V1_PREFIX: str = "/api/v1"

    DATABASE_URL: SecretStr
    DATABASE_POOL_SIZE: int = Field(default=10, ge=1)
    DATABASE_MAX_OVERFLOW: int = Field(default=20, ge=0)
    DATABASE_POOL_TIMEOUT: float = Field(default=30, gt=0)
    DATABASE_CONNECT_TIMEOUT: float = Field(default=5, gt=0)
    DATABASE_ECHO: bool = False

    REDIS_URL: SecretStr
    REDIS_SOCKET_TIMEOUT: float = Field(default=5, gt=0)

    CORS_ALLOWED_ORIGINS: CsvList = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:3009"]
    )
    CORS_ALLOW_CREDENTIALS: bool = False
    TRUSTED_HOSTS: CsvList = Field(default_factory=lambda: ["*"])

    BUILD_COMMIT_SHA: str | None = None
    BUILD_TIMESTAMP: str | None = None
    METRICS_ENABLED: bool = True
    METRICS_BEARER_TOKEN: SecretStr | None = None

    AUTH_ACCESS_SESSION_TTL_MINUTES: int = Field(default=15, ge=1, le=1440)
    AUTH_REFRESH_SESSION_TTL_DAYS: int = Field(default=14, ge=1, le=90)
    AUTH_SESSION_IDLE_TTL_MINUTES: int = Field(default=60, ge=1, le=10080)
    AUTH_MAX_ACTIVE_SESSIONS_PER_USER: int = Field(default=10, ge=1, le=100)
    AUTH_COOKIE_SECURE: bool = False
    AUTH_COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"
    AUTH_COOKIE_DOMAIN: str | None = None
    AUTH_ACCESS_COOKIE_NAME: str = "vip_access_session"
    AUTH_REFRESH_COOKIE_NAME: str = "vip_refresh_session"
    AUTH_CSRF_COOKIE_NAME: str = "vip_csrf_token"
    AUTH_CSRF_HEADER_NAME: str = "X-CSRF-Token"
    AUTH_MAX_FAILED_LOGIN_ATTEMPTS: int = Field(default=5, ge=2, le=50)
    AUTH_LOCKOUT_MINUTES: int = Field(default=15, ge=1, le=1440)
    AUTH_LOGIN_RATE_LIMIT_PER_MINUTE: int = Field(default=10, ge=1, le=1000)
    PASSWORD_MIN_LENGTH: int = Field(default=12, ge=8, le=128)
    PASSWORD_MAX_LENGTH: int = Field(default=256, ge=64, le=1024)
    PASSWORD_RESET_TOKEN_TTL_MINUTES: int = Field(default=30, ge=5, le=1440)
    FRONTEND_URL: str = "http://localhost:3009"
    CSRF_TRUSTED_ORIGINS: CsvList = Field(default_factory=lambda: ["http://localhost:3009"])

    TENANCY_ORGANIZATION_HEADER: str = "X-Organization-ID"
    TENANCY_WORKSPACE_HEADER: str = "X-Workspace-ID"
    TENANCY_REQUIRE_WORKSPACE_BY_DEFAULT: bool = False
    TENANCY_DEFAULT_WORKSPACE_NAME: str = Field(default="Default", min_length=1, max_length=200)
    TENANCY_AUDIT_ENABLED: bool = True
    TENANCY_CACHE_PREFIX: str = Field(default="vip", min_length=1, max_length=50)
    INVITATION_TOKEN_TTL_HOURS: int = Field(default=72, ge=1, le=720)
    INVITATION_TOKEN_BYTES: int = Field(default=32, ge=24, le=128)
    INVITATION_ACCEPT_URL: str = "http://localhost:3009/invitations/accept"

    AUTHORIZATION_CACHE_ENABLED: bool = False
    AUTHORIZATION_CACHE_TTL_SECONDS: int = Field(default=60, ge=1, le=3600)
    FEATURE_FLAGS_CACHE_TTL_SECONDS: int = Field(default=60, ge=1, le=3600)
    ENTITLEMENTS_CACHE_TTL_SECONDS: int = Field(default=60, ge=1, le=3600)
    QUOTA_CACHE_TTL_SECONDS: int = Field(default=30, ge=1, le=3600)
    AUDIT_EVENTS_ENABLED: bool = True
    AUDIT_DENIED_ACCESS: bool = True
    AUDIT_RETENTION_DAYS: int = Field(default=365, ge=30, le=3650)
    GOVERNANCE_FAIL_CLOSED: bool = True

    CONNECTION_SECRET_PROVIDER: Literal["database_encrypted"] = "database_encrypted"  # noqa: S105
    CONNECTION_ENCRYPTION_KEY: SecretStr | None = None
    CONNECTION_ENCRYPTION_KEY_VERSION: str = Field(default="v1", min_length=1, max_length=40)
    CONNECTION_TEST_TIMEOUT_SECONDS: float = Field(default=15, ge=1, le=60)
    CONNECTION_TEST_MAX_REDIRECTS: int = Field(default=2, ge=0, le=5)
    CONNECTION_TEST_RATE_LIMIT_PER_MINUTE: int = Field(default=10, ge=1, le=100)
    CONNECTION_ALLOW_PRIVATE_NETWORKS: bool = False
    CONNECTION_ALLOW_HTTP: bool = False
    CONNECTION_BLOCK_CLOUD_METADATA: bool = True
    CONNECTION_MAX_CONFIGURATION_BYTES: int = Field(default=32768, ge=1024, le=262144)
    CONNECTION_MAX_SECRET_BYTES: int = Field(default=16384, ge=256, le=65536)

    METADATA_DISCOVERY_TIMEOUT_SECONDS: float = Field(default=30, ge=1, le=120)
    METADATA_DISCOVERY_MAX_OBJECTS: int = Field(default=500, ge=1, le=5000)
    METADATA_DISCOVERY_MAX_FIELDS_PER_OBJECT: int = Field(default=500, ge=1, le=5000)
    LINEAGE_MAX_DEPTH: int = Field(default=5, ge=1, le=20)
    LINEAGE_MAX_NODES: int = Field(default=250, ge=1, le=2000)
    SEMANTIC_QUERY_DEFAULT_LIMIT: int = Field(default=100, ge=1, le=1000)
    SEMANTIC_QUERY_MAX_LIMIT: int = Field(default=1000, ge=1, le=10000)
    SEMANTIC_QUERY_MAX_OFFSET: int = Field(default=10000, ge=0, le=1000000)
    SEMANTIC_QUERY_MAX_DIMENSIONS: int = Field(default=10, ge=1, le=50)
    SEMANTIC_QUERY_MAX_METRICS: int = Field(default=20, ge=1, le=100)
    SEMANTIC_QUERY_MAX_FILTERS: int = Field(default=25, ge=0, le=100)
    SEMANTIC_QUERY_MAX_ORDER_FIELDS: int = Field(default=10, ge=0, le=50)
    SEMANTIC_QUERY_MAX_IN_VALUES: int = Field(default=500, ge=1, le=5000)
    SEMANTIC_QUERY_TIMEOUT_SECONDS: float = Field(default=30, ge=1, le=120)
    SEMANTIC_QUERY_MAX_RESULT_BYTES: int = Field(default=5242880, ge=1024, le=52428800)
    DASHBOARD_MAX_PAGES: int = Field(default=50, ge=1, le=200)
    DASHBOARD_MAX_WIDGETS: int = Field(default=250, ge=1, le=1000)
    DASHBOARD_MAX_WIDGETS_PER_PAGE: int = Field(default=100, ge=1, le=500)
    DASHBOARD_MAX_FILTERS: int = Field(default=50, ge=0, le=200)
    DASHBOARD_MAX_EDITOR_PAYLOAD_BYTES: int = Field(default=2097152, ge=65536, le=10485760)
    DASHBOARD_MAX_VERSION_SNAPSHOT_BYTES: int = Field(default=5242880, ge=65536, le=52428800)
    DASHBOARD_QUERY_MAX_CONCURRENT_WIDGETS: int = Field(default=8, ge=1, le=32)
    DASHBOARD_QUERY_TIMEOUT_SECONDS: float = Field(default=30, ge=1, le=120)
    DASHBOARD_QUERY_CACHE_ENABLED: bool = False
    DASHBOARD_QUERY_CACHE_TTL_SECONDS: int = Field(default=60, ge=0, le=3600)
    DASHBOARD_QUERY_MAX_RESULT_BYTES: int = Field(default=5242880, ge=1024, le=52428800)
    DASHBOARD_SNAPSHOT_MAX_BYTES: int = Field(default=20971520, ge=65536, le=104857600)
    DASHBOARD_SNAPSHOT_RETENTION_DAYS: int = Field(default=30, ge=1, le=3650)
    DASHBOARD_EXPORT_MAX_ATTEMPTS: int = Field(default=3, ge=1, le=10)
    DASHBOARD_EXPORT_MAX_ARTIFACT_BYTES: int = Field(default=52428800, ge=65536, le=524288000)
    DASHBOARD_EXPORT_RETENTION_HOURS: int = Field(default=24, ge=1, le=720)
    DASHBOARD_EXPORT_WORKER_POLL_SECONDS: float = Field(default=1.0, ge=0.1, le=60)
    DASHBOARD_EXPORT_LEASE_SECONDS: int = Field(default=120, ge=10, le=3600)
    DASHBOARD_ARTIFACT_ROOT: str = "/data/vip-artifacts"
    DASHBOARD_DOWNLOAD_TOKEN_TTL_SECONDS: int = Field(default=300, ge=30, le=3600)
    DASHBOARD_DOWNLOAD_SIGNING_KEY: SecretStr | None = None
    DASHBOARD_EMAIL_PROVIDER: Literal["disabled", "file", "smtp"] = "disabled"
    DASHBOARD_EMAIL_OUTBOX_ROOT: str = "/data/vip-email-outbox"
    DASHBOARD_EMAIL_FROM: str = "no-reply@vip.local"
    DASHBOARD_SMTP_HOST: str | None = None
    DASHBOARD_SMTP_PORT: int = Field(default=587, ge=1, le=65535)
    DASHBOARD_SMTP_USERNAME: str | None = None
    DASHBOARD_SMTP_PASSWORD: SecretStr | None = None
    DASHBOARD_SMTP_STARTTLS: bool = True
    DASHBOARD_SMTP_USE_TLS: bool = False
    DASHBOARD_SMTP_TIMEOUT_SECONDS: float = Field(default=30, ge=1, le=120)
    PIPELINE_MAX_NODES: int = Field(default=250, ge=1, le=1000)
    PIPELINE_MAX_EDGES: int = Field(default=1000, ge=0, le=5000)
    PIPELINE_RUN_MAX_ATTEMPTS: int = Field(default=3, ge=1, le=10)
    PIPELINE_RUN_MAX_ROWS: int = Field(default=100000, ge=1, le=1000000)
    PIPELINE_RUN_MAX_RESULT_BYTES: int = Field(default=52428800, ge=65536, le=536870912)
    PIPELINE_RUN_TIMEOUT_SECONDS: int = Field(default=900, ge=10, le=86400)
    PIPELINE_WORKER_POLL_SECONDS: float = Field(default=1.0, ge=0.1, le=60)
    PIPELINE_WORKER_LEASE_SECONDS: int = Field(default=120, ge=10, le=3600)
    PIPELINE_ARTIFACT_ROOT: str = "/data/vip-pipeline-artifacts"
    PIPELINE_ARTIFACT_RETENTION_HOURS: int = Field(default=24, ge=1, le=720)
    PIPELINE_DOWNLOAD_TOKEN_TTL_SECONDS: int = Field(default=300, ge=30, le=3600)
    PIPELINE_DOWNLOAD_SIGNING_KEY: SecretStr | None = None

    JOB_QUEUE_PREFIX: str = Field(default="vip:jobs", min_length=3, max_length=80)
    JOB_DEFAULT_QUEUE: str = Field(default="default", min_length=1, max_length=80)
    JOB_WORKER_QUEUES: CsvList = Field(default_factory=lambda: ["default", "dashboard"])
    JOB_WORKER_CONCURRENCY: int = Field(default=4, ge=1, le=64)
    JOB_WORKER_POLL_SECONDS: float = Field(default=1.0, ge=0.1, le=30)
    JOB_LEASE_SECONDS: int = Field(default=120, ge=10, le=3600)
    JOB_HEARTBEAT_SECONDS: int = Field(default=15, ge=2, le=300)
    JOB_DEFAULT_TIMEOUT_SECONDS: int = Field(default=900, ge=5, le=86400)
    JOB_MAX_PAYLOAD_BYTES: int = Field(default=1048576, ge=1024, le=16777216)
    JOB_MAX_RESULT_BYTES: int = Field(default=10485760, ge=1024, le=104857600)
    JOB_EVENT_STREAM_MAXLEN: int = Field(default=10000, ge=100, le=1000000)
    JOB_EVENT_HEARTBEAT_SECONDS: int = Field(default=15, ge=2, le=60)
    EVENTS_SUBSCRIPTION_RATE_LIMIT_PER_MINUTE: int = Field(default=30, ge=1, le=1000)

    FILE_STORAGE_PROVIDER: str = Field(default="local", pattern=r"^[a-z][a-z0-9_-]{0,31}$")
    FILE_STORAGE_ROOT: str = "/data/vip-files"
    FILE_MAX_UPLOAD_BYTES: int = Field(default=104857600, ge=1024, le=5368709120)
    FILE_ALLOWED_MIME_TYPES: CsvList = Field(
        default_factory=lambda: [
            "application/json",
            "application/pdf",
            "image/png",
            "image/jpeg",
            "text/csv",
            "text/plain",
        ]
    )
    FILE_ALLOWED_EXTENSIONS: CsvList = Field(
        default_factory=lambda: [".csv", ".json", ".pdf", ".png", ".jpg", ".jpeg", ".txt"]
    )
    FILE_DOWNLOAD_TOKEN_TTL_SECONDS: int = Field(default=300, ge=30, le=3600)
    FILE_DOWNLOAD_SIGNING_KEY: SecretStr | None = None
    FILE_STREAM_CHUNK_BYTES: int = Field(default=1048576, ge=65536, le=8388608)
    FILE_RETENTION_DAYS: int = Field(default=365, ge=1, le=3650)
    FILE_MALWARE_SCANNER: Literal["noop", "clamav", "defender"] = "noop"
    CLAMAV_HOST: str = "clamav"
    CLAMAV_PORT: int = Field(default=3310, ge=1, le=65535)
    FILE_SCAN_TIMEOUT_SECONDS: float = Field(default=30, ge=1, le=300)
    DEFENDER_COMMAND: str = "MpCmdRun.exe"
    FILE_UPLOAD_RATE_LIMIT_PER_MINUTE: int = Field(default=30, ge=1, le=10000)
    FILE_DOWNLOAD_RATE_LIMIT_PER_MINUTE: int = Field(default=120, ge=1, le=10000)

    @model_validator(mode="after")
    def validate_security_defaults(self) -> Settings:
        self.LOG_LEVEL = self.LOG_LEVEL.upper()
        if self.LOG_LEVEL not in {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}:
            raise ValueError("LOG_LEVEL must be a standard Python logging level")
        if not self.API_V1_PREFIX.startswith("/"):
            raise ValueError("API_V1_PREFIX must start with '/'")
        if not self.database_url.startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL must use the postgresql+asyncpg scheme")
        if not self.redis_url.startswith(("redis://", "rediss://")):
            raise ValueError("REDIS_URL must use the redis or rediss scheme")
        if self.APP_ENV is AppEnvironment.PRODUCTION:
            if self.DEBUG:
                raise ValueError("DEBUG must be false in production")
            if not self.GOVERNANCE_FAIL_CLOSED:
                raise ValueError("GOVERNANCE_FAIL_CLOSED must be true in production")
            if not self.AUDIT_EVENTS_ENABLED or not self.AUDIT_DENIED_ACCESS:
                raise ValueError(
                    "Governance audit events and denied-access auditing are required in production"
                )
            if "*" in self.CORS_ALLOWED_ORIGINS:
                raise ValueError("Wildcard CORS origins are forbidden in production")
            if "*" in self.TRUSTED_HOSTS:
                raise ValueError("TRUSTED_HOSTS must be explicit in production")
            if not self.AUTH_COOKIE_SECURE:
                raise ValueError("AUTH_COOKIE_SECURE must be true in production")
            if self.CONNECTION_ENCRYPTION_KEY is None:
                raise ValueError("CONNECTION_ENCRYPTION_KEY is required in production")
            if self.DASHBOARD_DOWNLOAD_SIGNING_KEY is None:
                raise ValueError("DASHBOARD_DOWNLOAD_SIGNING_KEY is required in production")
            if self.PIPELINE_DOWNLOAD_SIGNING_KEY is None:
                raise ValueError("PIPELINE_DOWNLOAD_SIGNING_KEY is required in production")
            if self.FILE_MALWARE_SCANNER == "noop":
                raise ValueError("A production malware scanner must be configured")
            if self.FILE_DOWNLOAD_SIGNING_KEY is None:
                raise ValueError("FILE_DOWNLOAD_SIGNING_KEY is required in production")
            if self.DASHBOARD_EMAIL_PROVIDER != "smtp":
                raise ValueError("SMTP dashboard delivery is required in production")
            if self.METRICS_ENABLED and self.METRICS_BEARER_TOKEN is None:
                raise ValueError("METRICS_BEARER_TOKEN is required when metrics are enabled")
        if self.AUTH_COOKIE_SAMESITE == "none" and not self.AUTH_COOKIE_SECURE:
            raise ValueError("SameSite=None cookies must be secure")
        if self.PASSWORD_MIN_LENGTH > self.PASSWORD_MAX_LENGTH:
            raise ValueError("PASSWORD_MIN_LENGTH cannot exceed PASSWORD_MAX_LENGTH")
        if self.SEMANTIC_QUERY_DEFAULT_LIMIT > self.SEMANTIC_QUERY_MAX_LIMIT:
            raise ValueError("SEMANTIC_QUERY_DEFAULT_LIMIT cannot exceed SEMANTIC_QUERY_MAX_LIMIT")
        if self.DASHBOARD_EMAIL_PROVIDER == "smtp":
            if not self.DASHBOARD_SMTP_HOST:
                raise ValueError("DASHBOARD_SMTP_HOST is required for SMTP delivery")
            if "@" not in self.DASHBOARD_EMAIL_FROM:
                raise ValueError("DASHBOARD_EMAIL_FROM must be a valid sender address")
            if self.DASHBOARD_SMTP_STARTTLS and self.DASHBOARD_SMTP_USE_TLS:
                raise ValueError("SMTP STARTTLS and implicit TLS cannot both be enabled")
            if bool(self.DASHBOARD_SMTP_USERNAME) != bool(self.DASHBOARD_SMTP_PASSWORD):
                raise ValueError("SMTP username and password must be configured together")
        if "*" in self.CSRF_TRUSTED_ORIGINS:
            raise ValueError("Wildcard CSRF trusted origins are forbidden")
        for header_name in (self.TENANCY_ORGANIZATION_HEADER, self.TENANCY_WORKSPACE_HEADER):
            if not header_name.lower().startswith("x-") or any(
                char.isspace() for char in header_name
            ):
                raise ValueError("Tenancy header names must be private X- headers without spaces")
        return self

    @property
    def connection_encryption_key(self) -> str | None:
        return (
            self.CONNECTION_ENCRYPTION_KEY.get_secret_value()
            if self.CONNECTION_ENCRYPTION_KEY is not None
            else None
        )

    @property
    def docs_enabled(self) -> bool:
        if self.ENABLE_DOCS is not None:
            return self.ENABLE_DOCS
        return self.APP_ENV in {AppEnvironment.DEVELOPMENT, AppEnvironment.TEST}

    @property
    def database_url(self) -> str:
        return self.DATABASE_URL.get_secret_value()

    @property
    def redis_url(self) -> str:
        return self.REDIS_URL.get_secret_value()

    @property
    def metrics_bearer_token(self) -> str | None:
        return (
            self.METRICS_BEARER_TOKEN.get_secret_value()
            if self.METRICS_BEARER_TOKEN is not None
            else None
        )

    @property
    def dashboard_download_signing_key(self) -> str:
        if self.DASHBOARD_DOWNLOAD_SIGNING_KEY is None:
            raise RuntimeError("Dashboard download signing is not configured")
        return self.DASHBOARD_DOWNLOAD_SIGNING_KEY.get_secret_value()

    @property
    def pipeline_download_signing_key(self) -> str:
        if self.PIPELINE_DOWNLOAD_SIGNING_KEY is None:
            raise RuntimeError("Pipeline download signing is not configured")
        return self.PIPELINE_DOWNLOAD_SIGNING_KEY.get_secret_value()

    @property
    def file_download_signing_key(self) -> str:
        if self.FILE_DOWNLOAD_SIGNING_KEY is None:
            raise RuntimeError("File download signing is not configured")
        return self.FILE_DOWNLOAD_SIGNING_KEY.get_secret_value()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the immutable process-level settings instance."""
    return Settings()
