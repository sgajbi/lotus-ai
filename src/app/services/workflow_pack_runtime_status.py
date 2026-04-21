from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.contracts.runtime_readiness import RuntimeReadinessStatus
from app.contracts.workflow_pack_task_flows import (
    WorkflowPackTaskFlowDescriptor,
    WorkflowPackTaskFlowStatus,
)
from app.contracts.workflow_pack_runs import (
    WorkflowPackRunCatalogResponse,
    WorkflowPackRunDescriptor,
    WorkflowPackRunReviewState,
    WorkflowPackRunRuntimeState,
    WorkflowPackRunSupportabilityStatus,
)
from app.contracts.workflow_packs import (
    WorkflowPackAttentionQueueItemResponse,
    WorkflowPackAttentionQueueSummaryResponse,
    WorkflowPackExecutableActivitySummaryResponse,
    WorkflowPackQueueAttentionSummaryResponse,
    WorkflowPackRunRuntimeSummaryResponse,
    WorkflowPackRuntimeStatusSummaryResponse,
    WorkflowPackTaskFlowAttentionItemResponse,
    WorkflowPackTaskFlowAttentionSummaryResponse,
)
from app.services.workflow_pack_bindings import list_workflow_pack_execution_binding_descriptors
from app.services.workflow_pack_registry import list_workflow_pack_registrations
from app.services.workflow_pack_queue_attention import (
    WORKFLOW_PACK_QUEUE_ATTENTION_LIMIT,
    build_workflow_pack_queue_attention_summary,
)
from app.services.workflow_pack_run_ledger import build_workflow_pack_run_catalog
from app.services.workflow_pack_run_provenance_summary import (
    build_workflow_pack_run_provenance_summary,
)
from app.services.runtime_readiness import (
    get_workflow_pack_registry_store_runtime_status,
    get_workflow_pack_queue_event_store_runtime_status,
    get_workflow_pack_run_store_runtime_status,
    get_workflow_pack_task_flow_store_runtime_status,
)
from app.services.workflow_pack_task_flow_service import list_task_flows

WORKFLOW_PACK_ATTENTION_QUEUE_LIMIT = 5
WORKFLOW_PACK_TASK_FLOW_ATTENTION_LIMIT = 5
WORKFLOW_PACK_TASK_FLOW_STALE_AFTER = timedelta(hours=24)


