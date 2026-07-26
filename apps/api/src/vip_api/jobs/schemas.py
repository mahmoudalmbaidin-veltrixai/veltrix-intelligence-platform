"""Public schemas for generic jobs."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class JobCreate(BaseModel):
    job_type: str = Field(
        pattern="^(export|pipeline|ai|automation|notification|maintenance|scheduled|system)$"
    )
    handler: str = Field(min_length=1, max_length=160)
    name: str = Field(min_length=1, max_length=240)
    payload: dict[str, object] = Field(default_factory=dict)
    priority: int = Field(default=0, ge=-100, le=100)
    idempotency_key: str = Field(min_length=8, max_length=160)
    max_attempts: int = Field(default=3, ge=1, le=100)
    timeout_seconds: int = Field(default=900, ge=5, le=86400)


class ProgressResponse(BaseModel):
    percent: int
    completed_steps: int
    total_steps: int | None
    stage: str | None
    message: str | None
    estimated_completion_at: datetime | None


class JobResponse(BaseModel):
    id: UUID
    type: str
    name: str
    status: str
    queue: str
    priority: int
    attempt: int
    max_attempts: int
    progress: ProgressResponse
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    cancellation_requested: bool


class JobList(BaseModel):
    items: list[JobResponse]
    next_cursor: datetime | None = None


class JobLogResponse(BaseModel):
    sequence: int
    level: str
    message: str
    created_at: datetime


class DeadLetterResponse(BaseModel):
    id: UUID
    job_id: UUID
    failure_reason: str
    last_error_code: str
    attempt_count: int
    status: str
    created_at: datetime
