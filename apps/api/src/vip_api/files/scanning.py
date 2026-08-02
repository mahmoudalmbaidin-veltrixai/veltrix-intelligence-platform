"""Replaceable malware scanning contract."""

from __future__ import annotations

import asyncio
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from vip_api.core.config import Settings


@dataclass(frozen=True, slots=True)
class ScanResult:
    status: str
    signature: str | None = None


class MalwareScanner(Protocol):
    name: str

    async def scan(self, path: Path) -> ScanResult: ...


class NoopDevelopmentScanner:
    """Development-only scanner; production configuration rejects this provider."""

    name = "noop"

    async def scan(self, path: Path) -> ScanResult:
        if not await asyncio.to_thread(path.is_file):
            return ScanResult("error")
        return ScanResult("clean")


class ClamAvScanner:
    name = "clamav"

    def __init__(self, host: str, port: int, timeout: float) -> None:
        self._host = host
        self._port = port
        self._timeout = timeout

    async def scan(self, path: Path) -> ScanResult:
        async def execute() -> ScanResult:
            reader, writer = await asyncio.open_connection(self._host, self._port)
            try:
                writer.write(b"zINSTREAM\0")
                handle = await asyncio.to_thread(path.open, "rb")
                try:
                    while chunk := await asyncio.to_thread(handle.read, 1024 * 1024):
                        writer.write(struct.pack("!I", len(chunk)) + chunk)
                        await writer.drain()
                finally:
                    await asyncio.to_thread(handle.close)
                writer.write(struct.pack("!I", 0))
                await writer.drain()
                reply = (await reader.read(4096)).decode(errors="replace").strip("\0\r\n")
            finally:
                writer.close()
                await writer.wait_closed()
            if reply.endswith("OK"):
                return ScanResult("clean")
            if "FOUND" in reply:
                signature = reply.rsplit(":", 1)[-1].replace("FOUND", "").strip()
                return ScanResult("infected", signature[:200] or None)
            return ScanResult("error")

        try:
            return await asyncio.wait_for(execute(), timeout=self._timeout)
        except (OSError, TimeoutError, UnicodeError):
            return ScanResult("error")


class DefenderScanner:
    name = "defender"

    def __init__(self, command: str, timeout: float) -> None:
        self._command = command
        self._timeout = timeout

    async def scan(self, path: Path) -> ScanResult:
        process = await asyncio.create_subprocess_exec(
            self._command,
            "-Scan",
            "-ScanType",
            "3",
            "-File",
            str(path),
            "-DisableRemediation",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            return_code = await asyncio.wait_for(process.wait(), timeout=self._timeout)
        except TimeoutError:
            process.kill()
            await process.wait()
            return ScanResult("error")
        if return_code == 0:
            return ScanResult("clean")
        if return_code == 2:
            return ScanResult("infected")
        return ScanResult("error")


def malware_scanner(settings: Settings) -> MalwareScanner:
    if settings.FILE_MALWARE_SCANNER == "noop":
        return NoopDevelopmentScanner()
    if settings.FILE_MALWARE_SCANNER == "clamav":
        return ClamAvScanner(
            settings.CLAMAV_HOST,
            settings.CLAMAV_PORT,
            settings.FILE_SCAN_TIMEOUT_SECONDS,
        )
    if settings.FILE_MALWARE_SCANNER == "defender":
        return DefenderScanner(
            settings.DEFENDER_COMMAND,
            settings.FILE_SCAN_TIMEOUT_SECONDS,
        )
    raise RuntimeError("The configured malware scanner is unavailable")