def build_workflow_pack_runtime_status_summary() -> WorkflowPackRuntimeStatusSummaryResponse:
    execution_bindings = list_workflow_pack_execution_binding_descriptors()
    registry_store_status = get_workflow_pack_registry_store_runtime_status()
    run_store_status = get_workflow_pack_run_store_runtime_status()
    task_flow_store_status = get_workflow_pack_task_flow_store_runtime_status()
    queue_event_store_status = get_workflow_pack_queue_event_store_runtime_status()
    registrations = (
        list_workflow_pack_registrations()
        if registry_store_status.status is RuntimeReadinessStatus.READY
        else []
    )
    binding_refs = {f"{binding.pack_id}@{binding.version}" for binding in execution_bindings}
    registered_registrations = [
        registration
        for registration in registrations
        if registration.registration_status.value == "REGISTERED"
    ]
    registered_registration_refs = [
        f"{registration.pack_id}@{registration.version}"
        for registration in registered_registrations
    ]
    executable_registrations = [
        registration
        for registration in registered_registrations
        if f"{registration.pack_id}@{registration.version}" in binding_refs
    ]
    executable_registration_refs = sorted(
        f"{registration.pack_id}@{registration.version}"
        for registration in executable_registrations
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
    if run_store_status.status is RuntimeReadinessStatus.READY:
        run_catalog = build_workflow_pack_run_catalog()
        executable_activity = build_workflow_pack_executable_activity_summary(
            executable_registration_refs=executable_registration_refs,
            run_catalog=run_catalog,
        )
        attention_queue = build_workflow_pack_attention_queue_summary(
            executable_registration_refs=executable_registration_refs,
            run_catalog=run_catalog,
        )
        run_summary = build_workflow_pack_run_runtime_summary(run_catalog=run_catalog)
    else:
        executable_activity = []
        attention_queue = WorkflowPackAttentionQueueSummaryResponse(
            queue_depth=0,
            queue_limit=WORKFLOW_PACK_ATTENTION_QUEUE_LIMIT,
            items=[],
            status_summary=[
                "Workflow-pack operator attention queue is unavailable until the configured run ledger store is ready.",
                f"Current workflow-pack run store status is `{run_store_status.status.value}`.",
            ],
        )
        run_summary = WorkflowPackRunRuntimeSummaryResponse(
            run_count=0,
            awaiting_review_count=0,
            accepted_count=0,
            rejected_count=0,
            abandoned_count=0,
            superseded_count=0,
            failed_count=0,
            expired_count=0,
            action_required_count=0,
            latest_recorded_at=None,
            status_summary=[
                "Workflow-pack run posture summary is unavailable until the configured run ledger store is ready.",
                f"Current workflow-pack run store status is `{run_store_status.status.value}`.",
            ],
        )

    if task_flow_store_status.status is RuntimeReadinessStatus.READY:
        task_flow_attention = build_workflow_pack_task_flow_attention_summary()
    else:
        task_flow_attention = WorkflowPackTaskFlowAttentionSummaryResponse(
            heartbeat_status="UNAVAILABLE",
            attention_count=0,
            waiting_for_review_count=0,
            blocked_count=0,
            degraded_count=0,
            stale_count=0,
            attention_limit=WORKFLOW_PACK_TASK_FLOW_ATTENTION_LIMIT,
            items=[],
            status_summary=[
                "Workflow-pack task-flow heartbeat attention is unavailable until the configured task-flow store is ready.",
                f"Current workflow-pack task-flow store status is `{task_flow_store_status.status.value}`.",
            ],
        )

    if (
        registry_store_status.status is RuntimeReadinessStatus.READY
        and queue_event_store_status.status is RuntimeReadinessStatus.READY
    ):
        queue_attention = build_workflow_pack_queue_attention_summary()
    else:
        blocking_store = (
            registry_store_status
            if registry_store_status.status is not RuntimeReadinessStatus.READY
            else queue_event_store_status
        )
        queue_attention = WorkflowPackQueueAttentionSummaryResponse(
            heartbeat_status="UNAVAILABLE",
            attention_count=0,
            saturated_lane_count=0,
            stale_item_count=0,
            terminal_event_count=0,
            recovery_blocked_count=0,
            failure_cluster_count=0,
            degraded_source_count=1,
            active_admission_count=0,
            queue_source_mode="unavailable",
            attention_limit=WORKFLOW_PACK_QUEUE_ATTENTION_LIMIT,
            items=[],
            status_summary=[
                "Workflow-pack queue heartbeat attention is unavailable until configured queue source stores are ready.",
                f"Current blocking queue source status is `{blocking_store.status.value}`.",
            ],
        )

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
        executable_activity=executable_activity,
        attention_queue=attention_queue,
        task_flow_attention=task_flow_attention,
        queue_attention=queue_attention,
        run_summary=run_summary,
        status_summary=[
            "Workflow-pack runtime readiness is narrower than catalog presence and counts only versions that are both REGISTERED and explicitly bound for lotus-ai execution.",
            "Executable workflow-pack versions are further split by whether the registered default execution mode still requires human review before downstream use.",
            "Registered workflow-pack versions without an explicit execution binding remain visible as governed catalog entries but are not yet executable through the current bounded lotus-ai runtime path.",
            "Per-pack activity summary shows whether executable workflow-pack versions are merely wired or are actually producing ledgered runs through the current bounded path.",
            "The operator attention queue highlights the newest actionable workflow-pack runs across executable pack versions without duplicating the full ledger catalog.",
            "Estate-level run posture is summarized separately so operators can see review backlog and action-required run state without reading the raw ledger catalog first.",
            "Use the workflow-pack registry detail surface for owner-artifact truth and the platform runtime status summary for estate-level execution readiness posture.",
            (
                "Registry-backed execution counts are unavailable until the configured workflow-pack registry store is ready."
                if registry_store_status.status is not RuntimeReadinessStatus.READY
                else "Registry-backed execution counts are available through the configured workflow-pack registry store."
            ),
            (
                "Run-ledger-backed activity posture is unavailable until the configured workflow-pack run store is ready."
                if run_store_status.status is not RuntimeReadinessStatus.READY
                else "Run-ledger-backed activity posture is available through the configured workflow-pack run store."
            ),
            (
                "Task-flow heartbeat attention is unavailable until the configured workflow-pack task-flow store is ready."
                if task_flow_store_status.status is not RuntimeReadinessStatus.READY
                else "Task-flow heartbeat attention is available through the configured workflow-pack task-flow store."
            ),
            (
                "Queue heartbeat attention is unavailable until the configured workflow-pack queue source stores are ready."
                if (
                    registry_store_status.status is not RuntimeReadinessStatus.READY
                    or queue_event_store_status.status is not RuntimeReadinessStatus.READY
                )
                else "Queue heartbeat attention is available through active-admission posture and durable queue-event source truth."
            ),
        ],
    )


