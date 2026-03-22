from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.contracts.evals import (
    EvaluationAssetStatus,
    EvaluationEvidenceCategoryDescriptor,
    EvaluationFixtureCaseDescriptor,
    EvaluationFixtureDescriptor,
)


class EvaluationFixtureManifest:
    def __init__(
        self,
        *,
        manifest_version: str,
        evidence_categories: list[EvaluationEvidenceCategoryDescriptor],
        fixture_families: list[EvaluationFixtureDescriptor],
    ) -> None:
        self.manifest_version = manifest_version
        self.evidence_categories = evidence_categories
        self.fixture_families = fixture_families


class EvaluationFixtureFamily:
    def __init__(
        self,
        *,
        descriptor: EvaluationFixtureDescriptor,
        task_id: str | None,
        cases: list[EvaluationFixtureCaseDescriptor],
    ) -> None:
        self.descriptor = descriptor
        self.task_id = task_id
        self.cases = cases


class EvaluationFixtureManifestValidationError(ValueError):
    """Raised when the governed evaluation fixture manifest is malformed."""


@lru_cache(maxsize=1)
def load_evaluation_fixture_manifest() -> EvaluationFixtureManifest:
    repo_root = Path(__file__).resolve().parents[3]
    manifest_path = repo_root / "docs" / "evals" / "fixture-manifest.json"
    with manifest_path.open("r", encoding="utf-8") as manifest_file:
        payload = json.load(manifest_file)
    validate_evaluation_fixture_manifest(repo_root=repo_root, manifest_payload=payload)
    return EvaluationFixtureManifest(
        manifest_version=payload["manifest_version"],
        evidence_categories=[
            EvaluationEvidenceCategoryDescriptor(**item) for item in payload["evidence_categories"]
        ],
        fixture_families=[
            EvaluationFixtureDescriptor(
                fixture_id=item["fixture_id"],
                status=EvaluationAssetStatus(item["status"]),
                description=item["description"],
                manifest_path=item.get("manifest_path"),
                case_count=_load_case_count(
                    repo_root=repo_root,
                    manifest_path=item.get("manifest_path"),
                ),
            )
            for item in payload["fixture_families"]
        ],
    )


def load_evaluation_fixture_family(*, fixture_id: str) -> EvaluationFixtureFamily:
    repo_root = Path(__file__).resolve().parents[3]
    manifest = load_evaluation_fixture_manifest()
    fixture = next(
        (fixture for fixture in manifest.fixture_families if fixture.fixture_id == fixture_id),
        None,
    )
    if fixture is None:
        raise EvaluationFixtureManifestValidationError(
            f"Unknown evaluation fixture family '{fixture_id}'."
        )
    task_id, cases = _load_fixture_family_detail(
        repo_root=repo_root,
        manifest_path=fixture.manifest_path,
    )
    return EvaluationFixtureFamily(descriptor=fixture, task_id=task_id, cases=cases)


def validate_evaluation_fixture_manifest(
    *,
    repo_root: Path,
    manifest_payload: dict[str, Any],
) -> None:
    _require_non_empty_string(
        manifest_payload.get("manifest_version"), field_name="manifest_version"
    )
    _validate_evidence_categories(manifest_payload.get("evidence_categories"))
    _validate_fixture_families(
        repo_root=repo_root, fixture_families=manifest_payload.get("fixture_families")
    )


def _load_case_count(*, repo_root: Path, manifest_path: str | None) -> int:
    if manifest_path is None:
        return 0
    fixture_path = repo_root / manifest_path
    with fixture_path.open("r", encoding="utf-8") as fixture_file:
        payload = json.load(fixture_file)
    cases = payload.get("cases", [])
    if not isinstance(cases, list):
        raise EvaluationFixtureManifestValidationError(
            f"Fixture manifest file has non-list cases payload: {fixture_path}"
        )
    return len(cases)


def _load_fixture_family_detail(
    *,
    repo_root: Path,
    manifest_path: str | None,
) -> tuple[str | None, list[EvaluationFixtureCaseDescriptor]]:
    if manifest_path is None:
        return None, []
    fixture_path = repo_root / manifest_path
    with fixture_path.open("r", encoding="utf-8") as fixture_file:
        payload = json.load(fixture_file)
    cases = payload.get("cases", [])
    if not isinstance(cases, list):
        raise EvaluationFixtureManifestValidationError(
            f"Fixture manifest file has non-list cases payload: {fixture_path}"
        )
    return (
        payload.get("task_id"),
        [
            EvaluationFixtureCaseDescriptor(case_id=case["case_id"], summary=case["summary"])
            for case in cases
        ],
    )


