"""Explicit registry of trusted job handlers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol
from uuid import UUID


class JobContextProtocol(Protocol):
    job_id: UUID

    async def progress(
        self,
        percent: int,
        *,
        stage: str,
        message: str,
        completed_steps: int = 0,
        total_steps: int | None = None,
    ) -> None: ...

    async def cancellation_requested(self) -> bool: ...


JobHandler = Callable[[JobContextProtocol, dict[str, object]], Awaitable[dict[str, object]]]


class JobHandlerRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, JobHandler] = {}

    def register(self, name: str, handler: JobHandler) -> None:
        if name in self._handlers:
            raise RuntimeError(f"Job handler already registered: {name}")
        self._handlers[name] = handler

    def get(self, name: str) -> JobHandler:
        try:
            return self._handlers[name]
        except KeyError as exc:
            raise RuntimeError(f"Unknown job handler: {name}") from exc


registry = JobHandlerRegistry()
