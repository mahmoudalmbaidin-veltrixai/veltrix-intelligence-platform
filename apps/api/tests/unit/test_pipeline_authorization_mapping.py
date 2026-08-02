"""Unit: Pipeline action-to-level mapping and precedence (pure evaluator).

Locks the Pipeline capability ladder — Viewer < Operator < Developer < Owner —
and the deny/expiry/ownership/suspension precedence that the centralized
evaluator applies, with no database. These assert the *rules* the pipeline
services rely on when they call ``check_access`` with a per-action level.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from vip_api.governance.resource_access import (
    LEVEL_ORDERS,
    AccessDecision,
    AccessEntry,
    evaluate_resource_access,
)
from vip_api.governance.resource_access_service import role_level

pytestmark = pytest.mark.unit

NOW = datetime(2026, 8, 1, tzinfo=UTC)
LEVELS = ("viewer", "operator", "developer", "owner")


def _decide(
    action_level: str,
    *,
    entries: list[AccessEntry] | None = None,
    subject_ids: set[UUID] | None = None,
    **kwargs: object,
) -> AccessDecision:
    subject = uuid4()
    return evaluate_resource_access(
        resource_type="pipeline",
        action_level=action_level,
        subject_ids=subject_ids if subject_ids is not None else {subject},
        entries=entries or [],
        now=NOW,
        **kwargs,  # type: ignore[arg-type]
    )


# --- Ladder shape ---------------------------------------------------------


def test_pipeline_level_order_is_viewer_operator_developer_owner() -> None:
    assert LEVEL_ORDERS["pipeline"] == ("viewer", "operator", "developer", "owner")


# --- Role permission -> level mapping ------------------------------------


def test_role_level_maps_each_pipeline_permission() -> None:
    assert role_level("pipeline", frozenset({"pipeline.read"})) == "viewer"
    assert role_level("pipeline", frozenset({"pipeline.execute"})) == "operator"
    assert role_level("pipeline", frozenset({"pipeline.update"})) == "developer"


def test_role_level_takes_highest_when_multiple_permissions() -> None:
    perms = frozenset({"pipeline.read", "pipeline.execute", "pipeline.update"})
    assert role_level("pipeline", perms) == "developer"


def test_role_level_none_without_pipeline_permissions() -> None:
    assert role_level("pipeline", frozenset()) is None
    assert role_level("pipeline", frozenset({"dashboard.read", "dataset.read"})) is None


# --- ACL grant is bounded by its level ------------------------------------


@pytest.mark.parametrize(
    ("grant", "expected_allowed"),
    [
        ("viewer", {"viewer"}),
        ("operator", {"viewer", "operator"}),
        ("developer", {"viewer", "operator", "developer"}),
        ("owner", {"viewer", "operator", "developer", "owner"}),
    ],
)
def test_acl_grant_authorizes_exactly_its_band(grant: str, expected_allowed: set[str]) -> None:
    subject = uuid4()
    entry = AccessEntry(subject_type="user", subject_id=subject, access_level=grant)
    allowed = {
        level
        for level in LEVELS
        if evaluate_resource_access(
            resource_type="pipeline",
            action_level=level,
            subject_ids={subject},
            entries=[entry],
            now=NOW,
        ).allowed
    }
    assert allowed == expected_allowed


# --- Role level combines the same way -------------------------------------


def test_role_operator_level_authorizes_operator_not_developer() -> None:
    assert _decide("operator", role_granted_level="operator").allowed is True
    assert _decide("developer", role_granted_level="operator").allowed is False


# --- Ownership overrides everything (except deny/suspend) ------------------


def test_owner_flag_authorizes_all_levels() -> None:
    for level in LEVELS:
        assert _decide(level, is_owner=True).allowed is True


# --- Deny precedence -------------------------------------------------------


def test_viewer_deny_blocks_every_level() -> None:
    subject = uuid4()
    entries = [
        AccessEntry("user", subject, "owner"),  # even an owner allow...
        AccessEntry("user", subject, "viewer", effect="deny"),  # ...is beaten by deny
    ]
    for level in LEVELS:
        decision = evaluate_resource_access(
            resource_type="pipeline",
            action_level=level,
            subject_ids={subject},
            entries=entries,
            now=NOW,
        )
        assert decision.allowed is False
        assert decision.reason == "EXPLICIT_DENY"


def test_developer_deny_blocks_developer_and_owner_only() -> None:
    subject = uuid4()
    entries = [
        AccessEntry("user", subject, "owner"),
        AccessEntry("user", subject, "developer", effect="deny"),
    ]

    def allowed(level: str) -> bool:
        return evaluate_resource_access(
            resource_type="pipeline",
            action_level=level,
            subject_ids={subject},
            entries=entries,
            now=NOW,
        ).allowed

    # deny at developer blocks rank >= developer; viewer/operator still allowed
    # by the owner allow entry beneath it.
    assert allowed("viewer") is True
    assert allowed("operator") is True
    assert allowed("developer") is False
    assert allowed("owner") is False


# --- Expiry ----------------------------------------------------------------


def test_expired_allow_does_not_grant() -> None:
    subject = uuid4()
    entry = AccessEntry("user", subject, "developer", expires_at=NOW - timedelta(hours=1))
    decision = evaluate_resource_access(
        resource_type="pipeline",
        action_level="viewer",
        subject_ids={subject},
        entries=[entry],
        now=NOW,
    )
    assert decision.allowed is False
    assert decision.reason == "GRANT_EXPIRED"


# --- Suspension fails closed ----------------------------------------------


def test_suspended_subject_denied_even_with_owner_grant() -> None:
    decision = _decide("viewer", is_owner=True, subject_suspended=True)
    assert decision.allowed is False
    assert decision.reason == "SUBJECT_SUSPENDED"


# --- Foreign-subject entries are ignored (no cross-subject leakage) --------


def test_entry_for_other_subject_is_ignored() -> None:
    me = uuid4()
    someone_else = uuid4()
    entry = AccessEntry("user", someone_else, "owner")
    decision = evaluate_resource_access(
        resource_type="pipeline",
        action_level="viewer",
        subject_ids={me},
        entries=[entry],
        now=NOW,
    )
    assert decision.allowed is False
    assert decision.reason == "NO_GRANT"


# --- Group subject id participates via subject_ids -------------------------


def test_group_grant_applies_when_group_id_in_subject_ids() -> None:
    user = uuid4()
    group = uuid4()
    entry = AccessEntry("group", group, "developer")
    decision = evaluate_resource_access(
        resource_type="pipeline",
        action_level="developer",
        subject_ids={user, group},
        entries=[entry],
        now=NOW,
    )
    assert decision.allowed is True
