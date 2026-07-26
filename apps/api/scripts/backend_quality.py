"""Cross-platform backend quality gate runner."""

from __future__ import annotations

import os
import subprocess
import sys


def run(*command: str) -> None:
    print(f"+ {' '.join(command)}", flush=True)
    # Commands are fixed below; no user-controlled shell input is evaluated.
    subprocess.run(command, check=True)  # noqa: S603


def main() -> int:
    python = sys.executable
    run(python, "-m", "ruff", "check", ".")
    run(python, "-m", "ruff", "format", "--check", ".")
    run(python, "-m", "mypy", "src", "tests")
    run(python, "-m", "pytest", "-m", "not integration")
    if os.getenv("RUN_INTEGRATION_TESTS") == "1":
        run(python, "-m", "alembic", "upgrade", "head")
        run(python, "-m", "pytest", "-m", "integration")
    else:
        print(
            "Integration/migration gate skipped: set RUN_INTEGRATION_TESTS=1 "
            "when services are available."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
