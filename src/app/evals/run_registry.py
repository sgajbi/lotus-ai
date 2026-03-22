from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.contracts.evals import EvaluationRunArtifactDescriptor


@lru_cache(maxsize=1)
def load_evaluation_run_artifacts() -> list[EvaluationRunArtifactDescriptor]:
    repo_root = Path(__file__).resolve().parents[3]
    run_manifest_path = repo_root / "docs" / "evals" / "run-artifacts.json"
    with run_manifest_path.open("r", encoding="utf-8") as run_manifest_file:
        payload = json.load(run_manifest_file)
    runs = payload.get("runs", [])
    return [EvaluationRunArtifactDescriptor(**run) for run in runs]
