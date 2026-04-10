from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import tempfile
import venv
from pathlib import Path

_TEMPORARY_IGNORED_VULNERABILITIES = {
    # No patched Pygments release is available yet on PyPI. Remove this exception immediately
    # once the upstream release exists so the audit returns to a strict zero-ignore posture.
    "CVE-2026-4539",
}


def _venv_python(venv_path: Path) -> Path:
    scripts_dir = "Scripts" if os.name == "nt" else "bin"
    executable_name = "python.exe" if os.name == "nt" else "python"
    return venv_path / scripts_dir / executable_name


def _run(command: list[str], *, cwd: Path, env: dict[str, str]) -> None:
    subprocess.run(command, cwd=cwd, env=env, check=True)


def _build_audit_command(python_bin: Path) -> list[str]:
    audit_command = [str(python_bin), "-m", "pip_audit"]
    for vulnerability_id in sorted(_TEMPORARY_IGNORED_VULNERABILITIES):
        audit_command.extend(["--ignore-vuln", vulnerability_id])
    return audit_command


def main() -> int:
    parser = argparse.ArgumentParser(description="Project-scoped dependency and security checks")
    parser.add_argument(
        "--skip-audit", action="store_true", help="Skip vulnerability audit and only run pip check"
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    temp_dir = Path(tempfile.mkdtemp(prefix="lotus-ai-dependency-health-"))
    venv_path = temp_dir / "venv"
    env = os.environ.copy()
    env["PIP_NO_CACHE_DIR"] = "1"
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"

    try:
        venv.EnvBuilder(with_pip=True).create(venv_path)
        python_bin = _venv_python(venv_path)

        _run([str(python_bin), "-m", "pip", "install", "--upgrade", "pip"], cwd=repo_root, env=env)
        _run([str(python_bin), "-m", "pip", "install", "-e", ".[dev]"], cwd=repo_root, env=env)
        _run([str(python_bin), "-m", "pip", "check"], cwd=repo_root, env=env)

        if not args.skip_audit:
            _run(_build_audit_command(python_bin), cwd=repo_root, env=env)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
