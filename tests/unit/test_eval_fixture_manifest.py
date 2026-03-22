from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from app.contracts.evals import EvaluationAssetStatus, EvaluationFixtureDescriptor
from app.evals.fixture_manifest import (
    EvaluationFixtureManifest,
    EvaluationFixtureManifestValidationError,
    load_evaluation_fixture_manifest,
    load_evaluation_fixture_family,
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


def test_load_evaluation_fixture_manifest_returns_governed_fixture_inventory() -> None:
    manifest = load_evaluation_fixture_manifest()

    assert manifest.manifest_version == "foundation.v1"
    assert any(category.category_id == "task_contract" for category in manifest.evidence_categories)
    assert any(
        fixture.fixture_id == "explanation_task_examples" and fixture.case_count == 2
        for fixture in manifest.fixture_families
    )


def test_load_evaluation_fixture_family_returns_case_summaries_for_known_fixture() -> None:
    family = load_evaluation_fixture_family(fixture_id="explanation_task_examples")

    assert family.descriptor.fixture_id == "explanation_task_examples"
    assert family.task_id == "explain.v1"
    assert [case.case_id for case in family.cases] == [
        "explain_blocked_rebalance",
        "explain_pending_review",
    ]


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


def test_validate_evaluation_fixture_manifest_rejects_blank_manifest_version() -> None:
    repo_root = Path(__file__).resolve().parents[2]

    with pytest.raises(
        EvaluationFixtureManifestValidationError,
        match="manifest_version",
    ):
        validate_evaluation_fixture_manifest(
            repo_root=repo_root,
            manifest_payload={
                "manifest_version": "  ",
                "evidence_categories": [],
                "fixture_families": [],
            },
        )


def test_validate_evaluation_fixture_manifest_rejects_non_list_categories() -> None:
    repo_root = Path(__file__).resolve().parents[2]

    with pytest.raises(
        EvaluationFixtureManifestValidationError,
        match="evidence_categories as a list",
    ):
        validate_evaluation_fixture_manifest(
            repo_root=repo_root,
            manifest_payload={
                "manifest_version": "foundation.v1",
                "evidence_categories": {},
                "fixture_families": [],
            },
        )


def test_validate_evaluation_fixture_manifest_rejects_duplicate_category_ids() -> None:
    repo_root = Path(__file__).resolve().parents[2]

    with pytest.raises(
        EvaluationFixtureManifestValidationError,
        match="Duplicate evidence category id",
    ):
        validate_evaluation_fixture_manifest(
            repo_root=repo_root,
            manifest_payload={
                "manifest_version": "foundation.v1",
                "evidence_categories": [
                    {"category_id": "task_contract", "description": "One."},
                    {"category_id": "task_contract", "description": "Two."},
                ],
                "fixture_families": [],
            },
        )


def test_validate_evaluation_fixture_manifest_rejects_non_object_category_entry() -> None:
    repo_root = Path(__file__).resolve().parents[2]

    with pytest.raises(
        EvaluationFixtureManifestValidationError,
        match="evidence_categories entry must be an object",
    ):
        validate_evaluation_fixture_manifest(
            repo_root=repo_root,
            manifest_payload={
                "manifest_version": "foundation.v1",
                "evidence_categories": ["bad-entry"],
                "fixture_families": [],
            },
        )


def test_validate_evaluation_fixture_manifest_rejects_duplicate_fixture_ids() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    manifest_path = "docs/evals/fixtures/explain.v1/basic_cases.json"

    with pytest.raises(
        EvaluationFixtureManifestValidationError,
        match="Duplicate fixture family id",
    ):
        validate_evaluation_fixture_manifest(
            repo_root=repo_root,
            manifest_payload={
                "manifest_version": "foundation.v1",
                "evidence_categories": [
                    {"category_id": "task_contract", "description": "Bounded task evidence."}
                ],
                "fixture_families": [
                    {
                        "fixture_id": "explanation_task_examples",
                        "status": "STAGED",
                        "description": "One.",
                        "manifest_path": manifest_path,
                    },
                    {
                        "fixture_id": "explanation_task_examples",
                        "status": "STAGED",
                        "description": "Two.",
                        "manifest_path": manifest_path,
                    },
                ],
            },
        )


def test_validate_evaluation_fixture_manifest_rejects_non_object_fixture_entry() -> None:
    repo_root = Path(__file__).resolve().parents[2]

    with pytest.raises(
        EvaluationFixtureManifestValidationError,
        match="fixture_families entry must be an object",
    ):
        validate_evaluation_fixture_manifest(
            repo_root=repo_root,
            manifest_payload={
                "manifest_version": "foundation.v1",
                "evidence_categories": [
                    {"category_id": "task_contract", "description": "Bounded task evidence."}
                ],
                "fixture_families": ["bad-entry"],
            },
        )


def test_validate_evaluation_fixture_manifest_rejects_staged_fixture_without_path() -> None:
    repo_root = Path(__file__).resolve().parents[2]

    with pytest.raises(
        EvaluationFixtureManifestValidationError,
        match="must define manifest_path",
    ):
        validate_evaluation_fixture_manifest(
            repo_root=repo_root,
            manifest_payload={
                "manifest_version": "foundation.v1",
                "evidence_categories": [
                    {"category_id": "task_contract", "description": "Bounded task evidence."}
                ],
                "fixture_families": [
                    {
                        "fixture_id": "explanation_task_examples",
                        "status": "STAGED",
                        "description": "Golden examples.",
                    }
                ],
            },
        )


def test_validate_evaluation_fixture_manifest_rejects_fixture_file_with_mismatched_family(
    tmp_path: Path,
) -> None:
    fixture_path = tmp_path / "fixture.json"
    fixture_path.write_text(
        """
        {
          "task_id": "explain.v1",
          "fixture_family": "different_fixture",
          "cases": [
            {
              "case_id": "case_1",
              "summary": "Summary",
              "input": {},
              "expected": {}
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    with pytest.raises(
        EvaluationFixtureManifestValidationError,
        match="declares fixture_family",
    ):
        validate_evaluation_fixture_manifest(
            repo_root=tmp_path,
            manifest_payload={
                "manifest_version": "foundation.v1",
                "evidence_categories": [
                    {"category_id": "task_contract", "description": "Bounded task evidence."}
                ],
                "fixture_families": [
                    {
                        "fixture_id": "expected_fixture",
                        "status": "STAGED",
                        "description": "Golden examples.",
                        "manifest_path": "fixture.json",
                    }
                ],
            },
        )


def test_validate_evaluation_fixture_manifest_rejects_fixture_file_with_duplicate_case_ids(
    tmp_path: Path,
) -> None:
    fixture_path = tmp_path / "fixture.json"
    fixture_path.write_text(
        """
        {
          "task_id": "explain.v1",
          "fixture_family": "expected_fixture",
          "cases": [
            {
              "case_id": "case_1",
              "summary": "Summary one",
              "input": {},
              "expected": {}
            },
            {
              "case_id": "case_1",
              "summary": "Summary two",
              "input": {},
              "expected": {}
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    with pytest.raises(
        EvaluationFixtureManifestValidationError,
        match="duplicate case_id",
    ):
        validate_evaluation_fixture_manifest(
            repo_root=tmp_path,
            manifest_payload={
                "manifest_version": "foundation.v1",
                "evidence_categories": [
                    {"category_id": "task_contract", "description": "Bounded task evidence."}
                ],
                "fixture_families": [
                    {
                        "fixture_id": "expected_fixture",
                        "status": "STAGED",
                        "description": "Golden examples.",
                        "manifest_path": "fixture.json",
                    }
                ],
            },
        )


def test_validate_evaluation_fixture_manifest_rejects_fixture_case_without_object_input(
    tmp_path: Path,
) -> None:
    fixture_path = tmp_path / "fixture.json"
    fixture_path.write_text(
        """
        {
          "task_id": "explain.v1",
          "fixture_family": "expected_fixture",
          "cases": [
            {
              "case_id": "case_1",
              "summary": "Summary",
              "input": [],
              "expected": {}
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    with pytest.raises(
        EvaluationFixtureManifestValidationError,
        match="must define input as an object",
    ):
        validate_evaluation_fixture_manifest(
            repo_root=tmp_path,
            manifest_payload={
                "manifest_version": "foundation.v1",
                "evidence_categories": [
                    {"category_id": "task_contract", "description": "Bounded task evidence."}
                ],
                "fixture_families": [
                    {
                        "fixture_id": "expected_fixture",
                        "status": "STAGED",
                        "description": "Golden examples.",
                        "manifest_path": "fixture.json",
                    }
                ],
            },
        )


def test_validate_evaluation_fixture_manifest_rejects_fixture_file_with_non_list_cases(
    tmp_path: Path,
) -> None:
    fixture_path = tmp_path / "fixture.json"
    fixture_path.write_text(
        """
        {
          "task_id": "explain.v1",
          "fixture_family": "expected_fixture",
          "cases": {}
        }
        """,
        encoding="utf-8",
    )

    with pytest.raises(
        EvaluationFixtureManifestValidationError,
        match="must define cases as a list",
    ):
        validate_evaluation_fixture_manifest(
            repo_root=tmp_path,
            manifest_payload={
                "manifest_version": "foundation.v1",
                "evidence_categories": [
                    {"category_id": "task_contract", "description": "Bounded task evidence."}
                ],
                "fixture_families": [
                    {
                        "fixture_id": "expected_fixture",
                        "status": "STAGED",
                        "description": "Golden examples.",
                        "manifest_path": "fixture.json",
                    }
                ],
            },
        )


def test_validate_evaluation_fixture_manifest_rejects_non_object_case_entry(
    tmp_path: Path,
) -> None:
    fixture_path = tmp_path / "fixture.json"
    fixture_path.write_text(
        """
        {
          "task_id": "explain.v1",
          "fixture_family": "expected_fixture",
          "cases": ["bad-case"]
        }
        """,
        encoding="utf-8",
    )

    with pytest.raises(
        EvaluationFixtureManifestValidationError,
        match="contains a non-object case entry",
    ):
        validate_evaluation_fixture_manifest(
            repo_root=tmp_path,
            manifest_payload={
                "manifest_version": "foundation.v1",
                "evidence_categories": [
                    {"category_id": "task_contract", "description": "Bounded task evidence."}
                ],
                "fixture_families": [
                    {
                        "fixture_id": "expected_fixture",
                        "status": "STAGED",
                        "description": "Golden examples.",
                        "manifest_path": "fixture.json",
                    }
                ],
            },
        )


def test_validate_evaluation_fixture_manifest_rejects_fixture_case_without_object_expected(
    tmp_path: Path,
) -> None:
    fixture_path = tmp_path / "fixture.json"
    fixture_path.write_text(
        """
        {
          "task_id": "explain.v1",
          "fixture_family": "expected_fixture",
          "cases": [
            {
              "case_id": "case_1",
              "summary": "Summary",
              "input": {},
              "expected": []
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    with pytest.raises(
        EvaluationFixtureManifestValidationError,
        match="must define expected as an object",
    ):
        validate_evaluation_fixture_manifest(
            repo_root=tmp_path,
            manifest_payload={
                "manifest_version": "foundation.v1",
                "evidence_categories": [
                    {"category_id": "task_contract", "description": "Bounded task evidence."}
                ],
                "fixture_families": [
                    {
                        "fixture_id": "expected_fixture",
                        "status": "STAGED",
                        "description": "Golden examples.",
                        "manifest_path": "fixture.json",
                    }
                ],
            },
        )


def test_load_evaluation_fixture_family_rejects_unknown_fixture_id() -> None:
    with pytest.raises(
        EvaluationFixtureManifestValidationError,
        match="Unknown evaluation fixture family 'missing_fixture'",
    ):
        load_evaluation_fixture_family(fixture_id="missing_fixture")


def test_load_evaluation_fixture_family_returns_empty_detail_for_documented_fixture() -> None:
    manifest = EvaluationFixtureManifest(
        manifest_version="foundation.v1",
        evidence_categories=[],
        fixture_families=[
            EvaluationFixtureDescriptor(
                fixture_id="documented_only_fixture",
                status=EvaluationAssetStatus.DOCUMENTED,
                description="Documented-only fixture family.",
                manifest_path=None,
                case_count=0,
            )
        ],
    )

    with patch(
        "app.evals.fixture_manifest.load_evaluation_fixture_manifest", return_value=manifest
    ):
        family = load_evaluation_fixture_family(fixture_id="documented_only_fixture")

    assert family.task_id is None
    assert family.cases == []


def test_load_evaluation_fixture_family_rejects_non_list_case_payload(tmp_path: Path) -> None:
    fixture_path = tmp_path / "fixture.json"
    fixture_path.write_text(
        """
        {
          "task_id": "explain.v1",
          "fixture_family": "bad_fixture",
          "cases": {}
        }
        """,
        encoding="utf-8",
    )
    manifest = EvaluationFixtureManifest(
        manifest_version="foundation.v1",
        evidence_categories=[],
        fixture_families=[
            EvaluationFixtureDescriptor(
                fixture_id="bad_fixture",
                status=EvaluationAssetStatus.STAGED,
                description="Malformed fixture family.",
                manifest_path=str(fixture_path.relative_to(tmp_path)),
                case_count=0,
            )
        ],
    )

    with (
        patch(
            "app.evals.fixture_manifest.Path.resolve",
            return_value=tmp_path / "src" / "app" / "evals" / "fixture_manifest.py",
        ),
        patch("app.evals.fixture_manifest.load_evaluation_fixture_manifest", return_value=manifest),
    ):
        with pytest.raises(
            EvaluationFixtureManifestValidationError,
            match="non-list cases payload",
        ):
            load_evaluation_fixture_family(fixture_id="bad_fixture")