def build_workflow_pack_run_runtime_summary(
    *,
    run_catalog: WorkflowPackRunCatalogResponse | None = None,
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
    return WorkflowPackRunRuntimeSummaryResponse(
        run_count=catalog.run_count,
        awaiting_review_count=catalog.awaiting_review_count,
        accepted_count=accepted_count,
        rejected_count=rejected_count,
        abandoned_count=abandoned_count,
        superseded_count=superseded_count,
        failed_count=failed_count,
        expired_count=expired_count,
        action_required_count=catalog.action_required_count,
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
    run_catalog: WorkflowPackRunCatalogResponse,
) -> list[WorkflowPackExecutableActivitySummaryResponse]:
    runs_by_registration_ref: dict[str, list[WorkflowPackRunDescriptor]] = {}
    for run in run_catalog.runs:
        runs_by_registration_ref.setdefault(run.registration_ref, []).append(run)

    summaries: list[WorkflowPackExecutableActivitySummaryResponse] = []
    for registration_ref in executable_registration_refs:
        pack_id, version = registration_ref.split("@", maxsplit=1)
        runs = runs_by_registration_ref.get(registration_ref, [])
        latest_run = max(runs, key=lambda run: run.created_at) if runs else None
        latest_action_required_run = _resolve_latest_run_by_supportability(
            runs=runs,
            target_status=WorkflowPackRunSupportabilityStatus.ACTION_REQUIRED,
        )
        latest_ready_run = _resolve_latest_run_by_supportability(
            runs=runs,
            target_status=WorkflowPackRunSupportabilityStatus.READY,
        )
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
                ready_count=sum(
                    1
                    for run in runs
                    if run.supportability_status is WorkflowPackRunSupportabilityStatus.READY
                ),
                action_required_count=sum(
                    1
                    for run in runs
                    if run.supportability_status
                    is WorkflowPackRunSupportabilityStatus.ACTION_REQUIRED
                ),
                historical_count=sum(
                    1
                    for run in runs
                    if run.supportability_status is WorkflowPackRunSupportabilityStatus.HISTORICAL
                ),
                latest_action_required_run_id=(
                    latest_action_required_run.run_id
                    if latest_action_required_run is not None
                    else None
                ),
                latest_action_required_recorded_at=(
                    latest_action_required_run.created_at
                    if latest_action_required_run is not None
                    else None
                ),
                latest_action_required_review_summary=(
                    latest_action_required_run.review_summary
                    if latest_action_required_run is not None
                    else None
                ),
                latest_action_required_provenance=(
                    build_workflow_pack_run_provenance_summary(run=latest_action_required_run)
                    if latest_action_required_run is not None
                    else None
                ),
                latest_ready_run_id=latest_ready_run.run_id
                if latest_ready_run is not None
                else None,
                latest_ready_recorded_at=(
                    latest_ready_run.created_at if latest_ready_run is not None else None
                ),
                latest_ready_review_summary=(
                    latest_ready_run.review_summary if latest_ready_run is not None else None
                ),
                latest_ready_provenance=(
                    build_workflow_pack_run_provenance_summary(run=latest_ready_run)
                    if latest_ready_run is not None
                    else None
                ),
                latest_run_id=latest_run.run_id if latest_run is not None else None,
                latest_recorded_at=latest_run.created_at if latest_run is not None else None,
                has_activity=bool(runs),
            )
        )
    return summaries


