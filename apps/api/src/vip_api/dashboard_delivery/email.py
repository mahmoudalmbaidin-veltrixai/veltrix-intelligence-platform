"""Provider-backed dashboard email composition and delivery."""

from __future__ import annotations

import asyncio
import html
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import make_msgid
from hashlib import sha256
from pathlib import Path
from typing import Protocol
from uuid import UUID

from vip_api.core.config import Settings
from vip_api.core.errors import ApplicationError


@dataclass(frozen=True, slots=True)
class EmailAttachment:
    filename: str
    content_type: str
    content: bytes


@dataclass(frozen=True, slots=True)
class DashboardEmail:
    recipients: list[str]
    cc: list[str]
    bcc: list[str]
    subject: str
    html: str
    attachments: list[EmailAttachment]


class EmailProvider(Protocol):
    async def send(self, message: DashboardEmail, delivery_id: UUID) -> str: ...


def render_email_html(
    dashboard_name: str,
    dashboard_version: int,
    generated_at: str,
    dashboard_url: str | None,
) -> str:
    safe_name = html.escape(dashboard_name)
    link = (
        f'<p><a href="{html.escape(dashboard_url, quote=True)}">Open dashboard</a></p>'
        if dashboard_url
        else ""
    )
    return (
        '<!doctype html><html><body style="font-family:Arial,sans-serif;color:#172033">'
        f"<h1>{safe_name}</h1><p>Published dashboard version {dashboard_version}</p>"
        f"<p>Generated {html.escape(generated_at)}</p>{link}"
        "<p>Sent securely by Veltrix One.</p></body></html>"
    )


class FileEmailProvider:
    """Safe local provider that writes RFC-compliant messages to a protected outbox."""

    def __init__(self, settings: Settings) -> None:
        self.root = Path(settings.DASHBOARD_EMAIL_OUTBOX_ROOT).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.sender = settings.DASHBOARD_EMAIL_FROM

    async def send(self, message: DashboardEmail, delivery_id: UUID) -> str:
        email = _compose_message(message, self.sender, delivery_id)
        content = email.as_bytes()
        target = (self.root / f"{delivery_id}.eml").resolve()
        if self.root not in target.parents:
            raise ApplicationError(
                code="DASHBOARD_EMAIL_FAILED",
                message="The dashboard email could not be delivered.",
                status_code=503,
            )
        await asyncio.to_thread(target.write_bytes, content)
        return sha256(content).hexdigest()[:32]


class SmtpEmailProvider:
    """Authenticated SMTP transport with TLS, bounded timeouts and safe errors."""

    def __init__(self, settings: Settings) -> None:
        if settings.DASHBOARD_SMTP_HOST is None:
            raise ValueError("SMTP host is required")
        self.host = settings.DASHBOARD_SMTP_HOST
        self.port = settings.DASHBOARD_SMTP_PORT
        self.username = settings.DASHBOARD_SMTP_USERNAME
        self.password = (
            settings.DASHBOARD_SMTP_PASSWORD.get_secret_value()
            if settings.DASHBOARD_SMTP_PASSWORD is not None
            else None
        )
        self.starttls = settings.DASHBOARD_SMTP_STARTTLS
        self.use_tls = settings.DASHBOARD_SMTP_USE_TLS
        self.timeout = settings.DASHBOARD_SMTP_TIMEOUT_SECONDS
        self.sender = settings.DASHBOARD_EMAIL_FROM

    async def send(self, message: DashboardEmail, delivery_id: UUID) -> str:
        email = _compose_message(message, self.sender, delivery_id)
        recipients = [*message.recipients, *message.cc, *message.bcc]

        def deliver() -> None:
            context = ssl.create_default_context()
            transport = (
                smtplib.SMTP_SSL(
                    self.host,
                    self.port,
                    timeout=self.timeout,
                    context=context,
                )
                if self.use_tls
                else smtplib.SMTP(self.host, self.port, timeout=self.timeout)
            )
            with transport as smtp:
                if self.starttls:
                    smtp.starttls(context=context)
                if self.username is not None and self.password is not None:
                    smtp.login(self.username, self.password)
                smtp.send_message(email, from_addr=self.sender, to_addrs=recipients)

        try:
            await asyncio.to_thread(deliver)
        except (OSError, smtplib.SMTPException) as exc:
            raise ApplicationError(
                code="DASHBOARD_EMAIL_FAILED",
                message="The dashboard email could not be delivered.",
                status_code=503,
            ) from exc
        return str(email["Message-ID"]).strip("<>")


def _compose_message(
    message: DashboardEmail,
    sender: str,
    delivery_id: UUID,
) -> EmailMessage:
    email = EmailMessage()
    email["Message-ID"] = make_msgid(idstring=str(delivery_id), domain="vip.local")
    email["From"] = sender
    email["To"] = ", ".join(message.recipients)
    if message.cc:
        email["Cc"] = ", ".join(message.cc)
    email["Subject"] = message.subject
    email.set_content("This dashboard delivery requires an HTML-capable email client.")
    email.add_alternative(message.html, subtype="html")
    for attachment in message.attachments:
        maintype, subtype = attachment.content_type.split("/", 1)
        email.add_attachment(
            attachment.content,
            maintype=maintype,
            subtype=subtype,
            filename=attachment.filename,
        )
    return email


def get_email_provider(settings: Settings) -> EmailProvider:
    if settings.DASHBOARD_EMAIL_PROVIDER == "file":
        return FileEmailProvider(settings)
    if settings.DASHBOARD_EMAIL_PROVIDER == "smtp":
        return SmtpEmailProvider(settings)
    raise ApplicationError(
        code="DASHBOARD_EMAIL_PROVIDER_UNAVAILABLE",
        message="Dashboard email delivery is unavailable.",
        status_code=503,
    )
