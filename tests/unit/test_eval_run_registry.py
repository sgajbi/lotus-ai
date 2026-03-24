from __future__ import annotations

from pathlib import Path

import pytest

from app.evals.run_registry import (
    EvaluationRunArtifactValidationError,
    load_evaluation_run_artifacts,
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
            },
            {
                "run_id": "foundation_eval_2026_03_21_001",
                "recorded_at": "2026-03-21T09:00:00Z",
                "status": "SUPERSEDED",
                "manifest_version": "foundation.v1",
                "staged_fixture_count": 0,
                "staged_case_count": 0,
                "seam_coverage": [
                    {
                        "seam_id": "safety_policy",
                        "fixture_ids": [],
                        "staged_fixture_count": 0,
                        "staged_case_count": 0,
                    }
                ],
                "notes": "Seeded superseded evaluation run artifact.",
            },
        ]
    }

    validate_evaluation_run_artifacts(repo_root=repo_root, run_manifest_payload=payload)


def test_load_evaluation_run_artifacts_returns_seeded_run_inventory() -> None:
    runs = load_evaluation_run_artifacts()

    assert runs[0].run_id == "foundation_eval_2026_03_22_001"
    assert runs[0].staged_case_count == 34
    assert runs[1].status == "SUPERSEDED"


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


def test_validate_evaluation_run_artifacts_rejects_non_list_runs() -> None:
    repo_root = Path(__file__).resolve().parents[2]

    with pytest.raises(EvaluationRunArtifactValidationError, match="runs as a list"):
        validate_evaluation_run_artifacts(
            repo_root=repo_root,
            run_manifest_payload={"runs": {}},
        )


def test_validate_evaluation_run_artifacts_rejects_duplicate_run_ids() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    run = {
        "run_id": "duplicate_run",
        "recorded_at": "2026-03-22T09:00:00Z",
        "status": "RECORDED",
        "manifest_version": "foundation.v1",
        "staged_fixture_count": 0,
        "staged_case_count": 0,
        "seam_coverage": [],
        "notes": "Duplicate id.",
    }

    with pytest.raises(
        EvaluationRunArtifactValidationError, match="Duplicate evaluation run artifact id"
    ):
        validate_evaluation_run_artifacts(
            repo_root=repo_root,
            run_manifest_payload={"runs": [run, run]},
        )


def test_validate_evaluation_run_artifacts_rejects_manifest_version_mismatch() -> None:
    repo_root = Path(__file__).resolve().parents[2]

    with pytest.raises(EvaluationRunArtifactValidationError, match="current manifest version is"):
        validate_evaluation_run_artifacts(
            repo_root=repo_root,
            run_manifest_payload={
                "runs": [
                    {
                        "run_id": "bad_manifest_version",
                        "recorded_at": "2026-03-22T09:00:00Z",
                        "status": "RECORDED",
                        "manifest_version": "foundation.v0",
                        "staged_fixture_count": 0,
                        "staged_case_count": 0,
                        "seam_coverage": [],
                        "notes": "Version mismatch.",
                    }
                ]
            },
        )


def test_validate_evaluation_run_artifacts_rejects_duplicate_seam_ids() -> None:
    repo_root = Path(__file__).resolve().parents[2]

    with pytest.raises(EvaluationRunArtifactValidationError, match="duplicate seam_id"):
        validate_evaluation_run_artifacts(
            repo_root=repo_root,
            run_manifest_payload={
                "runs": [
                    {
                        "run_id": "duplicate_seam",
                        "recorded_at": "2026-03-22T09:00:00Z",
                        "status": "RECORDED",
                        "manifest_version": "foundation.v1",
                        "staged_fixture_count": 0,
                        "staged_case_count": 0,
                        "seam_coverage": [
                            {
                                "seam_id": "retrieval",
                                "fixture_ids": [],
                                "staged_fixture_count": 0,
                                "staged_case_count": 0,
                            },
                            {
                                "seam_id": "retrieval",
                                "fixture_ids": [],
                                "staged_fixture_count": 0,
                                "staged_case_count": 0,
                            },
                        ],
                        "notes": "Duplicate seam ids.",
                    }
                ]
            },
        )


def test_validate_evaluation_run_artifacts_rejects_non_list_fixture_ids() -> None:
    repo_root = Path(__file__).resolve().parents[2]

    with pytest.raises(EvaluationRunArtifactValidationError, match="fixture_ids as a list"):
        validate_evaluation_run_artifacts(
            repo_root=repo_root,
            run_manifest_payload={
                "runs": [
                    {
                        "run_id": "bad_fixture_ids",
                        "recorded_at": "2026-03-22T09:00:00Z",
                        "status": "RECORDED",
                        "manifest_version": "foundation.v1",
                        "staged_fixture_count": 0,
                        "staged_case_count": 0,
                        "seam_coverage": [
                            {
                                "seam_id": "retrieval",
                                "fixture_ids": "not-a-list",
                                "staged_fixture_count": 0,
                                "staged_case_count": 0,
                            }
                        ],
                        "notes": "Invalid fixture ids shape.",
                    }
                ]
            },
        )


