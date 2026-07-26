"""Deterministic retry policies and failure classification."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum


class RetryStrategy(StrEnum):
    FIXED = "fixed"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    CUSTOM = "custom"


class JobExecutionError(Exception):
    def __init__(self, code: str, safe_message: str, *, retryable: bool) -> None:
        super().__init__(safe_message)
        self.code = code
        self.safe_message = safe_message
        self.retryable = retryable


class RetryableJobError(JobExecutionError):
    def __init__(self, code: str, safe_message: str) -> None:
        super().__init__(code, safe_message, retryable=True)


class PermanentJobError(JobExecutionError):
    def __init__(self, code: str, safe_message: str) -> None:
        super().__init__(code, safe_message, retryable=False)


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    base_seconds: int = 2
    maximum_seconds: int = 300
    custom_delays: tuple[int, ...] = ()

    def delay(self, attempt: int) -> timedelta:
        if attempt < 1:
            raise ValueError("attempt must be positive")
        if self.strategy is RetryStrategy.FIXED:
            seconds = self.base_seconds
        elif self.strategy is RetryStrategy.LINEAR:
            seconds = self.base_seconds * attempt
        elif self.strategy is RetryStrategy.CUSTOM:
            index = min(attempt - 1, len(self.custom_delays) - 1)
            seconds = self.custom_delays[index] if self.custom_delays else self.base_seconds
        else:
            seconds = self.base_seconds * (2 ** (attempt - 1))
        return timedelta(seconds=min(seconds, self.maximum_seconds))
