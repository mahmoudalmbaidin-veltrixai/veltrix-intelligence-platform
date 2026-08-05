"""B8 retry, storage, upload-hardening and event-isolation unit coverage."""

import asyncio
from collections.abc import AsyncGenerator
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest

from vip_api.core.config import Settings
from vip_api.core.errors import ApplicationError
from vip_api.events.broker import PlatformEvent, RedisEventBroker
from vip_api.events.routes import _subscription_rate_key
from vip_api.files.scanning import ClamAvScanner, DefenderScanner
from vip_api.files.storage import LocalStorageProvider, StorageProviderError
from vip_api.files.validation import inspect_signature, sanitize_filename, validate_file_type
from vip_api.governance.context import AuthorizationContext
from vip_api.jobs.models import Job
from vip_api.jobs.registry import JobContextProtocol, registry
from vip_api.jobs.retry import RetryPolicy, RetryStrategy
from vip_api.jobs.worker import GenericJobWorker


def test_event_subscription_rate_limit_is_tenant_and_session_scoped() -> None:
    settings = cast(Settings, SimpleNamespace(JOB_QUEUE_PREFIX="vip:jobs"))
    context = cast(
        AuthorizationContext,
        SimpleNamespace(
            organization_id=uuid4(),
            workspace_id=uuid4(),
            user_id=uuid4(),
        ),
    )
    first_session = uuid4()
    second_session = uuid4()

    first_key = _subscription_rate_key(settings, context, first_session)
    assert first_key == _subscription_rate_key(settings, context, first_session)
    assert first_key != _subscription_rate_key(settings, context, second_session)
    assert str(context.organization_id) in first_key
    assert str(context.workspace_id) in first_key
    assert str(context.user_id) in first_key


def test_retry_policies_are_bounded_and_deterministic() -> None:
    exponential = RetryPolicy(RetryStrategy.EXPONENTIAL, 2, 10)
    linear = RetryPolicy(RetryStrategy.LINEAR, 3, 20)
    custom = RetryPolicy(RetryStrategy.CUSTOM, custom_delays=(1, 7, 11))
    assert exponential.delay(1) == timedelta(seconds=2)
    assert exponential.delay(5) == timedelta(seconds=10)
    assert linear.delay(3) == timedelta(seconds=9)
    assert custom.delay(2) == timedelta(seconds=7)
    assert custom.delay(9) == timedelta(seconds=11)
    with pytest.raises(ValueError):
        exponential.delay(0)


def test_filename_validation_blocks_traversal_and_disallowed_types() -> None:
    assert sanitize_filename("../../quarterly report.csv") == "quarterly report.csv"
    with pytest.raises(ApplicationError) as error:
        validate_file_type("payload.exe", "application/octet-stream", [".csv"], ["text/csv"])
    assert error.value.code == "FILE_TYPE_NOT_ALLOWED"
    with pytest.raises(ApplicationError) as mismatch:
        validate_file_type(
            "payload.png",
            "text/plain",
            [".png"],
            ["image/png", "text/plain"],
        )
    assert mismatch.value.code == "FILE_CONTENT_TYPE_MISMATCH"


