from __future__ import annotations

from pathlib import Path

import pytest

from app.evals.fixture_manifest import (
    EvaluationFixtureManifestValidationError,
    validate_evaluation_fixture_manifest,
)


def test_validate_evaluation_fixture_manifest_accepts_current_repo_manifest() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    manifest_payload = {
        "manifest_version": "foundation.v1",
        "evidence_categories": [
            {
                "category_id": "task_contract",
                "description": "Bounded task contract evidence.",
            }
        ],
        "fixture_families": [
            {
                "fixture_id": "explanation_task_examples",
                "status": "STAGED",
                "description": "Golden examples for explanation-oriented tasks.",
                "manifest_path": "docs/evals/fixtures/explain.v1/basic_cases.json",
            }
        ],
    }

    validate_evaluation_fixture_manifest(
        repo_root=repo_root,
        manifest_payload=manifest_payload,
    )


def test_validate_evaluation_fixture_manifest_rejects_documented_fixture_with_path() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    manifest_payload = {
        "manifest_version": "foundation.v1",
        "evidence_categories": [
            {
                "category_id": "task_contract",
                "description": "Bounded task contract evidence.",
            }
        ],
        "fixture_families": [
            {
                "fixture_id": "summarization_task_examples",
                "status": "DOCUMENTED",
                "description": "Golden examples for summarization-oriented tasks.",
                "manifest_path": "docs/evals/fixtures/summarize.v1/basic_cases.json",
            }
        ],
    }

    with pytest.raises(
        EvaluationFixtureManifestValidationError,
        match="must not define manifest_path",
    ):
        validate_evaluation_fixture_manifest(
            repo_root=repo_root,
            manifest_payload=manifest_payload,
        )


def test_validate_evaluation_fixture_manifest_rejects_missing_fixture_file() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    manifest_payload = {
        "manifest_version": "foundation.v1",
        "evidence_categories": [
            {
                "category_id": "task_contract",
                "description": "Bounded task contract evidence.",
            }
        ],
        "fixture_families": [
            {
                "fixture_id": "summarization_task_examples",
                "status": "STAGED",
                "description": "Golden examples for summarization-oriented tasks.",
                "manifest_path": "docs/evals/fixtures/summarize.v1/missing.json",
            }
        ],
    }

    with pytest.raises(
        EvaluationFixtureManifestValidationError,
        match="does not exist",
    ):
        validate_evaluation_fixture_manifest(
            repo_root=repo_root,
            manifest_payload=manifest_payload,
        )
