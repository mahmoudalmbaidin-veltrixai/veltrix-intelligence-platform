"""Authentication request and safe response schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID
from zoneinfo import available_timezones

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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
    # Surfaced so the client can route a flagged user into the forced
    # password-change flow. Server-side enforcement is independent of this flag.
    must_change_password: bool = False
    # Personal profile + preferences surfaced for the Settings center. username,
    # email and status remain system/administrator-managed (read-only to self).
    account_type: str = "standard"
    job_title: str | None = None
    department: str | None = None
    phone: str | None = None
    locale: str | None = None
    timezone: str | None = None
    avatar_url: str | None = None
    preferences: dict[str, object] = Field(default_factory=dict)
    created_at: datetime | None = None
    last_login_at: datetime | None = None
    password_changed_at: datetime | None = None

    @classmethod
    def from_user(cls, user: User) -> AuthenticatedUser:
        return cls(
            id=user.id,
            username=user.username,
            email=user.email,
            display_name=user.display_name,
            status=user.status,
            is_platform_admin=user.is_platform_admin,
            must_change_password=user.must_change_password,
            account_type=user.account_type,
            job_title=user.job_title,
            department=user.department,
            phone=user.phone,
            locale=user.locale,
            timezone=user.timezone,
            avatar_url=user.avatar_url,
            preferences=dict(user.preferences or {}),
            created_at=user.created_at,
            last_login_at=user.last_login_at,
            password_changed_at=user.password_changed_at,
        )


class SessionInfo(BaseModel):
    expires_at: datetime
    # Sliding idle deadline (last activity + idle TTL) and the client warning
    # window, so the UI can count down and warn before automatic sign-out.
    idle_expires_at: datetime | None = None
    idle_timeout_minutes: int | None = None
    warning_minutes: int | None = None


class AuthenticationResponse(BaseModel):
    user: AuthenticatedUser
    session: SessionInfo


class LogoutResponse(BaseModel):
    success: bool = True


class PasswordResetRequest(BaseModel):
    # Username or email; the response never reveals which (or whether) it matched.
    identifier: str = Field(min_length=1, max_length=320)


class PasswordResetConfirm(BaseModel):
    token: str = Field(min_length=1, max_length=512)
    new_password: str = Field(min_length=1, max_length=1024)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=1024)
    new_password: str = Field(min_length=1, max_length=1024)


class GenericAcceptedResponse(BaseModel):
    status: str = "accepted"


class ProfileUpdateRequest(BaseModel):
    """Self-service profile edit. Only personal fields are editable here;
    username, email and status are administrator/system managed and rejected."""

    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    job_title: str | None = Field(default=None, max_length=150)
    department: str | None = Field(default=None, max_length=150)
    phone: str | None = Field(default=None, max_length=50)
    locale: str | None = Field(default=None, max_length=20)
    timezone: str | None = Field(default=None, max_length=64)
    # Merged (shallow) into the existing preferences bag; only string keys with
    # JSON-scalar values are accepted so the bag stays a flat preference map.
    preferences: dict[str, object] | None = None

    @field_validator("timezone")
    @classmethod
    def _known_timezone(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return value
        if value not in available_timezones():
            raise ValueError("Unknown time zone.")
        return value

    @field_validator("preferences")
    @classmethod
    def _validate_preferences(cls, value: dict[str, object] | None) -> dict[str, object] | None:
        # Each preference value is a JSON scalar, or a single flat object of
        # scalars (e.g. a grouped set like `notifications: {Pipelines: false}`).
        # Deeper nesting is rejected so the bag stays a small, predictable map.
        def _is_scalar(v: object) -> bool:
            return v is None or isinstance(v, (str, int, float, bool))

        def _check_scalar(v: object) -> None:
            if not _is_scalar(v):
                raise ValueError("Preference values must be JSON scalars.")
            if isinstance(v, str) and len(v) > 256:
                raise ValueError("Preference value too long.")

        if value is None:
            return None
        if len(value) > 50:
            raise ValueError("Too many preference keys.")
        for key, item in value.items():
            if not isinstance(key, str) or len(key) > 64:
                raise ValueError("Invalid preference key.")
            if isinstance(item, dict):
                if len(item) > 50:
                    raise ValueError("Preference group too large.")
                for sub_key, sub_value in item.items():
                    if not isinstance(sub_key, str) or len(sub_key) > 64:
                        raise ValueError("Invalid preference key.")
                    _check_scalar(sub_value)
            else:
                _check_scalar(item)
        return value


class SessionSummary(BaseModel):
    id: UUID
    created_at: datetime
    last_seen_at: datetime
    access_expires_at: datetime
    refresh_expires_at: datetime
    current: bool = False
    # Raw User-Agent (client parses into a friendly device/browser label). No
    # location is stored, so the UI must not fabricate one.
    user_agent: str | None = None


class SessionListResponse(BaseModel):
    sessions: list[SessionSummary]
    current_session_id: UUID | None = None


class RevokeSessionsResponse(BaseModel):
    revoked: int
