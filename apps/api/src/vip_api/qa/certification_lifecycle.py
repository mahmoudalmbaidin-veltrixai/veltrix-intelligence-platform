"""Deterministic QA/certification fixture lifecycle (VIP-BUG-009).

Resources created during a certification run are namespaced with a unique run
id, registered by exact ID, and cleaned up in dependency-safe order. Cleanup
never issues broad LIKE deletes against ambiguous production-like data.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

ResourceKind = Literal[
    "organization",
    "workspace",
    "user",
    "connection",
    "file",
    "dataset",
    "pipeline",
    "dashboard",
    "schedule",
    "export",
]

# Dependency-safe deletion order (dependents first).
CLEANUP_ORDER: tuple[ResourceKind, ...] = (
    "export",
    "schedule",
    "dashboard",
    "pipeline",
    "dataset",
    "file",
    "connection",
    "user",
    "workspace",
    "organization",
)

_RUN_ID_RE = re.compile(r"^qa-cert-\d{8}-[a-f0-9]{8}$")


def new_run_id(now: datetime | None = None) -> str:
    stamp = (now or datetime.now(UTC)).strftime("%Y%m%d")
    return f"qa-cert-{stamp}-{uuid.uuid4().hex[:8]}"


def assert_safe_run_id(run_id: str) -> str:
    if not _RUN_ID_RE.fullmatch(run_id):
        raise ValueError(
            f"Unsafe certification run id {run_id!r}; expected qa-cert-YYYYMMDD-<8 hex>"
        )
    return run_id


@dataclass
class RegisteredResource:
    kind: ResourceKind
    id: str
    name: str
    retain: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CleanupReport:
    run_id: str
    created: int
    deleted: list[str] = field(default_factory=list)
    retained: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class CertificationFixtureRegistry:
    """In-memory registry for one certification run."""

    def __init__(
        self,
        run_id: str | None = None,
        *,
        environment_guard: str = "certification",
        allowed_environments: frozenset[str] | None = None,
    ) -> None:
        self.run_id = assert_safe_run_id(run_id or new_run_id())
        self.environment_guard = environment_guard
        self.allowed_environments = allowed_environments or frozenset(
            {"certification", "test", "ci", "local"}
        )
        self._resources: list[RegisteredResource] = []

    def namespaced(self, label: str) -> str:
        safe = re.sub(r"[^A-Za-z0-9._-]+", "-", label).strip("-")[:80]
        return f"{self.run_id}-{safe}"

    def register(
        self,
        kind: ResourceKind,
        resource_id: str,
        name: str,
        *,
        retain: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> RegisteredResource:
        item = RegisteredResource(
            kind=kind,
            id=str(resource_id),
            name=name,
            retain=retain,
            metadata=metadata or {},
        )
        self._resources.append(item)
        return item

    def mark_retained(self, resource_id: str) -> None:
        for item in self._resources:
            if item.id == resource_id:
                item.retain = True

    @property
    def resources(self) -> list[RegisteredResource]:
        return list(self._resources)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "run_id": self.run_id,
            "environment_guard": self.environment_guard,
            "resources": [asdict(item) for item in self._resources],
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> CertificationFixtureRegistry:
        payload = json.loads(path.read_text(encoding="utf-8"))
        registry = cls(
            run_id=str(payload["run_id"]),
            environment_guard=str(payload.get("environment_guard", "certification")),
        )
        for item in payload.get("resources", []):
            registry.register(
                item["kind"],
                item["id"],
                item["name"],
                retain=bool(item.get("retain", False)),
                metadata=dict(item.get("metadata") or {}),
            )
        return registry

    def ensure_environment_allowed(self) -> None:
        if self.environment_guard not in self.allowed_environments:
            raise RuntimeError(
                f"Refusing QA cleanup in environment {self.environment_guard!r}; "
                f"allowed={sorted(self.allowed_environments)}"
            )

    async def cleanup(
        self,
        delete_handlers: dict[ResourceKind, Any],
    ) -> CleanupReport:
        """Delete registered disposable resources using exact IDs only."""
        self.ensure_environment_allowed()
        report = CleanupReport(run_id=self.run_id, created=len(self._resources))
        by_kind: dict[ResourceKind, list[RegisteredResource]] = {kind: [] for kind in CLEANUP_ORDER}
        for item in self._resources:
            by_kind.setdefault(item.kind, []).append(item)
        for kind in CLEANUP_ORDER:
            handler = delete_handlers.get(kind)
            for item in by_kind.get(kind, []):
                label = f"{kind}:{item.id}:{item.name}"
                if item.retain:
                    report.retained.append(label)
                    continue
                if handler is None:
                    report.failures.append(f"{label}: no delete handler")
                    continue
                try:
                    result = handler(item)
                    if hasattr(result, "__await__"):
                        await result
                    report.deleted.append(label)
                except Exception as exc:
                    report.failures.append(f"{label}: {exc}")
        return report


def identify_likely_stale_names(
    names: list[str], *, prefix_hints: tuple[str, ...] = ()
) -> list[str]:
    """Report likely stale QA names without deleting them.

    Only returns names that clearly match certification run namespaces or
    explicit prefix hints. Ambiguous names are left untouched.
    """
    hints = prefix_hints or (
        "qa-cert-",
        "B9.1B Disposable",
        "qa-phase1-e2e-",
        "Browser B4",
        "Contract QA",
    )
    stale: list[str] = []
    for name in names:
        if any(name.startswith(hint) for hint in hints):
            stale.append(name)
            continue
        if _RUN_ID_RE.search(name):
            stale.append(name)
    return sorted(set(stale))