def build_workflow_pack_attention_queue_summary(
    *,
    executable_registration_refs: list[str],
    run_catalog: WorkflowPackRunCatalogResponse,
) -> WorkflowPackAttentionQueueSummaryResponse:
    executable_registration_ref_set = set(executable_registration_refs)
    actionable_runs: list[WorkflowPackRunDescriptor] = []
    for run in run_catalog.runs:
        if run.registration_ref not in executable_registration_ref_set:
            continue
        if run.supportability_status is WorkflowPackRunSupportabilityStatus.ACTION_REQUIRED:
            actionable_runs.append(run)
    actionable_runs.sort(key=lambda item: item.created_at, reverse=True)
    queue_depth = len(actionable_runs)
    queue_items = [
        WorkflowPackAttentionQueueItemResponse(
            run_id=run.run_id,
            registration_ref=run.registration_ref,
            pack_id=run.pack_id,
            workflow_authority_owner=run.workflow_authority_owner,
            review_state=run.review_state.value,
            runtime_state=run.runtime_state.value,
            supportability_status=run.supportability_status.value,
            review_summary=run.review_summary,
            provenance=build_workflow_pack_run_provenance_summary(run=run),
            created_at=run.created_at,
        )
        for run in actionable_runs[:WORKFLOW_PACK_ATTENTION_QUEUE_LIMIT]
    ]
    status_summary = [
        "The workflow-pack attention queue is derived from the shared run-supportability seam and only includes actionable runs from explicitly executable pack versions.",
        "Use the queue as a pivot into run detail and operator-profile routes, not as a replacement for the full bounded run ledger.",
        "Newest actionable runs are prioritized first so operators can address fresh review backlog or failure posture without scanning every executable pack summary.",
    ]
    if queue_depth > WORKFLOW_PACK_ATTENTION_QUEUE_LIMIT:
        status_summary.append(
            "Returned queue items are truncated to the bounded queue limit; use queue_depth to measure the full actionable backlog."
        )
    return WorkflowPackAttentionQueueSummaryResponse(
        queue_depth=queue_depth,
        queue_limit=WORKFLOW_PACK_ATTENTION_QUEUE_LIMIT,
        items=queue_items,
        status_summary=status_summary,
    )