def test_renamed_executable_is_rejected_before_scanning(tmp_path: Path) -> None:
    disguised = tmp_path / "report.txt"
    disguised.write_bytes(b"MZ" + b"\x00" * 32)
    with pytest.raises(ApplicationError) as error:
        inspect_signature(disguised, "text/plain")
    assert error.value.code == "FILE_CONTENT_MISMATCH"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("return_code", "expected"),
    [(0, "clean"), (2, "infected"), (1, "error")],
)
async def test_defender_scan_is_non_remediating_and_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    return_code: int,
    expected: str,
) -> None:
    arguments: tuple[object, ...] = ()

    class Process:
        async def wait(self) -> int:
            return return_code

        def kill(self) -> None:
            pass

    async def create_process(*args: object, **_kwargs: object) -> Process:
        nonlocal arguments
        arguments = args
        return Process()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", create_process)
    target = tmp_path / "sample.txt"
    target.write_text("safe", encoding="utf-8")
    result = await DefenderScanner("MpCmdRun.exe", 2).scan(target)

    assert result.status == expected
    assert "-DisableRemediation" in arguments


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("reply", "expected_status", "expected_signature"),
    [
        (b"stream: OK\0", "clean", None),
        (b"stream: Eicar-Signature FOUND\0", "infected", "Eicar-Signature"),
        (b"stream: malformed\0", "error", None),
    ],
)
async def test_clamav_scan_maps_protocol_responses_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    reply: bytes,
    expected_status: str,
    expected_signature: str | None,
) -> None:
    class Reader:
        async def read(self, _size: int) -> bytes:
            return reply

    class Writer:
        def write(self, _data: bytes) -> None:
            pass

        async def drain(self) -> None:
            pass

        def close(self) -> None:
            pass

        async def wait_closed(self) -> None:
            pass

    async def open_connection(_host: str, _port: int) -> tuple[Reader, Writer]:
        return Reader(), Writer()

    monkeypatch.setattr(asyncio, "open_connection", open_connection)
    target = tmp_path / "sample.txt"
    target.write_text("safe", encoding="utf-8")

    result = await ClamAvScanner("clamav", 3310, 2).scan(target)

    assert result.status == expected_status
    assert result.signature == expected_signature


@pytest.mark.asyncio
async def test_clamav_scan_returns_error_when_service_is_unreachable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def unreachable(_host: str, _port: int) -> None:
        raise ConnectionRefusedError

    monkeypatch.setattr(asyncio, "open_connection", unreachable)
    target = tmp_path / "sample.txt"
    target.write_text("safe", encoding="utf-8")

    result = await ClamAvScanner("clamav", 3310, 2).scan(target)

    assert result.status == "error"


@pytest.mark.asyncio
async def test_clamav_scan_returns_error_on_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def stalled(_host: str, _port: int) -> None:
        await asyncio.sleep(1)

    monkeypatch.setattr(asyncio, "open_connection", stalled)
    target = tmp_path / "sample.txt"
    target.write_text("safe", encoding="utf-8")

    result = await ClamAvScanner("clamav", 3310, 0.01).scan(target)

    assert result.status == "error"


@pytest.mark.asyncio
async def test_local_storage_never_allows_paths_outside_root(tmp_path: Path) -> None:
    provider = LocalStorageProvider(str(tmp_path / "root"))
    source = tmp_path / "source.txt"
    source.write_bytes(b"tenant-safe")
    await provider.put(source, "organization/workspace/file/1.txt")
    body = b"".join(
        [chunk async for chunk in provider.stream("organization/workspace/file/1.txt", 4)]
    )
    assert body == b"tenant-safe"
    with pytest.raises(StorageProviderError):
        await provider.exists("../outside.txt")


def test_event_stream_keys_are_tenant_and_workspace_qualified() -> None:
    broker = RedisEventBroker(object(), "vip:test", 100)  # type: ignore[arg-type]
    organization_a, organization_b, workspace = uuid4(), uuid4(), uuid4()
    key_a = broker._stream_key(organization_a, workspace)
    key_b = broker._stream_key(organization_b, workspace)
    assert key_a != key_b
    assert str(organization_a) in key_a and str(workspace) in key_a


@pytest.mark.asyncio
async def test_event_stream_resolves_dollar_once_and_preserves_order() -> None:
    class RedisStub:
        async def xrevrange(self, _key: str, *, count: int) -> list[tuple[str, object]]:
            assert count == 1
            return [("10-0", {})]

        async def xread(
            self, streams: dict[str, str], *, count: int, block: int
        ) -> list[tuple[str, list[tuple[str, dict[str, str]]]]]:
            assert next(iter(streams.values())) == "10-0"
            assert count == 100 and block > 0
            return [
                (
                    "tenant-stream",
                    [
                        ("11-0", {"event_type": "job.progress", "data": '{"percent":50}'}),
                        ("12-0", {"event_type": "job.completed", "data": '{"percent":100}'}),
                    ],
                )
            ]

    broker = RedisEventBroker(cast(Any, RedisStub()), "vip:test", 100)
    stream = cast(
        AsyncGenerator[PlatformEvent | None, None],
        broker.subscribe(uuid4(), uuid4(), "$", frozenset(), 1),
    )
    first = await anext(stream)
    second = await anext(stream)
    assert isinstance(first, PlatformEvent) and first.id == "11-0"
    assert isinstance(second, PlatformEvent) and second.id == "12-0"
    await stream.aclose()


