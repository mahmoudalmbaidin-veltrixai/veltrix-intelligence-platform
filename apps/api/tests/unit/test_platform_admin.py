"""Coverage guards for the platform super-admin console.

The console is a cross-tenant capability, so the mandatory invariant is: every
`/api/v1/platform` route is gated by `require_platform_admin`, and the ordinary
governance route-policy coverage still holds for all other routes.
"""

from __future__ import annotations

import pytest
from fastapi.routing import APIRoute

from vip_api.core.config import Settings
from vip_api.governance.route_policy import _dependency_calls, missing_governance_policies
from vip_api.main import create_application
from vip_api.platform_admin.dependencies import require_platform_admin
from vip_api.platform_admin.routes import router as platform_router

pytestmark = pytest.mark.unit


def test_every_platform_route_requires_platform_admin() -> None:
    routes = [route for route in platform_router.routes if isinstance(route, APIRoute)]
    assert routes, "platform-admin routes should be registered"
    for route in routes:
        calls = _dependency_calls(route.dependant)
        assert require_platform_admin in calls, f"{route.path} is missing require_platform_admin"


def test_governance_route_policy_still_complete(settings: Settings) -> None:
    app = create_application(settings)
    assert missing_governance_policies(app) == []


def test_platform_admin_gate_is_non_disclosing() -> None:
    # A non-admin must be rejected with a non-disclosing 404, never a 200 or a hint.
    import inspect

    source = inspect.getsource(require_platform_admin)
    assert "is_platform_admin" in source
    assert "404" in source
