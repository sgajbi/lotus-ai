from __future__ import annotations

import subprocess
import sys
from types import SimpleNamespace

import pytest

from scripts import migration_contract_check


def test_migration_contract_uses_the_admitted_python_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[list[str]] = []

    def run(command: list[str], **_: object) -> SimpleNamespace:
        commands.append(command)
        return SimpleNamespace(returncode=0, stdout="0077_example (head)\n")

    monkeypatch.setattr(subprocess, "run", run)

    assert migration_contract_check._has_single_head() is True
    assert migration_contract_check._run([sys.executable, "-m", "alembic", "history"]) == 0
    assert commands == [
        [sys.executable, "-m", "alembic", "heads"],
        [sys.executable, "-m", "alembic", "history"],
    ]
