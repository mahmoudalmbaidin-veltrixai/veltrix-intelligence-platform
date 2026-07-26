"""Strict public contracts for dashboard exports and deliveries."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Literal, Self
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from vip_api.dashboards.schemas import Scalar

ExportFormat = Literal["pdf", "png", "json", "csv"]
ScheduleType = Literal["one_time", "daily", "weekly", "monthly", "cron"]
_EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _emails(values: list[str]) -> list[str]:
    normalized = sorted({value.strip().lower() for value in values if value.strip()})
    if any(len(value) > 320 or not _EMAIL.fullmatch(value) for value in normalized):
        raise ValueError("One or more recipient addresses are invalid")
    return normalized


class ExportCreate(StrictModel):
    format: ExportFormat
    filters: dict[str, Scalar | list[Scalar]] = Field(default_factory=dict)
    locale: str = Field(default="en-US", pattern=r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")
    timezone: str = Field(default="UTC", min_length=1, max_length=64)

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Unknown timezone") from exc
        return value


class ExportResponse(BaseModel):
    id: UUID
    dashboard_id: UUID
    dashboard_version_id: UUID
    format: str
    status: str
    progress: int
    attempts: int
    max_attempts: int
    cancellation_requested: bool
    artifact_content_type: str | None
    artifact_size_bytes: int | None
    safe_error_code: str | None
    safe_error_message: str | None
    row_version: int
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    cancelled_at: datetime | None
    expires_at: datetime | None


class ExportMutation(StrictModel):
    expected_version: int = Field(ge=1)


class DownloadTokenResponse(BaseModel):
    url: str
    expires_at: datetime


class ScheduleCreate(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    recipients: list[str] = Field(min_length=1, max_length=100)
    cc: list[str] = Field(default_factory=list, max_length=100)
    bcc: list[str] = Field(default_factory=list, max_length=100)
    subject: str = Field(min_length=1, max_length=300)
    format: Literal["pdf", "png", "csv"]
    filters: dict[str, Scalar | list[Scalar]] = Field(default_factory=dict)
    schedule_type: ScheduleType
    schedule_expression: str | None = Field(default=None, max_length=120)
    run_at: datetime | None = None
    timezone: str = Field(default="UTC", min_length=1, max_length=64)
    include_dashboard_link: bool = True
    enabled: bool = True
    max_retries: int = Field(default=3, ge=0, le=10)

    @field_validator("recipients", "cc", "bcc")
    @classmethod
    def valid_emails(cls, value: list[str]) -> list[str]:
        return _emails(value)

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Unknown timezone") from exc
        return value

    @model_validator(mode="after")
    def schedule_contract(self) -> Self:
        if self.schedule_type == "cron":
            if not self.schedule_expression or len(self.schedule_expression.split()) != 5:
                raise ValueError("Cron schedules require a five-field expression")
        elif self.schedule_expression:
            raise ValueError("schedule_expression is only valid for cron schedules")
        if self.schedule_type == "one_time":
            if self.run_at is None or self.run_at <= datetime.now(UTC):
                raise ValueError("One-time schedules require a future run_at value")
        elif self.run_at is not None:
            raise ValueError("run_at is only valid for one-time schedules")
        if len(set(self.recipients) | set(self.cc) | set(self.bcc)) > 200:
            raise ValueError("Too many unique recipients")
        return self


class ScheduleUpdate(ScheduleCreate):
    expected_version: int = Field(ge=1)


class ScheduleResponse(BaseModel):
    id: UUID
    dashboard_id: UUID
    dashboard_version_id: UUID
    name: str
    recipients: list[str]
    cc: list[str]
    bcc: list[str]
    subject: str
    format: str
    filters: dict[str, object]
    schedule_type: str
    schedule_expression: str | None
    timezone: str
    include_dashboard_link: bool
    enabled: bool
    status: str
    retry_count: int
    max_retries: int
    row_version: int
    created_at: datetime
    updated_at: datetime
    last_run_at: datetime | None
    next_run_at: datetime | None


class DeliveryRunResponse(BaseModel):
    id: UUID
    schedule_id: UUID
    export_id: UUID | None
    status: str
    attempt: int
    safe_error_code: str | None
    safe_error_message: str | None
    created_at: datetime
    sent_at: datetime | None
    completed_at: datetime | None


class EmailPreviewRequest(StrictModel):
    recipients: list[str] = Field(min_length=1, max_length=100)
    cc: list[str] = Field(default_factory=list, max_length=100)
    bcc: list[str] = Field(default_factory=list, max_length=100)
    subject: str = Field(min_length=1, max_length=300)
    include_dashboard_link: bool = True

    @field_validator("recipients", "cc", "bcc")
    @classmethod
    def valid_emails(cls, value: list[str]) -> list[str]:
        return _emails(value)


class EmailPreviewResponse(BaseModel):
    subject: str
    html: str
    recipients: int
    attachments: list[str]
