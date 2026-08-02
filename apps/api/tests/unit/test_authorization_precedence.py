"""Authoritative authorization precedence (Enterprise permissions — Phase C).

These tests lock in the single, documented precedence rule used everywhere:

    suspended > explicit deny > super-admin > archived workspace > ownership >
    grant (resource ACL / role) > default deny

The historically contradictory question — "does super-admin beat an explicit
deny?" — is resolved here in favor of *deny wins* (AWS-IAM style, fail-closed):
an explicit deny is evaluated before the super-admin override and therefore
overrides it. Super-admin still overrides archived-workspace and every lower
signal. This file is the executable specification for that rule.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from vip_api.governance.resource_access import (
    AccessDecision,
    AccessEntry,
    evaluate_resource_access,
)

NOW = datetime(2026, 8, 1, tzinfo=UTC)
USER = uuid4()


def _decide(**kwargs: object) -> AccessDecision:
    base: dict[str, object] = {
        "resource_type": "dashboard",
        "action_level": "view",
        "subject_ids": {USER},
        "entries": [],
        "now": NOW,
    }
    base.update(kwargs)
    return evaluate_resource_access(**base)  # type: ignore[arg-type]


def _deny(level: str = "view") -> AccessEntry:
    return AccessEntry(subject_type="user", subject_id=USER, access_level=level, effect="deny")


def _allow(level: str, *, expires: datetime | None = None) -> AccessEntry:
    return AccessEntry(
        subject_type="user", subject_id=USER, access_level=level, effect="allow", expires_at=expires
    )


def test_suspended_beats_everything_including_super_admin() -> None:
    decision = _decide(subject_suspended=True, is_platform_admin=True, is_owner=True)
    assert decision.allowed is False
    assert decision.reason == "SUBJECT_SUSPENDED"


def test_explicit_deny_overrides_super_admin() -> None:
    decision = _decide(entries=[_deny("view")], is_platform_admin=True)
    assert decision.allowed is False
    assert decision.reason == "EXPLICIT_DENY"


def test_super_admin_overrides_archived_workspace_and_missing_grant() -> None:
    decision = _decide(is_platform_admin=True, workspace_archived=True)
    assert decision.allowed is True
    assert decision.reason == "SUPER_ADMIN_OVERRIDE"


def test_archived_workspace_denies_non_super_admin_owner() -> None:
    decision = _decide(workspace_archived=True, is_owner=True)
    assert decision.allowed is False
    assert decision.reason == "WORKSPACE_ARCHIVED"


def test_ownership_grants_full_access() -> None:
    decision = _decide(action_level="manage", is_owner=True)
    assert decision.allowed is True
    assert decision.reason == "OWNER"


def test_resource_allow_grants_up_to_level() -> None:
    decision = _decide(action_level="edit", entries=[_allow("edit")])
    assert decision.allowed is True
    decision = _decide(action_level="manage", entries=[_allow("edit")])
    assert decision.allowed is False
    assert decision.reason == "NO_GRANT"


def test_role_grant_counts_as_allow() -> None:
    decision = _decide(action_level="interact", role_granted_level="edit")
    assert decision.allowed is True


def test_expired_allow_is_ignored_and_reported() -> None:
    expired = _allow("edit", expires=NOW - timedelta(hours=1))
    decision = _decide(action_level="edit", entries=[expired])
    assert decision.allowed is False
    assert decision.reason == "GRANT_EXPIRED"


def test_deny_of_higher_level_does_not_block_lower_action() -> None:
    # Deny "edit" still permits "view"; deny of the lowest level blocks all.
    decision = _decide(action_level="view", entries=[_deny("edit"), _allow("view")])
    assert decision.allowed is True
    decision = _decide(action_level="edit", entries=[_deny("edit"), _allow("edit")])
    assert decision.allowed is False
    assert decision.reason == "EXPLICIT_DENY"
