from __future__ import annotations

import sys

from _repo_imports import ensure_repo_src_first

REPO_ROOT = ensure_repo_src_first(script_file=__file__)


def main() -> int:
    from app.evals.run_registry import (
        EvaluationRunArtifactValidationError,
        load_evaluation_run_artifacts,
    )

    try:
        runs = load_evaluation_run_artifacts()
    except EvaluationRunArtifactValidationError as exc:
        print(f"Evaluation run artifact validation failed: {exc}", file=sys.stderr)
        return 1

    print(
        "Evaluation run artifact validation passed "
        f"({REPO_ROOT / 'docs' / 'evals' / 'run-artifacts.json'}; "
        f"{len(runs)} recorded runs)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
