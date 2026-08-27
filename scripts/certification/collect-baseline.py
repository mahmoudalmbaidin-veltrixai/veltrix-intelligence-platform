"""Collect a secret-free certification baseline snapshot."""
from __future__ import annotations

import json
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    return (result.stdout or result.stderr).strip()


def http_json(url: str) -> dict | None:
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def main() -> None:
    snapshot = {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
        "sha": git("rev-parse", "HEAD"),
        "status_short": git("status", "-sb"),
        "health": http_json("http://localhost:8000/health"),
        "ready": http_json("http://localhost:8000/ready"),
        "version": http_json("http://localhost:8000/api/v1/version"),
    }
    print(json.dumps(snapshot, indent=2))


if __name__ == "__main__":
    main()
