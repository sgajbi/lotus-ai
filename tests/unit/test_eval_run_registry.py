from __future__ import annotations

from pathlib import Path

import pytest

from app.evals.run_registry import (
    EvaluationRunArtifactValidationError,
    validate_evaluation_run_artifacts,
)


def test_validate_evaluation_run_artifacts_accepts_current_shape() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    payload = {
        "runs": [
            {
                "run_id": "foundation_eval_2026_03_22_001",
                "recorded_at": "2026-03-22T09:00:00Z",
                "status": "RECORDED",
                "manifest_version": "foundation.v1",
                "staged_fixture_count": 1,
                "staged_case_count": 2,
                "seam_coverage": [
                    {
                        "seam_id": "retrieval",
                        "fixture_ids": ["retrieval_citation_examples"],
                        "staged_fixture_count": 1,
                        "staged_case_count": 2,
                    }
                ],
                "notes": "Seeded baseline evaluation run artifact.",
            }
        ]
    }

    validate_evaluation_run_artifacts(repo_root=repo_root, run_manifest_payload=payload)


def test_validate_evaluation_run_artifacts_rejects_unknown_fixture_ids() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    payload = {
        "runs": [
            {
                "run_id": "foundation_eval_invalid_fixture",
                "recorded_at": "2026-03-22T09:00:00Z",
                "status": "RECORDED",
                "manifest_version": "foundation.v1",
                "staged_fixture_count": 1,
                "staged_case_count": 2,
                "seam_coverage": [
                    {
                        "seam_id": "retrieval",
                        "fixture_ids": ["missing_fixture"],
                        "staged_fixture_count": 1,
                        "staged_case_count": 2,
                    }
                ],
                "notes": "Invalid fixture reference.",
            }
        ]
    }

    with pytest.raises(EvaluationRunArtifactValidationError, match="unknown fixture id"):
        validate_evaluation_run_artifacts(repo_root=repo_root, run_manifest_payload=payload)


def test_validate_evaluation_run_artifacts_rejects_mismatched_totals() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    payload = {
        "runs": [
            {
                "run_id": "foundation_eval_invalid_totals",
                "recorded_at": "2026-03-22T09:00:00Z",
                "status": "RECORDED",
                "manifest_version": "foundation.v1",
                "staged_fixture_count": 2,
                "staged_case_count": 2,
                "seam_coverage": [
                    {
                        "seam_id": "retrieval",
                        "fixture_ids": ["retrieval_citation_examples"],
                        "staged_fixture_count": 1,
                        "staged_case_count": 2,
                    }
                ],
                "notes": "Invalid staged fixture total.",
            }
        ]
    }

    with pytest.raises(EvaluationRunArtifactValidationError, match="seam coverage totals 1"):
        validate_evaluation_run_artifacts(repo_root=repo_root, run_manifest_payload=payload)
