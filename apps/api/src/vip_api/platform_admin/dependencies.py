"""Authorization gate for the cross-tenant platform super-admin console.

This is the single, mandatory gate for every platform-scoped endpoint. It is
deliberately independent of the per-organization membership/role model: only a
user with the user-level ``is_platform_admin`` flag may pass. Non-admins receive a
non-disclosing 404 so the console's existence is not advertised to tenants.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from vip_api.auth.dependencies import get_current_user
from vip_api.auth.models import User
from vip_api.core.errors import ApplicationError


async def require_platform_admin(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    if not user.is_platform_admin:
        # Non-disclosing: do not reveal that a platform console exists.
        raise ApplicationError(
            code="RESOURCE_NOT_FOUND",
            message="The requested resource was not found.",
            status_code=404,
        )
    return user
