"""Authentication request and safe response schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from vip_api.auth.models import User, UserStatus


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)


class AuthenticatedUser(BaseModel):
    id: UUID
    email: str
    display_name: str
    status: UserStatus

    @classmethod
    def from_user(cls, user: User) -> AuthenticatedUser:
        return cls(id=user.id, email=user.email, display_name=user.display_name, status=user.status)


class SessionInfo(BaseModel):
    expires_at: datetime


class AuthenticationResponse(BaseModel):
    user: AuthenticatedUser
    session: SessionInfo


class LogoutResponse(BaseModel):
    success: bool = True
