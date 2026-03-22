from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"


def main() -> int:
    if str(SRC_ROOT) not in sys.path:
        sys.path.insert(0, str(SRC_ROOT))

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
