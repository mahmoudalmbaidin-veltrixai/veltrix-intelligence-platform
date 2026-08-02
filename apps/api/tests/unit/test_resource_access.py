"""Precedence coverage for the explainable resource-access evaluator (Slice A)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from vip_api.governance.resource_access import (
    AccessDecision,
    AccessEntry,
    evaluate_resource_access,
)

pytestmark = pytest.mark.unit

NOW = datetime(2026, 7, 29, tzinfo=UTC)
USER = uuid4()
GROUP = uuid4()
OTHER = uuid4()


def _eval(
    *,
    resource_type: str = "dashboard",
    action_level: str = "edit",
    subject_ids: set[UUID] | None = None,
    entries: list[AccessEntry] | None = None,
    now: datetime = NOW,
    is_platform_admin: bool = False,
    is_owner: bool = False,
    subject_suspended: bool = False,
    workspace_archived: bool = False,
    role_granted_level: str | None = None,
) -> AccessDecision:
    return evaluate_resource_access(
        resource_type=resource_type,
        action_level=action_level,
        subject_ids={USER, GROUP} if subject_ids is None else subject_ids,
        entries=[] if entries is None else entries,
        now=now,
        is_platform_admin=is_platform_admin,
        is_owner=is_owner,
        subject_suspended=subject_suspended,
        workspace_archived=workspace_archived,
        role_granted_level=role_granted_level,
    )


def test_no_grant_denies() -> None:
    d = _eval()
    assert d.allowed is False and d.reason == "NO_GRANT"


def test_direct_grant_allows_at_or_above_requested_level() -> None:
    d = _eval(entries=[AccessEntry("user", USER, "manage")])  # manage >= edit
    assert d.allowed is True and d.source == "resource_grant" and d.matched_level == "manage"


def test_grant_below_requested_level_denies() -> None:
    d = _eval(entries=[AccessEntry("user", USER, "view")])  # view < edit
    assert d.allowed is False and d.reason == "NO_GRANT"


def test_group_grant_counts() -> None:
    d = _eval(entries=[AccessEntry("group", GROUP, "edit")])
    assert d.allowed is True


def test_grant_for_other_subject_is_ignored() -> None:
    d = _eval(entries=[AccessEntry("user", OTHER, "manage")])
    assert d.allowed is False


def test_role_derived_level_grants() -> None:
    d = _eval(role_granted_level="edit")
    assert d.allowed is True and d.source == "role_permission"


def test_explicit_deny_overrides_grant() -> None:
    d = _eval(
        entries=[AccessEntry("user", USER, "manage"), AccessEntry("group", GROUP, "edit", "deny")],
    )
    assert d.allowed is False and d.reason == "EXPLICIT_DENY"


def test_deny_at_lower_level_blocks_higher_actions() -> None:
    # deny of "view" blocks everything, including edit
    d = _eval(action_level="edit", entries=[AccessEntry("user", USER, "view", "deny")])
    assert d.allowed is False and d.reason == "EXPLICIT_DENY"


def test_deny_of_higher_level_does_not_block_lower_action() -> None:
    # deny of "edit" must NOT block "view"
    d = _eval(
        action_level="view",
        entries=[AccessEntry("user", USER, "edit", "deny"), AccessEntry("user", USER, "view")],
    )
    assert d.allowed is True


def test_explicit_deny_overrides_super_admin() -> None:
    d = _eval(is_platform_admin=True, entries=[AccessEntry("user", USER, "edit", "deny")])
    assert d.allowed is False and d.reason == "EXPLICIT_DENY"


def test_super_admin_overrides_missing_grant() -> None:
    d = _eval(is_platform_admin=True)
    assert d.allowed is True and d.reason == "SUPER_ADMIN_OVERRIDE"


def test_suspended_subject_fails_closed_even_for_super_admin() -> None:
    d = _eval(is_platform_admin=True, subject_suspended=True)
    assert d.allowed is False and d.reason == "SUBJECT_SUSPENDED"


def test_archived_workspace_blocks_normal_grant_but_not_super_admin() -> None:
    blocked = _eval(workspace_archived=True, entries=[AccessEntry("user", USER, "manage")])
    assert blocked.allowed is False and blocked.reason == "WORKSPACE_ARCHIVED"
    admin = _eval(workspace_archived=True, is_platform_admin=True)
    assert admin.allowed is True


def test_owner_has_every_level() -> None:
    d = _eval(action_level="manage", is_owner=True)
    assert d.allowed is True and d.source == "owner"


def test_expired_grant_is_ignored_and_explained() -> None:
    past = NOW - timedelta(hours=1)
    d = _eval(entries=[AccessEntry("user", USER, "manage", "allow", expires_at=past)])
    assert d.allowed is False and d.reason == "GRANT_EXPIRED" and d.expired_grant_seen is True


def test_active_grant_with_future_expiry_allows() -> None:
    future = NOW + timedelta(hours=1)
    d = _eval(entries=[AccessEntry("user", USER, "edit", "allow", expires_at=future)])
    assert d.allowed is True


def test_expired_deny_does_not_block() -> None:
    past = NOW - timedelta(hours=1)
    d = _eval(
        entries=[
            AccessEntry("user", USER, "edit", "deny", expires_at=past),
            AccessEntry("user", USER, "edit"),
        ],
    )
    assert d.allowed is True


def test_pipeline_ladder_operator_cannot_develop() -> None:
    d = evaluate_resource_access(
        resource_type="pipeline",
        action_level="developer",
        subject_ids={USER},
        entries=[AccessEntry("user", USER, "operator")],
        now=NOW,
    )
    assert d.allowed is False


def test_unknown_resource_type_raises() -> None:
    with pytest.raises(ValueError):
        evaluate_resource_access(
            resource_type="nope",
            action_level="view",
            subject_ids={USER},
            entries=[],
            now=NOW,
        )
