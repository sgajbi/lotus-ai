from __future__ import annotations

from app.config import settings
from app.contracts.workflow_pack_runs import (
    WorkflowPackRunDetailResponse,
    WorkflowPackRunFindingSeverity,
    WorkflowPackRunOperatorProfileResponse,
    WorkflowPackRunRuntimeState,
    WorkflowPackRunSupportabilityFinding,
    WorkflowPackRunSupportabilityStatus,
)
from app.services.workflow_pack_run_ledger import build_workflow_pack_run_detail
from app.services.workflow_pack_run_supportability import (
    has_workflow_pack_run_partial_output,
    is_workflow_pack_run_historical,
    is_workflow_pack_run_review_pending,
    resolve_workflow_pack_run_supportability_status,
)


def build_workflow_pack_run_operator_profile(
    *, run_id: str
) -> WorkflowPackRunOperatorProfileResponse:
    detail = build_workflow_pack_run_detail(run_id=run_id)
    run = detail.run
    latest_event = detail.events[-1] if detail.events else None
    review_events = _list_review_events(detail)
    latest_review_event = review_events[-1] if review_events else None
    findings = _build_findings(detail)
    supportability_status = resolve_workflow_pack_run_supportability_status(run)
    provenance = detail.provenance

    return WorkflowPackRunOperatorProfileResponse(
        service=settings.service_name,
        version=settings.service_version,
        run_store_mode=settings.workflow_pack_run_store_mode,
        run_id=run.run_id,
        pack_id=run.pack_id,
        registration_ref=run.registration_ref,
        runtime_state=run.runtime_state,
        review_state=run.review_state,
        workflow_authority_owner=run.workflow_authority_owner,
        supportability_status=supportability_status,
        review_pending=is_workflow_pack_run_review_pending(run),
        failed=run.runtime_state is WorkflowPackRunRuntimeState.FAILED,
        expired=run.runtime_state is WorkflowPackRunRuntimeState.EXPIRED,
        superseded=is_workflow_pack_run_historical(run),
        partial_output_visible=has_workflow_pack_run_partial_output(run),
        provenance=provenance,
        artifact_ref_count=provenance.artifact_ref_count,
        evidence_descriptor_count=provenance.evidence_descriptor_count,
        history_event_count=len(detail.events),
        latest_event_at=latest_event.recorded_at if latest_event is not None else None,
        latest_event_type=latest_event.event_type if latest_event is not None else None,
        latest_event_actor=latest_event.actor if latest_event is not None else None,
        latest_review_event_at=(
            latest_review_event.recorded_at if latest_review_event is not None else None
        ),
        latest_review_actor=latest_review_event.actor if latest_review_event is not None else None,
        review_transition_count=len(review_events),
        event_type_counts=_build_event_type_counts(detail),
        replacement_run_id=run.superseded_by_run_id,
        current_summary_note=_build_current_summary_note(detail, supportability_status),
        findings=findings,
        inspection_surfaces=[
            "/platform/workflow-packs/runs",
            f"/platform/workflow-packs/runs/{run.run_id}",
            f"/platform/workflow-packs/runs/{run.run_id}/consumer-view",
            f"/platform/workflow-packs/runs/{run.run_id}/operator-profile",
        ],
        inspection_steps=_build_inspection_steps(detail),
    )


