"""Verify the Alembic migrations run cleanly upgrade->head and downgrade->base
against a fresh SQLite database (in an isolated subprocess so settings/env are
read fresh)."""

import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _run_alembic(args, db_url):
    env = os.environ.copy()
    env["DATABASE_URL"] = db_url
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )


def test_migrations_upgrade_and_downgrade(tmp_path):
    db_file = tmp_path / "migration_test.db"
    db_url = f"sqlite:///{db_file}"

    up = _run_alembic(["upgrade", "head"], db_url)
    assert up.returncode == 0, f"upgrade failed:\n{up.stdout}\n{up.stderr}"
    assert db_file.exists()

    down = _run_alembic(["downgrade", "base"], db_url)
    assert down.returncode == 0, f"downgrade failed:\n{down.stdout}\n{down.stderr}"
