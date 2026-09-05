from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from app.contracts.artifacts import ArtifactDescriptor
from app.contracts.workflow_pack_runs import WorkflowPackIdeaLineageDescriptor
from app.services.artifact_object_store import StoredArtifactObject
from app.services.artifact_store import get_artifact_object_store

_logger = logging.getLogger(__name__)


class SummaryArtifactMissingError(RuntimeError):
    """No run_output_summary artifact is linked to the run."""


class SummaryObjectMissingError(RuntimeError):
    """The linked artifact's object bytes are no longer retrievable."""


class SummaryIntegrityMismatchError(RuntimeError):
    """The loaded bytes do not match the recorded checksum and size."""


def load_verified_summary_object(
    artifact_refs: list[ArtifactDescriptor],
) -> tuple[ArtifactDescriptor, StoredArtifactObject]:
    """THE single read authority for run_output_summary bytes (issue #336).

    Every consumer of summary bytes - the accepted-output surface and the
    projection readers alike - resolves them through this function, so the
    #328 integrity guarantee (loaded bytes ARE the persisted bytes; the
    recorded checksum is never repaired at read time) cannot be bypassed by
    a second resolution path.
    """

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
        raise SummaryArtifactMissingError()
    _, _, object_key = summary_artifact.storage_reference.partition("://")
    stored_object = get_artifact_object_store().get_object(object_key=object_key)
    if stored_object is None:
        raise SummaryObjectMissingError()
    recorded_checksum = (summary_artifact.checksum_sha256 or "").strip().lower()
    loaded_checksum = hashlib.sha256(stored_object.payload).hexdigest()
    if (
        not recorded_checksum
        or loaded_checksum != recorded_checksum
        or summary_artifact.byte_size != len(stored_object.payload)
    ):
        raise SummaryIntegrityMismatchError()
    return summary_artifact, stored_object


def load_workflow_pack_run_output_summary(
    artifact_refs: list[ArtifactDescriptor],
) -> dict[str, Any]:
    try:
        _, stored_object = load_verified_summary_object(artifact_refs)
    except (SummaryArtifactMissingError, SummaryObjectMissingError):
        return {}
    except SummaryIntegrityMismatchError:
        # Fail-closed for projections: tampered bytes are never served, the
        # surface degrades to absent, and the mismatch is operator-visible.
        _logger.warning(
            "run_output_summary integrity mismatch: projection withheld "
            "(bytes do not match the recorded checksum/size)"
        )
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