def test_validate_evaluation_run_artifacts_rejects_non_object_run_entry() -> None:
    repo_root = Path(__file__).resolve().parents[2]

    with pytest.raises(EvaluationRunArtifactValidationError, match="must be an object"):
        validate_evaluation_run_artifacts(
            repo_root=repo_root,
            run_manifest_payload={"runs": ["bad-run"]},
        )


def test_validate_evaluation_run_artifacts_rejects_non_list_seam_coverage() -> None:
    repo_root = Path(__file__).resolve().parents[2]

    with pytest.raises(EvaluationRunArtifactValidationError, match="seam_coverage as a list"):
        validate_evaluation_run_artifacts(
            repo_root=repo_root,
            run_manifest_payload={
                "runs": [
                    {
                        "run_id": "bad_seam_coverage",
                        "recorded_at": "2026-03-22T09:00:00Z",
                        "status": "RECORDED",
                        "manifest_version": "foundation.v1",
                        "staged_fixture_count": 0,
                        "staged_case_count": 0,
                        "seam_coverage": {},
                        "notes": "Invalid seam coverage shape.",
                    }
                ]
            },
        )


def test_validate_evaluation_run_artifacts_rejects_non_object_seam_entry() -> None:
    repo_root = Path(__file__).resolve().parents[2]

    with pytest.raises(EvaluationRunArtifactValidationError, match="non-object seam coverage"):
        validate_evaluation_run_artifacts(
            repo_root=repo_root,
            run_manifest_payload={
                "runs": [
                    {
                        "run_id": "bad_seam_entry",
                        "recorded_at": "2026-03-22T09:00:00Z",
                        "status": "RECORDED",
                        "manifest_version": "foundation.v1",
                        "staged_fixture_count": 0,
                        "staged_case_count": 0,
                        "seam_coverage": ["bad-seam"],
                        "notes": "Invalid seam entry.",
                    }
                ]
            },
        )


def test_validate_evaluation_run_artifacts_rejects_mismatched_fixture_count_per_seam() -> None:
    repo_root = Path(__file__).resolve().parents[2]

    with pytest.raises(EvaluationRunArtifactValidationError, match="references 1 fixture ids"):
        validate_evaluation_run_artifacts(
            repo_root=repo_root,
            run_manifest_payload={
                "runs": [
                    {
                        "run_id": "bad_seam_fixture_total",
                        "recorded_at": "2026-03-22T09:00:00Z",
                        "status": "RECORDED",
                        "manifest_version": "foundation.v1",
                        "staged_fixture_count": 2,
                        "staged_case_count": 2,
                        "seam_coverage": [
                            {
                                "seam_id": "retrieval",
                                "fixture_ids": ["retrieval_citation_examples"],
                                "staged_fixture_count": 2,
                                "staged_case_count": 2,
                            }
                        ],
                        "notes": "Invalid seam fixture count.",
                    }
                ]
            },
        )


def test_validate_evaluation_run_artifacts_rejects_negative_case_count() -> None:
    repo_root = Path(__file__).resolve().parents[2]

    with pytest.raises(EvaluationRunArtifactValidationError, match="non-negative integer"):
        validate_evaluation_run_artifacts(
            repo_root=repo_root,
            run_manifest_payload={
                "runs": [
                    {
                        "run_id": "negative_case_count",
                        "recorded_at": "2026-03-22T09:00:00Z",
                        "status": "RECORDED",
                        "manifest_version": "foundation.v1",
                        "staged_fixture_count": 0,
                        "staged_case_count": -1,
                        "seam_coverage": [],
                        "notes": "Invalid staged case count.",
                    }
                ]
            },
        )


def test_validate_evaluation_run_artifacts_rejects_blank_notes() -> None:
    repo_root = Path(__file__).resolve().parents[2]

    with pytest.raises(EvaluationRunArtifactValidationError, match="notes"):
        validate_evaluation_run_artifacts(
            repo_root=repo_root,
            run_manifest_payload={
                "runs": [
                    {
                        "run_id": "blank_notes",
                        "recorded_at": "2026-03-22T09:00:00Z",
                        "status": "RECORDED",
                        "manifest_version": "foundation.v1",
                        "staged_fixture_count": 0,
                        "staged_case_count": 0,
                        "seam_coverage": [],
                        "notes": " ",
                    }
                ]
            },
        )
