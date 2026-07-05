from __future__ import annotations

import json
from typing import Any

from app.contracts.artifacts import ArtifactDescriptor
from app.contracts.workflow_pack_runs import WorkflowPackIdeaLineageDescriptor
from app.services.artifact_object_store import StoredArtifactObject
from app.services.artifact_store import get_artifact_object_store


def load_workflow_pack_run_output_summary(
    artifact_refs: list[ArtifactDescriptor],
) -> dict[str, Any]:
    summary_artifact = next(
        (
            artifact
            for artifact in artifact_refs
            if artifact.domain == "workflow_pack"
            and artifact.artifact_type == "run_output_summary"
            and artifact.storage_reference
        ),
        None,
    )
    if summary_artifact is None:
        return {}
    _, _, object_key = summary_artifact.storage_reference.partition("://")
    stored_object: StoredArtifactObject | None = get_artifact_object_store().get_object(
        object_key=object_key
    )
    if stored_object is None:
        return {}
    try:
        payload = json.loads(stored_object.payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def build_idea_lineage_from_run_output_summary(
    artifact_payload: dict[str, Any],
) -> WorkflowPackIdeaLineageDescriptor | None:
    if artifact_payload.get("pack_id") != "idea_explanation.pack":
        return None
    structured_output = artifact_payload.get("structured_output")
    if not isinstance(structured_output, dict):
        return None
    required = {
        "candidate_id": _string_from_mapping(structured_output, "candidate_id"),
        "evidence_packet_id": _string_from_mapping(structured_output, "evidence_packet_id"),
        "evidence_content_hash": _string_from_mapping(
            structured_output,
            "evidence_content_hash",
        ),
        "family": _string_from_mapping(structured_output, "family"),
        "lifecycle_status": _string_from_mapping(structured_output, "lifecycle_status"),
        "review_posture": _string_from_mapping(structured_output, "review_posture"),
    }
    if any(not value for value in required.values()):
        return None
    return WorkflowPackIdeaLineageDescriptor(
        candidate_id=required["candidate_id"],
        evidence_packet_id=required["evidence_packet_id"],
        evidence_content_hash=required["evidence_content_hash"],
        family=required["family"],
        lifecycle_status=required["lifecycle_status"],
        review_posture=required["review_posture"],
        source_ref_count=_int_from_mapping(structured_output, "source_ref_count"),
        source_signal_count=_int_from_mapping(structured_output, "source_signal_count"),
        score_policy_version=_optional_string_from_mapping(
            structured_output,
            "score_policy_version",
        ),
    )


def _string_from_mapping(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    return value if isinstance(value, str) else ""


def _optional_string_from_mapping(payload: dict[str, object], key: str) -> str | None:
    value = _string_from_mapping(payload, key)
    return value or None


def _int_from_mapping(payload: dict[str, object], key: str) -> int:
    value = payload.get(key)
    return value if isinstance(value, int) else 0
