"""Password-recovery email composition, reusing the platform email transport.

Delivery is best-effort from the caller's perspective: a transport failure must
never change the (deliberately non-disclosing) API response. Locally the ``file``
provider writes the message to the protected outbox for UAT.
"""

from __future__ import annotations

import html
import logging
from uuid import uuid4

from vip_api.core.config import Settings
from vip_api.dashboard_delivery.email import DashboardEmail, get_email_provider

logger = logging.getLogger(__name__)


def _reset_email_html(reset_url: str) -> str:
    safe = html.escape(reset_url, quote=True)
    return (
        '<!doctype html><html><body style="font-family:Arial,sans-serif;color:#172033">'
        "<h1>Reset your Veltrix password</h1>"
        "<p>We received a request to reset your password. This link is valid for a "
        "limited time and can be used once.</p>"
        f'<p><a href="{safe}">Reset your password</a></p>'
        "<p>If you did not request this, you can safely ignore this email.</p>"
        "<p>Veltrix One</p></body></html>"
    )


async def send_password_reset_email(settings: Settings, recipient: str, reset_url: str) -> None:
    """Send the reset link; swallow transport errors (response stays uniform)."""
    try:
        provider = get_email_provider(settings)
        message = DashboardEmail(
            recipients=[recipient],
            cc=[],
            bcc=[],
            subject="Reset your Veltrix password",
            html=_reset_email_html(reset_url),
            attachments=[],
        )
        await provider.send(message, uuid4())
    except Exception:
        # Delivery is best-effort: never let a transport error change the
        # (deliberately non-disclosing) response or leak account state.
        logger.warning(
            "Password-reset email could not be delivered",
            extra={"security_event": "password_reset_email_failed"},
        )
