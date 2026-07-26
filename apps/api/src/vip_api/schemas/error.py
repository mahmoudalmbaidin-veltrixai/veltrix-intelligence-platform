"""Reusable public error response schemas."""

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    field: str | None = None
    message: str


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[ErrorDetail] | None = None
    correlation_id: str


class ErrorResponse(BaseModel):
    error: ErrorBody
