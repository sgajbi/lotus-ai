from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

ALEMBIC_DIR = Path("alembic")
VERSIONS_DIR = ALEMBIC_DIR / "versions"
REQUIRED_DOC = Path("docs/standards/migration-contract.md")


def _default_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("LOTUS_AI_DATABASE_URL", "sqlite:///:memory:")
    env.setdefault("DATABASE_URL", env["LOTUS_AI_DATABASE_URL"])
    return env


def _run(command: list[str]) -> int:
    result = subprocess.run(command, check=False, env=_default_env())
    return result.returncode


def _has_single_head() -> bool:
    result = subprocess.run(
        ["python", "-m", "alembic", "heads"],
        check=False,
        capture_output=True,
        text=True,
        env=_default_env(),
    )
    if result.returncode != 0:
        return False
    heads = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if len(heads) != 1:
        print("Expected exactly one Alembic head, found:")
        for head in heads:
            print(f" - {head}")
        return False
    return True


def run_alembic_sql_smoke() -> int:
    if not ALEMBIC_DIR.exists() or not VERSIONS_DIR.exists():
        print("Missing Alembic migration directories.")
        return 1
    if not any(VERSIONS_DIR.glob("*.py")):
        print("No Alembic migration revision files found.")
        return 1
    if not REQUIRED_DOC.exists():
        print(f"Missing required migration contract document: {REQUIRED_DOC}")
        return 1
    if not _has_single_head():
        return 1
    if _run(["python", "-m", "alembic", "history"]) != 0:
        return 1
    if _run(["python", "-m", "alembic", "upgrade", "head", "--sql"]) != 0:
        return 1
    print("Migration contract check passed (alembic-sql mode).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate migration contract requirements.")
    parser.add_argument("--mode", choices=["alembic-sql"], default="alembic-sql")
    args = parser.parse_args()
    if args.mode == "alembic-sql":
        return run_alembic_sql_smoke()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
