"""Public home-summary contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class HealthMetric(BaseModel):
    label: str
    value: str
    delta: int | None = None
    tone: Literal["success", "warning", "danger", "info", "neutral"]
    icon: str
    spark: list[int]


class RecentResource(BaseModel):
    id: str
    name: str
    type: str
    icon: str
    to: str
    when: datetime


class ActivityEntry(BaseModel):
    id: str
    actor: str
    action: str
    target: str
    when: datetime
    icon: str


class ActivityFeedEntry(BaseModel):
    id: str
    domain: Literal[
        "pipeline",
        "dataset",
        "dashboard",
        "report",
        "ai",
        "automation",
        "admin",
        "billing",
    ]
    actor: str
    action: str
    target: str
    ts: datetime


class ChecklistItem(BaseModel):
    id: str
    label: str
    done: bool
    to: str


class HomeSummary(BaseModel):
    health: list[HealthMetric]
    recent: list[RecentResource]
    activity: list[ActivityEntry]
    checklist: list[ChecklistItem]
    pendingApprovals: int


class NotificationResource(BaseModel):
    label: str
    to: str


class NotificationEntry(BaseModel):
    id: str
    severity: Literal["info", "success", "warning", "danger"]
    title: str
    body: str
    category: str
    ts: datetime
    read: bool = False
    resource: NotificationResource | None = None
