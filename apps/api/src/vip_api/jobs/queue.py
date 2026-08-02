"""Replaceable priority/delay queue abstraction backed initially by Redis.

Ordering contract (independent of wall-clock enqueue timing):

  1. A job that is *ready* (its delay, if any, has elapsed) is always eligible
     before any job that is still delayed.
  2. Among ready jobs, higher ``priority`` wins.
  3. Among ready jobs of equal priority, earlier enqueue wins (FIFO).

To honour all three at once, ready jobs and delayed jobs live in two separate
sorted sets:

* the *ready* set is scored purely by ``(priority, sequence)`` so priority (and
  then FIFO) fully determines pop order — arrival second never interferes;
* the *delayed* set is scored by the absolute availability time in milliseconds,
  so a delayed job cannot be popped before it is due.

``dequeue`` atomically promotes any now-due delayed jobs into the ready set and
then pops the highest-priority ready job in a single Lua script, which keeps the
operation correct across multiple worker processes without sleeps or retries.
The database remains the authoritative job state; Redis only orders work.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from math import ceil
from typing import Protocol
from uuid import UUID

from redis.asyncio import Redis

# FIFO sequence space reserved below each priority tier. The ready score is
# ``priority_offset * _PRIORITY_TIER + sequence`` where ``priority_offset`` is in
# [0, 200]; keeping ``sequence`` below this bound guarantees priority always
# outranks arrival order while the total stays an exactly-representable double
# (max ≈ 200 * 1e13 + seq < 2**53). 1e13 enqueues per prefix is unreachable.
_PRIORITY_TIER = 10**13


@dataclass(frozen=True, slots=True)
class QueueMetrics:
    queue: str
    ready: int
    delayed: int


class JobQueue(Protocol):
    async def enqueue(
        self, queue: str, job_id: UUID, *, priority: int = 0, delay_seconds: float = 0
    ) -> None: ...

    async def dequeue(self, queue: str) -> UUID | None: ...
    async def metrics(self, queue: str) -> QueueMetrics: ...


class RedisJobQueue:
    """Sorted-set queue; the database remains the authoritative job state."""

    # Promote every now-due delayed job into the ready set (carrying its
    # pre-computed priority/FIFO score), then pop the highest-priority ready job.
    # KEYS: [ready set, delayed set, pending-score hash]; ARGV: [now_ms].
    _POP_SCRIPT = """
local due = redis.call('ZRANGEBYSCORE', KEYS[2], '-inf', ARGV[1])
for i = 1, #due do
    local member = due[i]
    local ready_score = redis.call('HGET', KEYS[3], member)
    if ready_score then
        redis.call('ZADD', KEYS[1], ready_score, member)
        redis.call('HDEL', KEYS[3], member)
    end
    redis.call('ZREM', KEYS[2], member)
end
local popped = redis.call('ZPOPMIN', KEYS[1])
if #popped == 0 then return nil end
return popped[1]
"""

    def __init__(self, redis: Redis, prefix: str) -> None:
        self._redis = redis
        self._prefix = prefix

    def _ready_key(self, queue: str) -> str:
        return f"{self._prefix}:queue:{queue}"

    def _delayed_key(self, queue: str) -> str:
        return f"{self._prefix}:queue:{queue}:delayed"

    def _pending_key(self, queue: str) -> str:
        return f"{self._prefix}:queue:{queue}:pending"

    def _sequence_key(self) -> str:
        return f"{self._prefix}:sequence"

    def _ready_score(self, priority: int, sequence: int) -> int:
        priority_offset = 100 - max(-100, min(priority, 100))  # 0 (highest) .. 200
        return (priority_offset * _PRIORITY_TIER) + sequence

    async def enqueue(
        self, queue: str, job_id: UUID, *, priority: int = 0, delay_seconds: float = 0
    ) -> None:
        sequence = int(await self._redis.incr(self._sequence_key()))
        ready_score = self._ready_score(priority, sequence)
        member = str(job_id)
        if delay_seconds > 0:
            available_ms = ceil((time.time() + delay_seconds) * 1000)
            # Record the ready score before advertising the delayed member so a
            # concurrent dequeue can never promote it without its score.
            # hset carries redis-py's `Awaitable[int] | int` async-stub union.
            await self._redis.hset(  # type: ignore[misc]
                self._pending_key(queue), member, str(ready_score)
            )
            await self._redis.zadd(self._delayed_key(queue), {member: available_ms})
        else:
            await self._redis.zadd(self._ready_key(queue), {member: ready_score})

    async def dequeue(self, queue: str) -> UUID | None:
        now_ms = int(time.time() * 1000)
        value = await self._redis.eval(  # type: ignore[misc]
            self._POP_SCRIPT,
            3,
            self._ready_key(queue),
            self._delayed_key(queue),
            self._pending_key(queue),
            str(now_ms),
        )
        return UUID(str(value)) if value else None

    async def metrics(self, queue: str) -> QueueMetrics:
        now_ms = int(time.time() * 1000)
        ready = int(await self._redis.zcard(self._ready_key(queue)))
        due = int(await self._redis.zcount(self._delayed_key(queue), "-inf", now_ms))
        total_delayed = int(await self._redis.zcard(self._delayed_key(queue)))
        return QueueMetrics(queue, ready + due, total_delayed - due)
