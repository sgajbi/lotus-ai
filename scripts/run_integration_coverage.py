from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    integration_dir = repo_root / "tests" / "integration"
    test_files = sorted(integration_dir.glob("test_*.py"))
    if not test_files:
        print("No integration test files found.")
        return 1

    for index, test_file in enumerate(test_files):
        command = [
            sys.executable,
            "-m",
            "pytest",
            str(test_file),
            "--cov=src",
            "--cov-report=",
        ]
        if index > 0:
            command.append("--cov-append")

        print(f"[integration-coverage] Running {test_file.relative_to(repo_root)}")
        completed = subprocess.run(command, cwd=repo_root, check=False)
        if completed.returncode != 0:
            return completed.returncode

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
