"""Authentication request and safe response schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from vip_api.auth.models import User, UserStatus


class LoginRequest(BaseModel):
    # Username is the primary identifier; email is accepted for backward
    # compatibility. At least one must be supplied.
    username: str | None = Field(default=None, min_length=1, max_length=150)
    email: str | None = Field(default=None, min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)

    @model_validator(mode="after")
    def _require_identifier(self) -> LoginRequest:
        if not (self.username or self.email):
            raise ValueError("A username or email is required.")
        return self

    @property
    def identifier(self) -> str:
        return (self.username or self.email or "").strip()


class AuthenticatedUser(BaseModel):
    id: UUID
    username: str
    email: str | None = None
    display_name: str
    status: UserStatus
    is_platform_admin: bool = False

    @classmethod
    def from_user(cls, user: User) -> AuthenticatedUser:
        return cls(
            id=user.id,
            username=user.username,
            email=user.email,
            display_name=user.display_name,
            status=user.status,
            is_platform_admin=user.is_platform_admin,
        )


class SessionInfo(BaseModel):
    expires_at: datetime


class AuthenticationResponse(BaseModel):
    user: AuthenticatedUser
    session: SessionInfo


class LogoutResponse(BaseModel):
    success: bool = True
