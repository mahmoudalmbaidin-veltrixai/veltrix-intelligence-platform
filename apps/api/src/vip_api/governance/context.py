"""Immutable request-scoped authorization state derived by the backend."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from uuid import UUID


@dataclass(frozen=True, slots=True)
class QuotaSnapshot:
    limit: int
    used: int
    reserved: int
    remaining: int
    hard: bool


@dataclass(frozen=True, slots=True)
class AuthorizationContext:
    user_id: UUID
    organization_id: UUID
    workspace_id: UUID | None
    organization_role_key: str
    workspace_role_key: str | None
    permissions: frozenset[str]
    entitlements: frozenset[str]
    feature_flags: Mapping[str, bool]
    quotas: Mapping[str, QuotaSnapshot]
    correlation_id: str

    @staticmethod
    def readonly(values: dict[str, object]) -> Mapping[str, object]:
        return MappingProxyType(values)
