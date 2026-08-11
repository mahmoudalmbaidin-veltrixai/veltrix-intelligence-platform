"""Request identity and structured access logging middleware."""

from __future__ import annotations

import json
import logging
import re
import time
from typing import ClassVar
from uuid import UUID, uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from vip_api.core.context import bind_request_context, reset_request_context
from vip_api.core.metrics import metrics

logger = logging.getLogger("vip_api.request")
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def _safe_incoming_id(value: str | None) -> str:
    if value and _SAFE_ID.fullmatch(value):
        return value
    return str(uuid4())


class RequestContextMiddleware:
    """Bind request identifiers, add response headers, and emit one access log."""

    def __init__(self, app: ASGIApp, *, organization_header: str, workspace_header: str) -> None:
        self.app = app
        self.organization_header = organization_header.lower().encode("ascii")
        self.workspace_header = workspace_header.lower().encode("ascii")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        raw_headers = [(key.lower(), value) for key, value in scope.get("headers", [])]
        headers = {key: value for key, value in raw_headers}
        incoming = headers.get(b"x-correlation-id")
        correlation_id = _safe_incoming_id(
            incoming.decode("ascii", errors="ignore") if incoming else None
        )
        request_id = str(uuid4())
        tokens = bind_request_context(correlation_id, request_id)
        started = time.perf_counter()
        metrics.request_started()
        status_code = 500
        response_started = False

        invalid_tenant_headers = False
        for header_name in (self.organization_header, self.workspace_header):
            values = [value for key, value in raw_headers if key == header_name]
            if len(values) > 1:
                invalid_tenant_headers = True
                break
            if values:
                try:
                    UUID(values[0].decode("ascii"))
                except (UnicodeDecodeError, ValueError):
                    invalid_tenant_headers = True
                    break

        async def send_with_context(message: Message) -> None:
            nonlocal response_started, status_code
            if message["type"] == "http.response.start":
                response_started = True
                status_code = message["status"]
                response_headers = list(message.get("headers", []))
                response_headers.extend(
                    [
                        (b"x-correlation-id", correlation_id.encode("ascii")),
                        (b"x-request-id", request_id.encode("ascii")),
                    ]
                )
                message["headers"] = response_headers
            await send(message)

        try:
            if invalid_tenant_headers:
                status_code = 400
                body = json.dumps(
                    {
                        "error": {
                            "code": "INVALID_TENANT_CONTEXT",
                            "message": "The tenant context is invalid.",
                            "correlation_id": correlation_id,
                        }
                    },
                    separators=(",", ":"),
                ).encode()
                await send_with_context(
                    {
                        "type": "http.response.start",
                        "status": 400,
                        "headers": [
                            (b"content-type", b"application/json"),
                            (b"content-length", str(len(body)).encode()),
                        ],
                    }
                )
                await send_with_context({"type": "http.response.body", "body": body})
            else:
                await self.app(scope, receive, send_with_context)
        except Exception:
            logger.exception(
                "Unhandled exception escaped the application",
                extra={"http_method": scope["method"], "http_path": scope["path"]},
            )
            # Streaming responses (notably SSE) may fail after headers were
            # committed. ASGI forbids starting a second response at that point;
            # close the stream and let the standards-compliant client reconnect.
            if response_started:
                return
            body = json.dumps(
                {
                    "error": {
                        "code": "INTERNAL_SERVER_ERROR",
                        "message": "An unexpected error occurred.",
                        "correlation_id": correlation_id,
                    }
                },
                separators=(",", ":"),
            ).encode()
            await send(
                {
                    "type": "http.response.start",
                    "status": 500,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"content-length", str(len(body)).encode()),
                        (b"x-correlation-id", correlation_id.encode()),
                        (b"x-request-id", request_id.encode()),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body})
        finally:
            duration_seconds = time.perf_counter() - started
            duration_ms = round(duration_seconds * 1000, 3)
            metrics.request_finished(scope["method"], status_code, duration_seconds)
            if scope["path"].endswith("/auth/login") and status_code in {401, 423}:
                metrics.authentication_failed()
            log_level = logging.ERROR if status_code >= 500 else logging.INFO
            if scope["path"] not in {"/health", "/ready"} or status_code >= 400:
                logger.log(
                    log_level,
                    "HTTP request completed",
                    extra={
                        "http_method": scope["method"],
                        "http_path": scope["path"],
                        "status_code": status_code,
                        "duration_ms": duration_ms,
                    },
                )
            reset_request_context(tokens)


class SecurityHeadersMiddleware:
    """Adds a coherent, environment-aware set of browser/API security headers to
    every HTTP response (VIP-BUG-005).

    - Static hardening headers apply to all responses.
    - A strict Content-Security-Policy applies to API/JSON responses; the docs UI
      paths are exempt so Swagger/ReDoc keep working.
    - HSTS is emitted ONLY in production (never over local HTTP development), so
      it is never falsely asserted on non-HTTPS environments.
    """

    _DOCS_PREFIXES = ("/docs", "/redoc", "/openapi.json")
    _STATIC_HEADERS: ClassVar[dict[str, str]] = {
        "x-content-type-options": "nosniff",
        "x-frame-options": "DENY",
        "referrer-policy": "strict-origin-when-cross-origin",
        "permissions-policy": (
            "camera=(), microphone=(), geolocation=(), payment=(), usb=(), "
            "magnetometer=(), gyroscope=(), accelerometer=()"
        ),
        "cross-origin-opener-policy": "same-origin",
        "cross-origin-resource-policy": "same-origin",
    }
    _API_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
    _HSTS = "max-age=63072000; includeSubDomains; preload"

    def __init__(self, app: ASGIApp, *, is_production: bool) -> None:
        self.app = app
        self.is_production = is_production

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        apply_csp = not any(path.startswith(prefix) for prefix in self._DOCS_PREFIXES)

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                from starlette.datastructures import MutableHeaders

                headers = MutableHeaders(scope=message)
                for name, value in self._STATIC_HEADERS.items():
                    headers[name] = value
                if apply_csp:
                    headers["content-security-policy"] = self._API_CSP
                if self.is_production:
                    headers["strict-transport-security"] = self._HSTS
            await send(message)

        await self.app(scope, receive, send_with_headers)
