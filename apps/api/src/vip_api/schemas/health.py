"""Operational endpoint response schemas."""

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["healthy"] = "healthy"
    service: str
    version: str


class DependencyCheck(BaseModel):
    status: Literal["healthy", "unhealthy"]


class ReadinessChecks(BaseModel):
    database: DependencyCheck
    redis: DependencyCheck


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    checks: ReadinessChecks
