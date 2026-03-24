from __future__ import annotations

from app.config import settings
from app.contracts.evals import EvaluationApprovalEvidenceState
from app.contracts.resilience import (
    ResilienceDrillEvidenceItem,
    ResilienceDrillEvidenceResponse,
    ResilienceDrillEvidenceState,
    ResiliencePosture,
)
from app.contracts.artifacts import ArtifactRuntimeStatusResponse
from app.contracts.async_runtime import AsyncRuntimeStatusResponse
from app.contracts.resilience import (
    ResilienceRestorePlanResponse,
    ResilienceRuntimeStatusResponse,
)
from app.services.artifact_runtime import build_artifact_runtime_status
from app.services.async_runtime_status import build_async_runtime_status
from app.services.eval_approval_gate_summary import (
    build_provider_approval_gate_summary,
    build_retrieval_approval_gate_summary,
)
from app.services.governance_readiness import summarize_activation_items
from app.services.resilience_restore_plan import build_resilience_restore_plan
from app.services.resilience_runtime import build_resilience_runtime_status


def build_resilience_drill_evidence() -> ResilienceDrillEvidenceResponse:
    runtime_status = build_resilience_runtime_status()
    restore_plan = build_resilience_restore_plan()
    async_runtime = build_async_runtime_status()
    artifact_runtime = build_artifact_runtime_status()
    provider_approval_gate = build_provider_approval_gate_summary()
    retrieval_approval_gate = build_retrieval_approval_gate_summary()

    items = [
        _build_store_restore_validation_item(runtime_status, restore_plan),
        _build_async_recovery_drill_item(async_runtime),
        _build_provider_recovery_drill_item(provider_approval_gate.evidence_state),
        _build_retrieval_recovery_drill_item(retrieval_approval_gate.evidence_state),
        _build_artifact_restore_review_item(artifact_runtime),
    ]
    required_item_count, completed_required_item_count = summarize_activation_items(items)
    return ResilienceDrillEvidenceResponse(
        service=settings.service_name,
        version=settings.service_version,
        drill_evidence_ready=required_item_count == completed_required_item_count,
        required_item_count=required_item_count,
        completed_required_item_count=completed_required_item_count,
        items=items,
    )


def _build_store_restore_validation_item(
    runtime_status: ResilienceRuntimeStatusResponse,
    restore_plan: ResilienceRestorePlanResponse,
) -> ResilienceDrillEvidenceItem:
    if (
        runtime_status.posture is not ResiliencePosture.LOCAL_OR_DEMO_CONTINUITY
        and restore_plan.restore_step_count > 0
    ):
        status = ResilienceDrillEvidenceState.READY
        notes = "Restore ordering and authoritative-store validation are defined and the current runtime posture is no longer limited to local or demo continuity."
    elif restore_plan.restore_step_count > 0:
        status = ResilienceDrillEvidenceState.FOUNDATION_STAGED
        notes = "Restore ordering is now defined, but current runtime posture still depends on local or fallback continuity rather than a drill-verifiable durable baseline."
    else:
        status = ResilienceDrillEvidenceState.NOT_READY
        notes = (
            "Restore ordering has not been defined well enough to support resilience drill review."
        )
    return ResilienceDrillEvidenceItem(
        drill_id="authoritative_store_restore_validation",
        status=status,
        required_for_activation=True,
        notes=notes,
    )


def _build_async_recovery_drill_item(
    async_runtime: AsyncRuntimeStatusResponse,
) -> ResilienceDrillEvidenceItem:
    queue_active = async_runtime.queue_backend == "redis_queue"
    dedicated_workers = async_runtime.worker_mode == "DEDICATED"
    if queue_active and dedicated_workers and not async_runtime.degraded_findings:
        status = ResilienceDrillEvidenceState.READY
        notes = "Managed queue and dedicated workers are active without degraded findings, so async recovery review can use runtime-backed queue and worker evidence."
    elif queue_active and dedicated_workers:
        status = ResilienceDrillEvidenceState.PARTIAL
        notes = "Managed queue and dedicated workers are configured, but degraded async findings still need operator review before treating recovery evidence as complete."
    else:
        status = ResilienceDrillEvidenceState.FOUNDATION_STAGED
        notes = "Async recovery remains on a local or fallback posture, so only foundational recovery proof is available in this environment."
    return ResilienceDrillEvidenceItem(
        drill_id="async_runtime_recovery_drill",
        status=status,
        required_for_activation=True,
        notes=notes,
    )


