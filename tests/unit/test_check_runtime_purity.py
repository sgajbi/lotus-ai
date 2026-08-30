"""Runtime purity guard behaviour (issue #148)."""

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_guard() -> ModuleType:
    script_path = Path("scripts") / "check_runtime_purity.py"
    spec = importlib.util.spec_from_file_location("check_runtime_purity", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_runtime_purity_guard_passes_on_current_src() -> None:
    guard = _load_guard()
    assert guard.main("src") == 0


def test_runtime_purity_guard_flags_test_tooling_and_secret_literals(tmp_path: Path) -> None:
    guard = _load_guard()
    (tmp_path / "violations.py").write_text(
        "import unittest\n"
        "from unittest.mock import patch\n"
        "import mock\n"
        "def use(monkeypatch):\n"
        "    monkeypatch.setattr('a', 'b')\n"
        "live_text_provider_api_key = 'sk-secret'\n"
        "settings_api_key: str = 'raw-secret'\n",
        encoding="utf-8",
    )

    violations = guard._violations_for_file(tmp_path / "violations.py")

    assert len(violations) == 7
    assert sum("test-tooling import" in item for item in violations) == 3
    assert sum("'monkeypatch'" in item for item in violations) == 2
    assert sum("secret-shaped api-key literal" in item for item in violations) == 2
    assert guard.main(str(tmp_path)) == 1


def test_runtime_purity_guard_allows_credential_references(tmp_path: Path) -> None:
    guard = _load_guard()
    (tmp_path / "clean.py").write_text(
        "from contextlib import contextmanager\n"
        "live_text_provider_api_key = 'credential-ref:eval-hermetic'\n"
        "provider_api_key = None\n",
        encoding="utf-8",
    )

    assert guard._violations_for_file(tmp_path / "clean.py") == []
    assert guard.main(str(tmp_path)) == 0
