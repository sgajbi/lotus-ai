from __future__ import annotations

from app.config import settings
from app.contracts.workflow_pack_runs import (
    WorkflowPackRunDetailResponse,
    WorkflowPackRunFindingSeverity,
    WorkflowPackRunOperatorProfileResponse,
    WorkflowPackRunReviewState,
    WorkflowPackRunRuntimeState,
    WorkflowPackRunSupportabilityFinding,
    WorkflowPackRunSupportabilityStatus,
)
from app.services.workflow_pack_run_ledger import build_workflow_pack_run_detail


def build_workflow_pack_run_operator_profile(
    *, run_id: str
) -> WorkflowPackRunOperatorProfileResponse:
    detail = build_workflow_pack_run_detail(run_id=run_id)
    run = detail.run
    findings = _build_findings(detail)
    supportability_status = _resolve_supportability_status(detail)

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
        review_pending=run.review_required
        and run.review_state is WorkflowPackRunReviewState.AWAITING_REVIEW,
        failed=run.runtime_state is WorkflowPackRunRuntimeState.FAILED,
        expired=run.runtime_state is WorkflowPackRunRuntimeState.EXPIRED,
        superseded=_is_superseded(detail),
        partial_output_visible=_has_partial_output(detail),
        artifact_ref_count=len(run.artifact_refs),
        evidence_descriptor_count=len(run.evidence_descriptors),
        history_event_count=len(detail.events),
        latest_event_at=detail.events[-1].recorded_at if detail.events else None,
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


def _resolve_supportability_status(
    detail: WorkflowPackRunDetailResponse,
) -> WorkflowPackRunSupportabilityStatus:
    run = detail.run
    if _is_superseded(detail):
        return WorkflowPackRunSupportabilityStatus.HISTORICAL
    if (
        run.runtime_state
        in {WorkflowPackRunRuntimeState.FAILED, WorkflowPackRunRuntimeState.EXPIRED}
        or run.review_state
        in {
            WorkflowPackRunReviewState.REJECTED,
            WorkflowPackRunReviewState.ABANDONED,
        }
        or (run.review_required and run.review_state is WorkflowPackRunReviewState.AWAITING_REVIEW)
        or len(run.artifact_refs) == 0
        or len(run.evidence_descriptors) == 0
    ):
        return WorkflowPackRunSupportabilityStatus.ACTION_REQUIRED
    return WorkflowPackRunSupportabilityStatus.READY


def _build_findings(
    detail: WorkflowPackRunDetailResponse,
) -> list[WorkflowPackRunSupportabilityFinding]:
    run = detail.run
    findings: list[WorkflowPackRunSupportabilityFinding] = []

    if run.review_required and run.review_state is WorkflowPackRunReviewState.AWAITING_REVIEW:
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
    if _is_superseded(detail):
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
    if _has_partial_output(detail):
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
    if run.review_required and run.review_state is WorkflowPackRunReviewState.AWAITING_REVIEW:
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


def _is_superseded(detail: WorkflowPackRunDetailResponse) -> bool:
    run = detail.run
    return (
        run.superseded_by_run_id is not None
        or run.review_state
        in {
            WorkflowPackRunReviewState.REVISED,
            WorkflowPackRunReviewState.SUPERSEDED,
        }
        or run.runtime_state is WorkflowPackRunRuntimeState.SUPERSEDED
    )


def _has_partial_output(detail: WorkflowPackRunDetailResponse) -> bool:
    run = detail.run
    return run.runtime_state in {
        WorkflowPackRunRuntimeState.FAILED,
        WorkflowPackRunRuntimeState.EXPIRED,
    } and bool(run.output_preview.strip() or run.structured_output_keys)