def _build_provider_recovery_drill_item(
    evidence_state: EvaluationApprovalEvidenceState,
) -> ResilienceDrillEvidenceItem:
    status, notes = _map_approval_state_to_drill_status(
        evidence_state,
        ready_notes="Provider recovery evidence is backed by passing runtime-produced approval evidence.",
        staged_notes="Provider recovery evidence is still staged-only and has not been re-proven through current runtime-backed evaluation.",
        partial_notes="Provider recovery evidence exists, but it is partial, stale, in progress, or failing and still blocks drill-ready posture.",
    )
    return ResilienceDrillEvidenceItem(
        drill_id="provider_recovery_drill",
        status=status,
        required_for_activation=True,
        notes=notes,
    )


def _build_retrieval_recovery_drill_item(
    evidence_state: EvaluationApprovalEvidenceState,
) -> ResilienceDrillEvidenceItem:
    status, notes = _map_approval_state_to_drill_status(
        evidence_state,
        ready_notes="Retrieval recovery evidence is backed by passing runtime-produced approval evidence.",
        staged_notes="Retrieval recovery evidence is still staged-only and has not been re-proven through current runtime-backed evaluation.",
        partial_notes="Retrieval recovery evidence exists, but it is partial, stale, in progress, or failing and still blocks drill-ready posture.",
    )
    return ResilienceDrillEvidenceItem(
        drill_id="retrieval_recovery_drill",
        status=status,
        required_for_activation=True,
        notes=notes,
    )


def _build_artifact_restore_review_item(
    artifact_runtime: ArtifactRuntimeStatusResponse,
) -> ResilienceDrillEvidenceItem:
    if (
        artifact_runtime.metadata_store.status.value == "READY"
        and artifact_runtime.object_store.status.value == "READY"
        and artifact_runtime.object_store_mode not in {"memory", "filesystem"}
    ):
        status = ResilienceDrillEvidenceState.READY
        notes = "Artifact metadata and payload storage are configured through a non-fallback backend, so artifact-backed recovery review can be treated as drill-ready."
    elif (
        artifact_runtime.metadata_store.status.value == "READY"
        and artifact_runtime.object_store.status.value == "READY"
    ):
        status = ResilienceDrillEvidenceState.PARTIAL
        notes = "Artifact metadata is durable and payload storage is reachable, but the current object-store mode is still a local or development fallback rather than a production recovery backend."
    else:
        status = ResilienceDrillEvidenceState.NOT_READY
        notes = "Artifact metadata or payload storage is not yet ready enough to support governed restore review."
    return ResilienceDrillEvidenceItem(
        drill_id="artifact_restore_review_drill",
        status=status,
        required_for_activation=True,
        notes=notes,
    )


def _map_approval_state_to_drill_status(
    evidence_state: EvaluationApprovalEvidenceState,
    *,
    ready_notes: str,
    staged_notes: str,
    partial_notes: str,
) -> tuple[ResilienceDrillEvidenceState, str]:
    if evidence_state is EvaluationApprovalEvidenceState.RUNTIME_PASS:
        return ResilienceDrillEvidenceState.READY, ready_notes
    if evidence_state in {
        EvaluationApprovalEvidenceState.STAGED_ONLY,
        EvaluationApprovalEvidenceState.NO_EVIDENCE,
    }:
        return ResilienceDrillEvidenceState.FOUNDATION_STAGED, staged_notes
    return ResilienceDrillEvidenceState.PARTIAL, partial_notes
