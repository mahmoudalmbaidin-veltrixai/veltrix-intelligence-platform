"""Request-model guards for the focused administration surface.

These are pure schema tests (no database) covering the security-relevant
validation: mass-assignment protection (``extra="forbid"``), the
username-or-email requirement for membership assignment, the admin
password-reset policy, and the workspace slug format.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from vip_api.platform_admin.schemas import (
    AddOrgMemberRequest,
    AddWorkspaceMemberRequest,
    AdminResetPasswordRequest,
    CreateWorkspaceRequest,
    UpdatePlatformUserRequest,
)

pytestmark = pytest.mark.unit


def test_org_member_requires_username_or_email() -> None:
    with pytest.raises(ValidationError):
        AddOrgMemberRequest(organization_role="organization_member")
    # username alone is sufficient (email-less accounts must be assignable)
    assert AddOrgMemberRequest(username="e2e.member", organization_role="organization_member")


def test_workspace_member_requires_identifier_and_role() -> None:
    with pytest.raises(ValidationError):
        AddWorkspaceMemberRequest(workspace_role="workspace_admin")
    assert AddWorkspaceMemberRequest(username="e2e.member", workspace_role="workspace_admin")


def test_admin_reset_password_enforces_minimum_length() -> None:
    with pytest.raises(ValidationError):
        AdminResetPasswordRequest(password="short")
    reset = AdminResetPasswordRequest(password="a-sufficiently-long-secret")
    # must_change_password defaults to True (safe default for admin-set passwords)
    assert reset.must_change_password is True


def test_update_user_rejects_unknown_fields_mass_assignment() -> None:
    # Mass-assignment guard: privileged columns must not be settable via the PATCH body.
    for forbidden in ("is_platform_admin", "password_hash", "status", "id"):
        with pytest.raises(ValidationError):
            UpdatePlatformUserRequest(**{forbidden: "x"})


def test_update_user_empty_email_is_allowed_to_clear() -> None:
    payload = UpdatePlatformUserRequest(email="")
    assert payload.email == ""


def test_create_workspace_slug_pattern() -> None:
    assert CreateWorkspaceRequest(name="Marketing", slug="marketing-team")
    for bad in ("Marketing", "bad_slug", "-lead", "a"):
        with pytest.raises(ValidationError):
            CreateWorkspaceRequest(name="Marketing", slug=bad)