def _build_findings(
    detail: WorkflowPackRunDetailResponse,
) -> list[WorkflowPackRunSupportabilityFinding]:
    run = detail.run
    findings: list[WorkflowPackRunSupportabilityFinding] = []

    if is_workflow_pack_run_review_pending(run):
        findings.append(
            WorkflowPackRunSupportabilityFinding(
                finding_id="review_pending",
                severity=WorkflowPackRunFindingSeverity.ACTION_REQUIRED,
                summary="Run is awaiting review.",
                detail=(
                    "This workflow-pack run completed execution but still requires bounded human "
                    "review before downstream consumers should treat it as usable draft output."
                ),
            )
        )
    if run.runtime_state is WorkflowPackRunRuntimeState.FAILED:
        findings.append(
            WorkflowPackRunSupportabilityFinding(
                finding_id="runtime_failed",
                severity=WorkflowPackRunFindingSeverity.ACTION_REQUIRED,
                summary="Run is in failed runtime posture.",
                detail=(
                    "Support should inspect event history, evidence descriptors, and linked "
                    "artifacts before deciding whether the run needs replay or downstream escalation."
                ),
            )
        )
    if run.runtime_state is WorkflowPackRunRuntimeState.EXPIRED:
        findings.append(
            WorkflowPackRunSupportabilityFinding(
                finding_id="runtime_expired",
                severity=WorkflowPackRunFindingSeverity.ACTION_REQUIRED,
                summary="Run is in expired runtime posture.",
                detail=(
                    "The run should be treated as stale historical output until a newer "
                    "replacement run is recorded or downstream workflow owners explicitly reconcile it."
                ),
            )
        )
    if is_workflow_pack_run_historical(run):
        findings.append(
            WorkflowPackRunSupportabilityFinding(
                finding_id="run_historical",
                severity=WorkflowPackRunFindingSeverity.INFO,
                summary="Run has been superseded by a newer replacement.",
                detail=(
                    "The current run remains durable for history and audit, but operators should "
                    "inspect the replacement run for the latest active draft posture."
                ),
            )
        )
    if has_workflow_pack_run_partial_output(run):
        findings.append(
            WorkflowPackRunSupportabilityFinding(
                finding_id="partial_output_visible",
                severity=WorkflowPackRunFindingSeverity.INFO,
                summary="Partial output is still visible for inspection.",
                detail=(
                    "The run preserves some output preview or structured output keys even though it "
                    "did not land in a clean ready posture. Treat that content as diagnostic support evidence."
                ),
            )
        )
    if len(run.artifact_refs) == 0:
        findings.append(
            WorkflowPackRunSupportabilityFinding(
                finding_id="artifact_refs_missing",
                severity=WorkflowPackRunFindingSeverity.ACTION_REQUIRED,
                summary="No governed artifact refs are linked to the run.",
                detail=(
                    "Support should treat this as incomplete provenance posture because bounded "
                    "artifact-backed output review is expected for Phase-1 workflow-pack runs."
                ),
            )
        )
    if len(run.evidence_descriptors) == 0:
        findings.append(
            WorkflowPackRunSupportabilityFinding(
                finding_id="evidence_missing",
                severity=WorkflowPackRunFindingSeverity.ACTION_REQUIRED,
                summary="No execution evidence descriptors are linked to the run.",
                detail=(
                    "Support should treat this as incomplete supportability posture because runtime "
                    "decision evidence should remain attached to the run ledger."
                ),
            )
        )
    if not findings:
        findings.append(
            WorkflowPackRunSupportabilityFinding(
                finding_id="run_ready",
                severity=WorkflowPackRunFindingSeverity.INFO,
                summary="Run is supportable through the current bounded ledger posture.",
                detail=(
                    "Runtime state, review state, evidence, artifact refs, and lineage are all "
                    "present for the current Phase-1 workflow-pack path."
                ),
            )
        )
    return findings


def _build_current_summary_note(
    detail: WorkflowPackRunDetailResponse,
    supportability_status: WorkflowPackRunSupportabilityStatus,
) -> str:
    run = detail.run
    if supportability_status is WorkflowPackRunSupportabilityStatus.HISTORICAL:
        return (
            f"Run `{run.run_id}` is now historical because a replacement run "
            f"`{run.superseded_by_run_id}` exists."
        )
    if run.runtime_state is WorkflowPackRunRuntimeState.FAILED:
        return (
            "Run failed and requires operator diagnosis before any downstream replay or escalation."
        )
    if run.runtime_state is WorkflowPackRunRuntimeState.EXPIRED:
        return "Run expired and should be treated as stale until downstream owners reconcile it."
    if is_workflow_pack_run_review_pending(run):
        return "Run completed but still requires bounded human review before downstream use."
    return "Run is supportable through the current bounded workflow-pack ledger posture."


def _build_inspection_steps(detail: WorkflowPackRunDetailResponse) -> list[str]:
    run = detail.run
    return [
        "Inspect the workflow-pack run detail route first to verify runtime state, review state, and lineage identity.",
        "Review linked artifact refs and evidence descriptors before treating the output preview as supportable.",
        (
            f"If downstream consequences are blocked or disputed, escalate through "
            f"`{run.workflow_authority_owner}` because lotus-ai does not own business workflow authority."
        ),
        "When a newer replacement run exists, move diagnosis to that replacement before asking downstream teams to act on the historical run.",
    ]


def _build_event_type_counts(detail: WorkflowPackRunDetailResponse) -> dict[str, int]:
    counts: dict[str, int] = {}
    for event in detail.events:
        counts[event.event_type.value] = counts.get(event.event_type.value, 0) + 1
    return counts


def _list_review_events(detail: WorkflowPackRunDetailResponse):
    return [
        event
        for event in detail.events
        if event.event_type.value == "REVIEW_STATE_UPDATED"
    ]
