from __future__ import annotations

from app.contracts.workflow_pack_runs import (
    WorkflowPackRunReviewState,
    WorkflowPackRunRuntimeState,
)
from app.contracts.workflow_packs import (
    WorkflowPackExecutableActivitySummaryResponse,
    WorkflowPackRunRuntimeSummaryResponse,
    WorkflowPackRuntimeStatusSummaryResponse,
)
from app.services.workflow_pack_bindings import list_workflow_pack_execution_binding_descriptors
from app.services.workflow_pack_registry import list_workflow_pack_registrations
from app.services.workflow_pack_run_ledger import build_workflow_pack_run_catalog


def build_workflow_pack_runtime_status_summary() -> WorkflowPackRuntimeStatusSummaryResponse:
    registrations = list_workflow_pack_registrations()
    execution_bindings = list_workflow_pack_execution_binding_descriptors()
    binding_refs = {f"{binding.pack_id}@{binding.version}" for binding in execution_bindings}
    registered_registrations = [
        registration
        for registration in registrations
        if registration.registration_status.value == "REGISTERED"
    ]
    registered_registration_refs = [
        f"{registration.pack_id}@{registration.version}" for registration in registered_registrations
    ]
    executable_registrations = [
        registration
        for registration in registered_registrations
        if f"{registration.pack_id}@{registration.version}" in binding_refs
    ]
    executable_registration_refs = sorted(
        f"{registration.pack_id}@{registration.version}" for registration in executable_registrations
    )
    executable_review_required_refs = sorted(
        f"{registration.pack_id}@{registration.version}"
        for registration in executable_registrations
        if registration.default_execution_mode.value == "REVIEW_GATED"
    )
    registered_count = len(registered_registration_refs)
    executable_registration_count = len(executable_registration_refs)
    executable_review_required_count = len(executable_review_required_refs)
    registered_without_execution_binding_count = registered_count - executable_registration_count
    run_catalog = build_workflow_pack_run_catalog()

    return WorkflowPackRuntimeStatusSummaryResponse(
        registration_count=len(registrations),
        registered_count=registered_count,
        execution_binding_count=len(execution_bindings),
        executable_registration_count=executable_registration_count,
        executable_review_required_count=executable_review_required_count,
        executable_without_review_count=(
            executable_registration_count - executable_review_required_count
        ),
        registered_without_execution_binding_count=registered_without_execution_binding_count,
        executable_registration_refs=executable_registration_refs,
        executable_review_required_refs=executable_review_required_refs,
        executable_activity=build_workflow_pack_executable_activity_summary(
            executable_registration_refs=executable_registration_refs,
            run_catalog=run_catalog,
        ),
        run_summary=build_workflow_pack_run_runtime_summary(run_catalog=run_catalog),
        status_summary=[
            "Workflow-pack runtime readiness is narrower than catalog presence and counts only versions that are both REGISTERED and explicitly bound for lotus-ai execution.",
            "Executable workflow-pack versions are further split by whether the registered default execution mode still requires human review before downstream use.",
            "Registered workflow-pack versions without an explicit execution binding remain visible as governed catalog entries but are not yet executable through the current bounded lotus-ai runtime path.",
            "Per-pack activity summary shows whether executable workflow-pack versions are merely wired or are actually producing ledgered runs through the current bounded path.",
            "Estate-level run posture is summarized separately so operators can see review backlog and action-required run state without reading the raw ledger catalog first.",
            "Use the workflow-pack registry detail surface for owner-artifact truth and the platform runtime status summary for estate-level execution readiness posture.",
        ],
    )


def build_workflow_pack_run_runtime_summary(
    *,
    run_catalog=None,
) -> WorkflowPackRunRuntimeSummaryResponse:
    catalog = run_catalog or build_workflow_pack_run_catalog()
    runs = catalog.runs
    accepted_count = sum(
        1 for run in runs if run.review_state is WorkflowPackRunReviewState.ACCEPTED
    )
    rejected_count = sum(
        1 for run in runs if run.review_state is WorkflowPackRunReviewState.REJECTED
    )
    abandoned_count = sum(
        1 for run in runs if run.review_state is WorkflowPackRunReviewState.ABANDONED
    )
    superseded_count = sum(
        1
        for run in runs
        if run.review_state
        in {
            WorkflowPackRunReviewState.REVISED,
            WorkflowPackRunReviewState.SUPERSEDED,
        }
        or run.runtime_state is WorkflowPackRunRuntimeState.SUPERSEDED
    )
    failed_count = sum(1 for run in runs if run.runtime_state is WorkflowPackRunRuntimeState.FAILED)
    expired_count = sum(
        1 for run in runs if run.runtime_state is WorkflowPackRunRuntimeState.EXPIRED
    )
    action_required_count = sum(
        1
        for run in runs
        if run.review_state
        in {
            WorkflowPackRunReviewState.AWAITING_REVIEW,
            WorkflowPackRunReviewState.REJECTED,
            WorkflowPackRunReviewState.ABANDONED,
        }
        or run.runtime_state
        in {
            WorkflowPackRunRuntimeState.FAILED,
            WorkflowPackRunRuntimeState.EXPIRED,
        }
    )

    return WorkflowPackRunRuntimeSummaryResponse(
        run_count=catalog.run_count,
        awaiting_review_count=catalog.awaiting_review_count,
        accepted_count=accepted_count,
        rejected_count=rejected_count,
        abandoned_count=abandoned_count,
        superseded_count=superseded_count,
        failed_count=failed_count,
        expired_count=expired_count,
        action_required_count=action_required_count,
        latest_recorded_at=catalog.latest_recorded_at,
        status_summary=[
            "Workflow-pack run posture is summarized from the bounded ledger catalog rather than from a separate estate-only store.",
            "Action-required count currently covers review backlog plus failed, expired, rejected, and abandoned run posture so operator attention can be triaged quickly.",
            "Use the run detail, consumer-view, and operator-profile routes when estate-level counts show a posture that needs diagnosis.",
        ],
    )


def build_workflow_pack_executable_activity_summary(
    *,
    executable_registration_refs: list[str],
    run_catalog,
) -> list[WorkflowPackExecutableActivitySummaryResponse]:
    runs_by_registration_ref: dict[str, list] = {}
    for run in run_catalog.runs:
        runs_by_registration_ref.setdefault(run.registration_ref, []).append(run)

    summaries: list[WorkflowPackExecutableActivitySummaryResponse] = []
    for registration_ref in executable_registration_refs:
        pack_id, version = registration_ref.split("@", maxsplit=1)
        runs = runs_by_registration_ref.get(registration_ref, [])
        latest_run = max(runs, key=lambda run: run.created_at) if runs else None
        summaries.append(
            WorkflowPackExecutableActivitySummaryResponse(
                registration_ref=registration_ref,
                pack_id=pack_id,
                version=version,
                run_count=len(runs),
                awaiting_review_count=sum(
                    1
                    for run in runs
                    if run.review_state is WorkflowPackRunReviewState.AWAITING_REVIEW
                ),
                accepted_count=sum(
                    1 for run in runs if run.review_state is WorkflowPackRunReviewState.ACCEPTED
                ),
                latest_run_id=latest_run.run_id if latest_run is not None else None,
                latest_recorded_at=latest_run.created_at if latest_run is not None else None,
                has_activity=bool(runs),
            )
        )
    return summaries
