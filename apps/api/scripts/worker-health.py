"""Container health probe for the generic worker heartbeat."""

from __future__ import annotations

import asyncio
import socket
import sys
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from vip_api.core.config import get_settings
from vip_api.database.session import Database
from vip_api.jobs.models import WorkerHeartbeat


async def check() -> bool:
    settings = get_settings()
    database = Database(settings)
    try:
        async with database.session_factory() as db:
            heartbeat = await db.scalar(
                select(WorkerHeartbeat)
                .where(
                    WorkerHeartbeat.hostname == socket.gethostname(),
                    WorkerHeartbeat.status == "running",
                )
                .order_by(WorkerHeartbeat.last_seen_at.desc())
                .limit(1)
            )
            cutoff = datetime.now(UTC) - timedelta(
                seconds=max(settings.JOB_HEARTBEAT_SECONDS * 3, 30)
            )
            return heartbeat is not None and heartbeat.last_seen_at >= cutoff
    finally:
        await database.dispose()


if __name__ == "__main__":
    sys.exit(0 if asyncio.run(check()) else 1)
