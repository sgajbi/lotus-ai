from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

from app.contracts.evals import EvaluationRunArtifactDescriptor
from app.evals.fixture_manifest import load_evaluation_fixture_manifest


class EvaluationRunArtifactValidationError(ValueError):
    """Raised when the governed evaluation run artifact registry is malformed."""


@lru_cache(maxsize=1)
def load_evaluation_run_artifacts() -> list[EvaluationRunArtifactDescriptor]:
    repo_root = Path(__file__).resolve().parents[3]
    run_manifest_path = repo_root / "docs" / "evals" / "run-artifacts.json"
    with run_manifest_path.open("r", encoding="utf-8") as run_manifest_file:
        payload = json.load(run_manifest_file)
    validate_evaluation_run_artifacts(repo_root=repo_root, run_manifest_payload=payload)
    runs = payload.get("runs", [])
    return [EvaluationRunArtifactDescriptor(**run) for run in runs]


def validate_evaluation_run_artifacts(
    *,
    repo_root: Path,
    run_manifest_payload: dict[str, Any],
) -> None:
    runs = run_manifest_payload.get("runs")
    if not isinstance(runs, list):
        raise EvaluationRunArtifactValidationError(
            "Evaluation run artifact registry must define runs as a list."
        )

    fixture_manifest = load_evaluation_fixture_manifest()
    manifest_version = fixture_manifest.manifest_version
    expected_fixture_ids = {fixture.fixture_id for fixture in fixture_manifest.fixture_families}
    run_ids: set[str] = set()

    for run in runs:
        if not isinstance(run, dict):
            raise EvaluationRunArtifactValidationError(
                "Each evaluation run artifact entry must be an object."
            )
        run_id = run.get("run_id")
        _require_non_empty_string(run_id, field_name="runs[].run_id")
        run_id = cast(str, run_id)
        if run_id in run_ids:
            raise EvaluationRunArtifactValidationError(
                f"Duplicate evaluation run artifact id '{run_id}'."
            )
        run_ids.add(run_id)

        _require_non_empty_string(run.get("recorded_at"), field_name=f"{run_id}.recorded_at")
        _require_non_empty_string(run.get("notes"), field_name=f"{run_id}.notes")
        if run.get("manifest_version") != manifest_version:
            raise EvaluationRunArtifactValidationError(
                f"Evaluation run artifact '{run_id}' references manifest version "
                f"'{run.get('manifest_version')}' but current manifest version is '{manifest_version}'."
            )

        seam_coverage = run.get("seam_coverage")
        if not isinstance(seam_coverage, list):
            raise EvaluationRunArtifactValidationError(
                f"Evaluation run artifact '{run_id}' must define seam_coverage as a list."
            )

        seam_ids: set[str] = set()
        staged_fixture_count = 0
        staged_case_count = 0
        for seam in seam_coverage:
            if not isinstance(seam, dict):
                raise EvaluationRunArtifactValidationError(
                    f"Evaluation run artifact '{run_id}' contains a non-object seam coverage entry."
                )
            seam_id = seam.get("seam_id")
            _require_non_empty_string(seam_id, field_name=f"{run_id}.seam_coverage[].seam_id")
            seam_id = cast(str, seam_id)
            if seam_id in seam_ids:
                raise EvaluationRunArtifactValidationError(
                    f"Evaluation run artifact '{run_id}' contains duplicate seam_id '{seam_id}'."
                )
            seam_ids.add(seam_id)

            fixture_ids = seam.get("fixture_ids")
            if not isinstance(fixture_ids, list):
                raise EvaluationRunArtifactValidationError(
                    f"Evaluation run artifact '{run_id}' seam '{seam_id}' must define fixture_ids as a list."
                )
            for fixture_id in fixture_ids:
                _require_non_empty_string(
                    fixture_id,
                    field_name=f"{run_id}.{seam_id}.fixture_ids[]",
                )
                if fixture_id not in expected_fixture_ids:
                    raise EvaluationRunArtifactValidationError(
                        f"Evaluation run artifact '{run_id}' seam '{seam_id}' references unknown fixture id '{fixture_id}'."
                    )

            seam_fixture_count = seam.get("staged_fixture_count")
            seam_case_count = seam.get("staged_case_count")
            _require_non_negative_int(
                seam_fixture_count,
                field_name=f"{run_id}.{seam_id}.staged_fixture_count",
            )
            _require_non_negative_int(
                seam_case_count,
                field_name=f"{run_id}.{seam_id}.staged_case_count",
            )
            seam_fixture_count = cast(int, seam_fixture_count)
            seam_case_count = cast(int, seam_case_count)
            if seam_fixture_count != len(fixture_ids):
                raise EvaluationRunArtifactValidationError(
                    f"Evaluation run artifact '{run_id}' seam '{seam_id}' has staged_fixture_count "
                    f"{seam_fixture_count} but references {len(fixture_ids)} fixture ids."
                )
            staged_fixture_count += seam_fixture_count
            staged_case_count += seam_case_count

        _require_non_negative_int(
            run.get("staged_fixture_count"),
            field_name=f"{run_id}.staged_fixture_count",
        )
        _require_non_negative_int(
            run.get("staged_case_count"),
            field_name=f"{run_id}.staged_case_count",
        )
        if run["staged_fixture_count"] != staged_fixture_count:
            raise EvaluationRunArtifactValidationError(
                f"Evaluation run artifact '{run_id}' has staged_fixture_count "
                f"{run['staged_fixture_count']} but seam coverage totals {staged_fixture_count}."
            )
        if run["staged_case_count"] != staged_case_count:
            raise EvaluationRunArtifactValidationError(
                f"Evaluation run artifact '{run_id}' has staged_case_count "
                f"{run['staged_case_count']} but seam coverage totals {staged_case_count}."
            )


def _require_non_empty_string(value: Any, *, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise EvaluationRunArtifactValidationError(
            f"Evaluation run artifact field '{field_name}' must be a non-empty string."
        )


def _require_non_negative_int(value: Any, *, field_name: str) -> None:
    if not isinstance(value, int) or value < 0:
        raise EvaluationRunArtifactValidationError(
            f"Evaluation run artifact field '{field_name}' must be a non-negative integer."
        )
