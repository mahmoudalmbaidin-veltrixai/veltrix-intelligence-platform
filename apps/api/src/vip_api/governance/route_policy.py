"""Runtime route-policy inventory used by automated coverage tests."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.routing import APIRoute

from vip_api.governance.dependencies import RequireGovernance, get_authorization_context
from vip_api.tenancy.dependencies import get_tenant_context

# Platform super-admin routes intentionally use the stronger, cross-tenant
# `require_platform_admin` gate instead of per-tenant governance. Their protection
# is asserted separately in the platform-admin coverage test.
PUBLIC_PREFIXES = ("/health", "/ready", "/auth/", "/api/v1/version", "/api/v1/platform")
SPECIAL_POLICIES = {
    ("GET", "/api/v1/organizations"): "authentication",
    ("POST", "/api/v1/organizations"): "authentication",
    ("POST", "/api/v1/invitations/accept"): "authentication",
    ("GET", "/api/v1/tenant-context"): "tenant",
    ("GET", "/api/v1/authorization/context"): "authorization",
}


def _dependency_calls(dependant: object) -> list[object]:
    calls: list[object] = []
    for dependency in getattr(dependant, "dependencies", []):
        call = getattr(dependency, "call", None)
        if call is not None:
            calls.append(call)
        calls.extend(_dependency_calls(dependency))
    return calls


def missing_governance_policies(app: FastAPI) -> list[str]:
    missing: list[str] = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods or set():
            key = (method, route.path)
            if route.path.startswith(PUBLIC_PREFIXES) or key in SPECIAL_POLICIES:
                continue
            if not route.path.startswith("/api/v1"):
                continue
            calls = _dependency_calls(route.dependant)
            if not any(
                isinstance(call, RequireGovernance)
                or call in {get_tenant_context, get_authorization_context}
                for call in calls
            ):
                missing.append(f"{method} {route.path}")
    return sorted(missing)
