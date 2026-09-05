from __future__ import annotations

import hashlib

from app.contracts.artifacts import (
    ArtifactDescriptor,
    ArtifactLifecycleStatus,
    ArtifactStorageBackend,
)
from app.services.artifact_store import get_artifact_object_store, reset_artifact_store_cache
from app.services.workflow_pack_run_output_summary import (
    build_idea_lineage_from_run_output_summary,
    load_workflow_pack_run_output_summary,
)


def _summary_artifact(storage_reference: str) -> ArtifactDescriptor:
    return ArtifactDescriptor(
        artifact_id="artifact-run-output-summary",
        domain="workflow_pack",
        artifact_type="run_output_summary",
        source_object_kind="workflow_pack_run",
        source_object_id="run-idea-001",
        lifecycle_status=ArtifactLifecycleStatus.RUNTIME_GENERATED,
        retention_posture="active",
        media_type="application/json",
        byte_size=2,
        checksum_sha256=hashlib.sha256(b"summary-test").hexdigest(),
        storage_backend=ArtifactStorageBackend.MEMORY,
        storage_reference=storage_reference,
        created_at="2026-04-21T12:00:00Z",
        created_by="worker",
    )


def test_workflow_pack_run_output_summary_handles_missing_and_malformed_artifacts() -> None:
    reset_artifact_store_cache()
    store = get_artifact_object_store()
    store.put_object(
        object_key="workflow-pack/run-1/non-json",
        payload=b"\xff",
        content_type="application/json",
    )
    store.put_object(
        object_key="workflow-pack/run-1/list-json",
        payload=b'["not", "an", "object"]',
        content_type="application/json",
    )

    assert load_workflow_pack_run_output_summary([]) == {}
    assert load_workflow_pack_run_output_summary([_summary_artifact("memory://missing")]) == {}
    assert (
        load_workflow_pack_run_output_summary(
            [_summary_artifact("memory://workflow-pack/run-1/non-json")]
        )
        == {}
    )
    assert (
        load_workflow_pack_run_output_summary(
            [_summary_artifact("memory://workflow-pack/run-1/list-json")]
        )
        == {}
    )


def test_build_idea_lineage_from_run_output_summary_requires_idea_payload() -> None:
    assert build_idea_lineage_from_run_output_summary({"pack_id": "advisor_brief.pack"}) is None
    assert (
        build_idea_lineage_from_run_output_summary(
            {"pack_id": "idea_explanation.pack", "structured_output": "not-an-object"}
        )
        is None
    )
    assert (
        build_idea_lineage_from_run_output_summary(
            {
                "pack_id": "idea_explanation.pack",
                "structured_output": {"candidate_id": "candidate-1"},
            }
        )
        is None
    )


def test_build_idea_lineage_from_run_output_summary_accepts_governed_idea_payload() -> None:
    lineage = build_idea_lineage_from_run_output_summary(
        {
            "pack_id": "idea_explanation.pack",
            "structured_output": {
                "candidate_id": "idea-1",
                "evidence_packet_id": "packet-1",
                "evidence_content_hash": "sha256:evidence",
                "family": "portfolio_rebalancing",
                "lifecycle_status": "candidate",
                "review_posture": "pending_review",
                "source_ref_count": 3,
                "source_signal_count": 5,
            },
        }
    )

    assert lineage is not None
    assert lineage.candidate_id == "idea-1"
    assert lineage.score_policy_version is None
    assert lineage.source_ref_count == 3
