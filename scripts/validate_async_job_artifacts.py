from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"


def main() -> int:
    if str(SRC_ROOT) not in sys.path:
        sys.path.insert(0, str(SRC_ROOT))

    from app.async_runtime.job_registry import (
        AsyncJobArtifactValidationError,
        load_async_job_artifacts,
    )

    try:
        jobs = load_async_job_artifacts()
    except AsyncJobArtifactValidationError as exc:
        print(f"Async job artifact validation failed: {exc}", file=sys.stderr)
        return 1

    print(
        "Async job artifact validation passed "
        f"({REPO_ROOT / 'docs' / 'async' / 'job-artifacts.json'}; "
        f"{len(jobs)} recorded jobs)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
