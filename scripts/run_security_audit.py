from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import venv
from pathlib import Path


def _run(command: list[str], *, cwd: Path, env: dict[str, str]) -> None:
    subprocess.run(command, cwd=cwd, env=env, check=True)


def _venv_python(venv_path: Path) -> Path:
    scripts_dir = "Scripts" if os.name == "nt" else "bin"
    return venv_path / scripts_dir / ("python.exe" if os.name == "nt" else "python")


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    temp_dir = Path(tempfile.mkdtemp(prefix="lotus-ai-audit-"))
    venv_path = temp_dir / "venv"
    env = os.environ.copy()
    env["PIP_NO_CACHE_DIR"] = "1"
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"

    try:
        venv.EnvBuilder(with_pip=True).create(venv_path)
        python_bin = _venv_python(venv_path)

        _run([str(python_bin), "-m", "pip", "install", "--upgrade", "pip"], cwd=repo_root, env=env)
        _run([str(python_bin), "-m", "pip", "install", "-e", ".[dev]"], cwd=repo_root, env=env)
        _run([str(python_bin), "-m", "pip_audit"], cwd=repo_root, env=env)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
