from __future__ import annotations

import sys

from _repo_imports import ensure_repo_src_first

REPO_ROOT = ensure_repo_src_first(script_file=__file__)


def main() -> int:
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
