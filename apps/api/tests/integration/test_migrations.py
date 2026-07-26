"""Alembic upgrade, downgrade, and head validation against the test database."""

import os
import sys
from pathlib import Path
from subprocess import run

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.engine import make_url


@pytest.mark.integration
def test_alembic_clean_upgrade_and_current_head() -> None:
    database_name = make_url(os.environ["DATABASE_URL"]).database or ""
    assert database_name.endswith("_test"), "migration tests require a dedicated *_test database"
    root = Path(__file__).parents[2]
    config = Config(root / "alembic.ini")
    command.downgrade(config, "base")
    command.upgrade(config, "head")

    head = ScriptDirectory.from_config(config).get_current_head()
    result = run(
        [sys.executable, "-m", "alembic", "current"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    assert head is not None
    assert head in result.stdout
