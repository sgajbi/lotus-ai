from __future__ import annotations

import sys

from _repo_imports import ensure_repo_src_first

REPO_ROOT = ensure_repo_src_first(script_file=__file__)


def main() -> int:
    from app.evals.fixture_manifest import (
        EvaluationFixtureManifestValidationError,
        load_evaluation_fixture_manifest,
    )

    try:
        manifest = load_evaluation_fixture_manifest()
    except EvaluationFixtureManifestValidationError as exc:
        print(f"Evaluation fixture manifest validation failed: {exc}", file=sys.stderr)
        return 1

    print(
        "Evaluation fixture manifest validation passed "
        f"({REPO_ROOT / 'docs' / 'evals' / 'fixture-manifest.json'}; "
        f"{len(manifest.fixture_families)} families, "
        f"{sum(fixture.case_count for fixture in manifest.fixture_families)} staged cases)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