def _validate_evidence_categories(evidence_categories: Any) -> None:
    if not isinstance(evidence_categories, list):
        raise EvaluationFixtureManifestValidationError(
            "Evaluation fixture manifest must define evidence_categories as a list."
        )
    category_ids: set[str] = set()
    for item in evidence_categories:
        if not isinstance(item, dict):
            raise EvaluationFixtureManifestValidationError(
                "Each evidence_categories entry must be an object."
            )
        category_id = item.get("category_id")
        _require_non_empty_string(category_id, field_name="evidence_categories[].category_id")
        _require_non_empty_string(
            item.get("description"), field_name="evidence_categories[].description"
        )
        if category_id in category_ids:
            raise EvaluationFixtureManifestValidationError(
                f"Duplicate evidence category id '{category_id}' in evaluation fixture manifest."
            )
        category_ids.add(category_id)


def _validate_fixture_families(*, repo_root: Path, fixture_families: Any) -> None:
    if not isinstance(fixture_families, list):
        raise EvaluationFixtureManifestValidationError(
            "Evaluation fixture manifest must define fixture_families as a list."
        )
    fixture_ids: set[str] = set()
    for item in fixture_families:
        if not isinstance(item, dict):
            raise EvaluationFixtureManifestValidationError(
                "Each fixture_families entry must be an object."
            )
        fixture_id = item.get("fixture_id")
        _require_non_empty_string(fixture_id, field_name="fixture_families[].fixture_id")
        _require_non_empty_string(
            item.get("description"), field_name="fixture_families[].description"
        )
        if fixture_id in fixture_ids:
            raise EvaluationFixtureManifestValidationError(
                f"Duplicate fixture family id '{fixture_id}' in evaluation fixture manifest."
            )
        fixture_ids.add(fixture_id)

        status = EvaluationAssetStatus(item["status"])
        manifest_path = item.get("manifest_path")
        if status == EvaluationAssetStatus.STAGED and manifest_path is None:
            raise EvaluationFixtureManifestValidationError(
                f"Staged fixture family '{fixture_id}' must define manifest_path."
            )
        if status == EvaluationAssetStatus.DOCUMENTED and manifest_path is not None:
            raise EvaluationFixtureManifestValidationError(
                f"Documented-only fixture family '{fixture_id}' must not define manifest_path."
            )
        if manifest_path is not None:
            _validate_fixture_file(
                repo_root=repo_root,
                fixture_id=fixture_id,
                manifest_path=manifest_path,
            )


def _validate_fixture_file(*, repo_root: Path, fixture_id: str, manifest_path: str) -> None:
    fixture_path = repo_root / manifest_path
    if not fixture_path.is_file():
        raise EvaluationFixtureManifestValidationError(
            f"Fixture file for '{fixture_id}' does not exist: {manifest_path}"
        )
    with fixture_path.open("r", encoding="utf-8") as fixture_file:
        payload = json.load(fixture_file)
    _require_non_empty_string(payload.get("task_id"), field_name=f"{manifest_path}.task_id")
    _require_non_empty_string(
        payload.get("fixture_family"),
        field_name=f"{manifest_path}.fixture_family",
    )
    if payload["fixture_family"] != fixture_id:
        raise EvaluationFixtureManifestValidationError(
            f"Fixture file '{manifest_path}' declares fixture_family "
            f"'{payload['fixture_family']}' but manifest expects '{fixture_id}'."
        )
    cases = payload.get("cases")
    if not isinstance(cases, list):
        raise EvaluationFixtureManifestValidationError(
            f"Fixture file '{manifest_path}' must define cases as a list."
        )
    case_ids: set[str] = set()
    for case in cases:
        if not isinstance(case, dict):
            raise EvaluationFixtureManifestValidationError(
                f"Fixture file '{manifest_path}' contains a non-object case entry."
            )
        case_id = case.get("case_id")
        _require_non_empty_string(case_id, field_name=f"{manifest_path}.cases[].case_id")
        _require_non_empty_string(
            case.get("summary"), field_name=f"{manifest_path}.cases[].summary"
        )
        if case_id in case_ids:
            raise EvaluationFixtureManifestValidationError(
                f"Fixture file '{manifest_path}' contains duplicate case_id '{case_id}'."
            )
        case_ids.add(case_id)
        if not isinstance(case.get("input"), dict):
            raise EvaluationFixtureManifestValidationError(
                f"Fixture case '{case_id}' in '{manifest_path}' must define input as an object."
            )
        if not isinstance(case.get("expected"), dict):
            raise EvaluationFixtureManifestValidationError(
                f"Fixture case '{case_id}' in '{manifest_path}' must define expected as an object."
            )


def _require_non_empty_string(value: Any, *, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise EvaluationFixtureManifestValidationError(
            f"Evaluation fixture manifest field '{field_name}' must be a non-empty string."
        )
