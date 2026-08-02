"""Deterministic, explainable resource-access evaluation (Slice A foundation).

Pure and IO-free so the precedence rules are exhaustively unit-testable. The
service computes an allow/deny decision for a (subject, resource, action) plus a
safe administrative explanation. It is additive: nothing here changes the
existing role-permission decision path yet — resource enforcement is wired in a
later slice.

Precedence (highest wins), matching the documented design:

  1. Suspended subject                -> DENY  (fail closed, even super-admin)
  2. Explicit resource deny           -> DENY  (deny is the strongest control)
  3. Platform super-admin override    -> ALLOW
  4. Archived workspace               -> DENY  (blocks non-super-admin access)
  5. Ownership                        -> ALLOW (owner has every level)
  6. Grant (resource ACL and/or role) -> ALLOW if a non-expired grant covers the
                                         requested level
  7. Otherwise                        -> DENY  (no grant; "expired" if the only
                                         matching grant had lapsed)

A deny at level L blocks every action whose required level is >= L (a deny of
the lowest level blocks everything; a deny of "edit" still permits "view").
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

# Canonical access-level ladders per resource type. Higher index = more power and
# implicitly includes every lower level.
LEVEL_ORDERS: dict[str, tuple[str, ...]] = {
    "dashboard": ("view", "interact", "edit", "manage"),
    "pipeline": ("viewer", "operator", "developer", "owner"),
    "dataset": ("query", "export", "edit", "certify", "manage"),
    "connection": ("use", "test", "edit", "rotate", "manage"),
    "report": ("view", "interact", "edit", "manage"),
    "semantic_model": ("view", "query", "edit", "manage"),
}


@dataclass(frozen=True, slots=True)
class AccessEntry:
    """An in-memory resource ACL entry for evaluation (mirrors ResourceAccessEntry)."""

    subject_type: str
    subject_id: UUID
    access_level: str
    effect: str = "allow"  # "allow" | "deny"
    expires_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class AccessDecision:
    allowed: bool
    reason: str  # machine-stable code
    source: str  # which layer decided
    matched_level: str | None = None
    expired_grant_seen: bool = field(default=False)


def _rank(order: tuple[str, ...], level: str) -> int | None:
    try:
        return order.index(level)
    except ValueError:
        return None


def evaluate_resource_access(
    *,
    resource_type: str,
    action_level: str,
    subject_ids: set[UUID],
    entries: Iterable[AccessEntry],
    now: datetime,
    is_platform_admin: bool = False,
    is_owner: bool = False,
    subject_suspended: bool = False,
    workspace_archived: bool = False,
    role_granted_level: str | None = None,
) -> AccessDecision:
    order = LEVEL_ORDERS.get(resource_type)
    if order is None:
        raise ValueError(f"Unknown resource type: {resource_type}")
    action_rank = _rank(order, action_level)
    if action_rank is None:
        raise ValueError(f"Unknown access level '{action_level}' for {resource_type}")

    relevant = [entry for entry in entries if entry.subject_id in subject_ids]

    def _active(entry: AccessEntry) -> bool:
        return entry.expires_at is None or entry.expires_at > now

    # 1. Suspended subject — fail closed.
    if subject_suspended:
        return AccessDecision(False, "SUBJECT_SUSPENDED", "suspended")

    # 2. Explicit deny (non-expired) covering the requested level.
    for entry in relevant:
        if entry.effect != "deny" or not _active(entry):
            continue
        deny_rank = _rank(order, entry.access_level)
        if deny_rank is not None and action_rank >= deny_rank:
            return AccessDecision(False, "EXPLICIT_DENY", "resource_deny", entry.access_level)

    # 3. Platform super-admin override.
    if is_platform_admin:
        return AccessDecision(True, "SUPER_ADMIN_OVERRIDE", "super_admin", order[-1])

    # 4. Archived workspace blocks non-super-admin access.
    if workspace_archived:
        return AccessDecision(False, "WORKSPACE_ARCHIVED", "archived_workspace")

    # 5. Ownership grants every level.
    if is_owner:
        return AccessDecision(True, "OWNER", "owner", order[-1])

    # 6. Grants — resource ACL allows and/or role-derived level.
    best_rank = -1
    best_level: str | None = None
    expired_seen = False
    for entry in relevant:
        if entry.effect != "allow":
            continue
        grant_rank = _rank(order, entry.access_level)
        if grant_rank is None:
            continue
        if not _active(entry):
            if grant_rank >= action_rank:
                expired_seen = True
            continue
        if grant_rank > best_rank:
            best_rank, best_level = grant_rank, entry.access_level

    role_rank = _rank(order, role_granted_level) if role_granted_level else None
    if role_rank is not None and role_rank > best_rank:
        best_rank, best_level = role_rank, role_granted_level

    if best_rank >= action_rank:
        source = "resource_grant" if best_level != role_granted_level else "role_permission"
        return AccessDecision(True, "GRANTED", source, best_level)

    # 7. No sufficient grant.
    if expired_seen:
        return AccessDecision(False, "GRANT_EXPIRED", "expired", expired_grant_seen=True)
    return AccessDecision(False, "NO_GRANT", "no_grant")
