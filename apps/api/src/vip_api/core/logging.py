"""Structured, secret-conscious logging configuration."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from vip_api.core.config import Settings
from vip_api.core.context import (
    actor_user_id_var,
    correlation_id_var,
    organization_id_var,
    organization_membership_id_var,
    request_id_var,
    workspace_id_var,
    workspace_membership_id_var,
)

_STANDARD_FIELDS = set(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}
_SENSITIVE_KEY_PARTS = (
    "authorization",
    "cookie",
    "password",
    "secret",
    "token",
    "api_key",
    "private_key",
    "ciphertext",
    "nonce",
)


def _redact(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            str(key): "[REDACTED]"
            if any(part in str(key).casefold() for part in _SENSITIVE_KEY_PARTS)
            else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_redact(item) for item in value]
    return value


class JsonFormatter(logging.Formatter):
    """Format log records as one JSON object per line."""

    def __init__(self, *, environment: str, service_name: str) -> None:
        super().__init__()
        self.environment = environment
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "environment": self.environment,
            "service": self.service_name,
            "correlation_id": correlation_id_var.get(),
            "request_id": request_id_var.get(),
        }
        tenant_fields = {
            "actor_user_id": actor_user_id_var.get(),
            "organization_id": organization_id_var.get(),
            "workspace_id": workspace_id_var.get(),
            "organization_membership_id": organization_membership_id_var.get(),
            "workspace_membership_id": workspace_membership_id_var.get(),
        }
        payload.update({key: value for key, value in tenant_fields.items() if value is not None})
        for key, value in record.__dict__.items():
            if key not in _STANDARD_FIELDS and not key.startswith("_"):
                payload[key] = (
                    "[REDACTED]"
                    if any(part in key.casefold() for part in _SENSITIVE_KEY_PARTS)
                    else _redact(value)
                )
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, separators=(",", ":"))


def configure_logging(settings: Settings) -> None:
    """Configure application and Uvicorn loggers without duplicate handlers."""
    handler = logging.StreamHandler()
    handler.setFormatter(
        JsonFormatter(environment=settings.APP_ENV.value, service_name=settings.SERVICE_NAME)
    )
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(settings.LOG_LEVEL)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True
    logging.getLogger("uvicorn.access").disabled = True
