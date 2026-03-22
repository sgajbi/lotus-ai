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
    manifest_path = Path(__file__).resolve().parents[3] / "docs" / "evals" / "fixture-manifest.json"
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
            )
            for item in payload["fixture_families"]
        ],
    )