def build_workflow_pack_task_flow_attention_summary(
    *,
    task_flows: list[WorkflowPackTaskFlowDescriptor] | None = None,
    now_utc: datetime | None = None,
) -> WorkflowPackTaskFlowAttentionSummaryResponse:
    flows = task_flows if task_flows is not None else list_task_flows()
    now = now_utc or datetime.now(UTC)
    attention_items = [
        item for item in (_build_task_flow_attention_item(flow, now=now) for flow in flows) if item
    ]
    attention_items.sort(key=lambda item: item.updated_at, reverse=True)
    waiting_for_review_count = sum(
        1 for flow in flows if flow.flow_status is WorkflowPackTaskFlowStatus.WAITING_FOR_REVIEW
    )
    blocked_count = sum(
        1 for flow in flows if flow.flow_status is WorkflowPackTaskFlowStatus.BLOCKED
    )
    degraded_count = sum(
        1
        for flow in flows
        if flow.supportability_status is WorkflowPackRunSupportabilityStatus.ACTION_REQUIRED
    )
    stale_count = sum(1 for flow in flows if _is_stale_task_flow(flow, now=now))
    heartbeat_status = "READY" if not attention_items else "ATTENTION_REQUIRED"
    status_summary = [
        "Workflow-pack task-flow heartbeat attention is derived from durable task-flow posture and does not replace run-ledger review authority.",
        "Waiting-for-review, blocked, degraded, and stale active task flows are surfaced as bounded attention items.",
    ]
    if len(attention_items) > WORKFLOW_PACK_TASK_FLOW_ATTENTION_LIMIT:
        status_summary.append(
            "Returned task-flow attention items are truncated to the bounded attention limit; use attention_count to measure the full backlog."
        )
    return WorkflowPackTaskFlowAttentionSummaryResponse(
        heartbeat_status=heartbeat_status,
        attention_count=len(attention_items),
        waiting_for_review_count=waiting_for_review_count,
        blocked_count=blocked_count,
        degraded_count=degraded_count,
        stale_count=stale_count,
        attention_limit=WORKFLOW_PACK_TASK_FLOW_ATTENTION_LIMIT,
        items=attention_items[:WORKFLOW_PACK_TASK_FLOW_ATTENTION_LIMIT],
        status_summary=status_summary,
    )


def _resolve_latest_run_by_supportability(
    *,
    runs: list[WorkflowPackRunDescriptor],
    target_status: WorkflowPackRunSupportabilityStatus,
) -> WorkflowPackRunDescriptor | None:
    matching_runs = [run for run in runs if run.supportability_status is target_status]
    if not matching_runs:
        return None
    return max(matching_runs, key=lambda run: run.created_at)


def _build_task_flow_attention_item(
    flow: WorkflowPackTaskFlowDescriptor,
    *,
    now: datetime,
) -> WorkflowPackTaskFlowAttentionItemResponse | None:
    attention_reasons = _task_flow_attention_reasons(flow, now=now)
    if not attention_reasons:
        return None
    return WorkflowPackTaskFlowAttentionItemResponse(
        task_flow_id=flow.task_flow_id,
        workflow_pack_id=flow.workflow_pack_id,
        workflow_pack_version=flow.workflow_pack_version,
        flow_status=flow.flow_status.value,
        supportability_status=flow.supportability_status.value,
        current_step_id=flow.current_step_id,
        run_refs=flow.run_refs,
        replacement_lineage_count=len(flow.replacement_lineage),
        updated_at=flow.updated_at,
        attention_reasons=attention_reasons,
    )


def _task_flow_attention_reasons(
    flow: WorkflowPackTaskFlowDescriptor,
    *,
    now: datetime,
) -> list[str]:
    reasons: list[str] = []
    if flow.flow_status is WorkflowPackTaskFlowStatus.WAITING_FOR_REVIEW:
        reasons.append("Task flow is waiting for bounded human review.")
    if flow.flow_status is WorkflowPackTaskFlowStatus.BLOCKED:
        reasons.append("Task flow is blocked and requires operator triage.")
    if flow.supportability_status is WorkflowPackRunSupportabilityStatus.ACTION_REQUIRED:
        reasons.append("Task flow supportability requires operator action.")
    if _is_stale_task_flow(flow, now=now):
        reasons.append("Task flow has not advanced within the heartbeat stale threshold.")
    return reasons


def _is_stale_task_flow(flow: WorkflowPackTaskFlowDescriptor, *, now: datetime) -> bool:
    if flow.flow_status not in {
        WorkflowPackTaskFlowStatus.CREATED,
        WorkflowPackTaskFlowStatus.RUNNING,
        WorkflowPackTaskFlowStatus.WAITING_FOR_INPUT,
        WorkflowPackTaskFlowStatus.WAITING_FOR_REVIEW,
        WorkflowPackTaskFlowStatus.BLOCKED,
    }:
        return False
    updated_at = _parse_utc_timestamp(flow.updated_at)
    if updated_at is None:
        return True
    return now - updated_at > WORKFLOW_PACK_TASK_FLOW_STALE_AFTER


def _parse_utc_timestamp(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
