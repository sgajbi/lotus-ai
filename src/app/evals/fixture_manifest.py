from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.contracts.evals import (
    EvaluationAssetStatus,
    EvaluationEvidenceCategoryDescriptor,
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


@lru_cache(maxsize=1)
def load_evaluation_fixture_manifest() -> EvaluationFixtureManifest:
    repo_root = Path(__file__).resolve().parents[3]
    manifest_path = repo_root / "docs" / "evals" / "fixture-manifest.json"
    with manifest_path.open("r", encoding="utf-8") as manifest_file:
        payload = json.load(manifest_file)
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


def _load_case_count(*, repo_root: Path, manifest_path: str | None) -> int:
    if manifest_path is None:
        return 0
    fixture_path = repo_root / manifest_path
    with fixture_path.open("r", encoding="utf-8") as fixture_file:
        payload = json.load(fixture_file)
    cases = payload.get("cases", [])
    if not isinstance(cases, list):
        raise ValueError(f"Fixture manifest file has non-list cases payload: {fixture_path}")
    return len(cases)
