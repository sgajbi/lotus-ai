from __future__ import annotations

from pathlib import Path

from scripts import dependency_health_check


def test_build_audit_command_uses_sorted_temporary_ignores() -> None:
    python_bin = Path("C:/tmp/python.exe")

    command = dependency_health_check._build_audit_command(python_bin)

    assert command[:3] == [str(python_bin), "-m", "pip_audit"]
    assert command[3:] == [
        "--ignore-vuln",
        "CVE-2026-4539",
        "--ignore-vuln",
        "PYSEC-2026-161",
    ]


def test_venv_python_uses_expected_windows_layout() -> None:
    venv_path = Path("C:/tmp/lotus-ai-venv")

    python_bin = dependency_health_check._venv_python(venv_path)

    assert python_bin == venv_path / "Scripts" / "python.exe"