@pytest.mark.asyncio
async def test_event_stream_reports_retention_gap_before_replay() -> None:
    class RedisStub:
        async def xrange(self, _key: str, *, count: int) -> list[tuple[str, object]]:
            assert count == 1
            return [("20-0", {})]

        async def xread(self, _streams: dict[str, str], *, count: int, block: int) -> list[object]:
            return []

    broker = RedisEventBroker(cast(Any, RedisStub()), "vip:test", 100)
    stream = cast(
        AsyncGenerator[PlatformEvent | None, None],
        broker.subscribe(uuid4(), uuid4(), "5-0", frozenset(), 1),
    )
    event = await anext(stream)
    assert isinstance(event, PlatformEvent)
    assert event.event_type == "stream.replay_gap"
    assert event.data["requested_cursor"] == "5-0"
    await stream.aclose()


@pytest.mark.asyncio
async def test_event_stream_turns_redis_read_timeout_into_heartbeat() -> None:
    from redis.exceptions import TimeoutError as RedisTimeoutError

    class RedisStub:
        async def xrevrange(self, _key: str, *, count: int) -> list[object]:
            return []

        async def xread(self, _streams: dict[str, str], *, count: int, block: int) -> list[object]:
            raise RedisTimeoutError("idle blocking read")

    broker = RedisEventBroker(cast(Any, RedisStub()), "vip:test", 100)
    stream = cast(
        AsyncGenerator[PlatformEvent | None, None],
        broker.subscribe(uuid4(), uuid4(), "$", frozenset(), 15),
    )
    assert await anext(stream) is None
    await stream.aclose()


def test_generic_worker_terminal_updates_require_active_owned_lease() -> None:
    worker = object.__new__(GenericJobWorker)
    worker.worker_id = "worker:current"
    assert worker._owns_active_lease(Job(status="running", lease_owner="worker:current"))
    assert not worker._owns_active_lease(Job(status="retrying", lease_owner="worker:current"))
    assert not worker._owns_active_lease(Job(status="running", lease_owner="worker:replacement"))


@pytest.mark.asyncio
async def test_generic_worker_honors_cancellation_after_handler_completion() -> None:
    cancellation_checks = iter((False, True))

    class Session:
        async def __aenter__(self) -> "Session":
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def get(self, _model: type[object], _identifier: object) -> object | None:
            return None

        async def scalar(self, _statement: object) -> bool:
            return next(cancellation_checks)

    class DatabaseStub:
        def session_factory(self) -> Session:
            return Session()

    async def handler(
        _context: JobContextProtocol, _payload: dict[str, object]
    ) -> dict[str, object]:
        return {"ok": True}

    handler_name = "tests.cancellation-after-handler"
    registry.register(handler_name, handler)

    class Worker(GenericJobWorker):
        def __init__(self) -> None:
            self.database = cast(object, DatabaseStub())  # type: ignore[assignment]
            self.broker = cast(RedisEventBroker, object())
            self.worker_id = "worker:test"
            self.cancelled: list[object] = []
            self.succeeded: list[object] = []

        async def _claim(self, job_id: object) -> Job:
            return cast(
                Job,
                SimpleNamespace(
                    id=job_id,
                    correlation_id="test-correlation",
                    handler=handler_name,
                    timeout_seconds=5,
                ),
            )

        async def _renew_lease(self, _job_id: object) -> None:
            await asyncio.Event().wait()

        async def _cancel(self, job_id: object) -> None:
            self.cancelled.append(job_id)

        async def _succeed(self, job_id: object, _result: dict[str, object]) -> None:
            self.succeeded.append(job_id)

    worker = Worker()
    job_id = uuid4()
    await worker._execute(job_id)
    assert worker.cancelled == [job_id]
    assert worker.succeeded == []
