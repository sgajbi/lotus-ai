from _pytest.monkeypatch import MonkeyPatch
from datetime import UTC, datetime, timedelta

from app.contracts.runtime_readiness import RuntimeReadinessStatus, StoreRuntimeStatusDescriptor
from app.contracts.workflow_pack_runs import (
    WorkflowPackRunCatalogResponse,
    WorkflowPackRunReviewActionType,
    WorkflowPackRunReviewState,
    WorkflowPackRunRuntimeState,
    WorkflowPackRunSupportabilityStatus,
)
from app.contracts.workflow_pack_queue_policies import (
    WorkflowPackQueueCancellationActor,
    WorkflowPackQueueEventType,
    WorkflowPackQueueState,
)
from app.contracts.workflow_packs import WorkflowPackExecutionMode, WorkflowPackRegistrationStatus
from app.services.workflow_pack_bindings import get_workflow_pack_execution_binding_descriptor
from app.services.workflow_pack_registry import get_workflow_pack_registration
from app.services.workflow_pack_queue_attention import (
    build_workflow_pack_queue_attention_summary,
)
from app.services.workflow_pack_runtime_status import (
    build_workflow_pack_task_flow_attention_summary,
    build_workflow_pack_run_runtime_summary,
    build_workflow_pack_runtime_status_summary,
)
from app.services.workflow_pack_queue_admission import (
    acquire_workflow_pack_queue_admission,
    cancel_workflow_pack_queue_admission,
    release_workflow_pack_queue_admission,
)
from app.services.workflow_pack_queue_events import record_workflow_pack_queue_event
from app.contracts.workflow_pack_task_flows import WorkflowPackTaskFlowStatus
from tests.support.workflow_pack_task_flow_fixtures import workflow_pack_task_flow_descriptor
from tests.support.workflow_pack_run_builders import build_workflow_pack_run_descriptor


def test_build_workflow_pack_runtime_status_summary_separates_catalog_from_execution_readiness(
    monkeypatch: MonkeyPatch,
) -> None:
    registered = get_workflow_pack_registration(pack_id="advisor_brief.pack", version="v1")
    discovered = get_workflow_pack_registration(pack_id="advisor_brief.pack", version="v2")
    binding = get_workflow_pack_execution_binding_descriptor(
        pack_id="advisor_brief.pack",
        version="v1",
    )

    assert registered is not None
    assert discovered is not None
    assert binding is not None

    monkeypatch.setattr(
        "app.services.workflow_pack_runtime_status.list_workflow_pack_registrations",
        lambda: [
            registered,
            discovered.model_copy(
                update={"registration_status": WorkflowPackRegistrationStatus.REGISTERED}
            ),
        ],
    )
    monkeypatch.setattr(
        "app.services.workflow_pack_runtime_status.list_workflow_pack_execution_binding_descriptors",
        lambda: [binding],
    )

    summary = build_workflow_pack_runtime_status_summary()

    assert summary.registration_count == 2
    assert summary.registered_count == 2
    assert summary.execution_binding_count == 1
    assert summary.executable_registration_count == 1
    assert summary.executable_review_required_count == 1
    assert summary.executable_without_review_count == 0
    assert summary.registered_without_execution_binding_count == 1
    assert summary.executable_registration_refs == ["advisor_brief.pack@v1"]
    assert summary.executable_review_required_refs == ["advisor_brief.pack@v1"]
    assert len(summary.executable_activity) == 1
    assert summary.executable_activity[0].registration_ref == "advisor_brief.pack@v1"
    assert summary.executable_activity[0].run_count == 0
    assert summary.executable_activity[0].ready_count == 0
    assert summary.executable_activity[0].action_required_count == 0
    assert summary.executable_activity[0].historical_count == 0
    assert summary.executable_activity[0].latest_action_required_run_id is None
    assert summary.executable_activity[0].latest_ready_run_id is None
    assert summary.executable_activity[0].latest_run_id is None
    assert summary.executable_activity[0].has_activity is False
    assert summary.attention_queue.queue_depth == 0
    assert summary.attention_queue.queue_limit == 5
    assert summary.attention_queue.items == []
    assert summary.task_flow_attention.heartbeat_status == "READY"
    assert summary.task_flow_attention.attention_count == 0
    assert summary.queue_attention.heartbeat_status == "READY"
    assert summary.queue_attention.attention_count == 0
    assert summary.run_summary.run_count == 0
    assert summary.run_summary.action_required_count == 0


def test_build_workflow_pack_runtime_status_summary_tracks_non_review_gated_execution(
    monkeypatch: MonkeyPatch,
) -> None:
    registered = get_workflow_pack_registration(pack_id="advisor_brief.pack", version="v1")
    binding = get_workflow_pack_execution_binding_descriptor(
        pack_id="advisor_brief.pack",
        version="v1",
    )

    assert registered is not None
    assert binding is not None

    monkeypatch.setattr(
        "app.services.workflow_pack_runtime_status.list_workflow_pack_registrations",
        lambda: [
            registered.model_copy(
                update={"default_execution_mode": WorkflowPackExecutionMode.SYNCHRONOUS}
            )
        ],
    )
    monkeypatch.setattr(
        "app.services.workflow_pack_runtime_status.list_workflow_pack_execution_binding_descriptors",
        lambda: [binding],
    )

    summary = build_workflow_pack_runtime_status_summary()

    assert summary.registration_count == 1
    assert summary.registered_count == 1
    assert summary.executable_registration_count == 1
    assert summary.executable_review_required_count == 0
    assert summary.executable_without_review_count == 1
    assert summary.executable_review_required_refs == []


def test_build_workflow_pack_runtime_status_summary_tracks_activity_for_executable_pack(
    monkeypatch: MonkeyPatch,
) -> None:
    registered = get_workflow_pack_registration(pack_id="advisor_brief.pack", version="v1")
    binding = get_workflow_pack_execution_binding_descriptor(
        pack_id="advisor_brief.pack",
        version="v1",
    )

    assert registered is not None
    assert binding is not None

    monkeypatch.setattr(
        "app.services.workflow_pack_runtime_status.list_workflow_pack_registrations",
        lambda: [registered],
    )
    monkeypatch.setattr(
        "app.services.workflow_pack_runtime_status.list_workflow_pack_execution_binding_descriptors",
        lambda: [binding],
    )
    monkeypatch.setattr(
        "app.services.workflow_pack_runtime_status.build_workflow_pack_run_catalog",
        lambda: WorkflowPackRunCatalogResponse(
            service="lotus-ai",
            version="0.1.0",
            phase="foundation",
            run_store_mode="memory",
            run_count=2,
            awaiting_review_count=1,
            completed_count=2,
            ready_count=1,
            action_required_count=1,
            historical_count=0,
            latest_recorded_at="2026-04-19T12:00:00Z",
            runs=[
                build_workflow_pack_run_descriptor(
                    run_id="run-awaiting",
                    review_state=WorkflowPackRunReviewState.AWAITING_REVIEW,
                    created_at="2026-04-19T11:00:00Z",
                    evidence_descriptors_count=1,
                    artifact_refs_count=1,
                ),
                build_workflow_pack_run_descriptor(
                    run_id="run-accepted",
                    review_state=WorkflowPackRunReviewState.ACCEPTED,
                    allowed_review_actions=[WorkflowPackRunReviewActionType.SUPERSEDE],
                    created_at="2026-04-19T12:00:00Z",
                    evidence_descriptors_count=1,
                    artifact_refs_count=1,
                ),
            ],
            notes=["summary"],
        ),
    )

    summary = build_workflow_pack_runtime_status_summary()

    assert len(summary.executable_activity) == 1
    assert summary.executable_activity[0].registration_ref == "advisor_brief.pack@v1"
    assert summary.executable_activity[0].run_count == 2
    assert summary.executable_activity[0].awaiting_review_count == 1
    assert summary.executable_activity[0].accepted_count == 1
    assert summary.executable_activity[0].ready_count == 1
    assert summary.executable_activity[0].action_required_count == 1
    assert summary.executable_activity[0].historical_count == 0
    assert summary.executable_activity[0].latest_action_required_run_id == "run-awaiting"
    assert (
        summary.executable_activity[0].latest_action_required_recorded_at == "2026-04-19T11:00:00Z"
    )
    latest_action_required_review_summary = summary.executable_activity[
        0
    ].latest_action_required_review_summary
    assert latest_action_required_review_summary is not None
    assert latest_action_required_review_summary.review_transition_count == 0
    assert latest_action_required_review_summary.has_review_history is False
    latest_action_required_provenance = summary.executable_activity[
        0
    ].latest_action_required_provenance
    assert latest_action_required_provenance is not None
    assert latest_action_required_provenance.artifact_ref_count == 1
    assert latest_action_required_provenance.artifact_types == ["run_output_summary"]
    assert latest_action_required_provenance.evidence_descriptor_count == 1
    assert latest_action_required_provenance.evidence_types == ["evidence_0"]
    assert summary.executable_activity[0].latest_ready_run_id == "run-accepted"
    assert summary.executable_activity[0].latest_ready_recorded_at == "2026-04-19T12:00:00Z"
    latest_ready_review_summary = summary.executable_activity[0].latest_ready_review_summary
    assert latest_ready_review_summary is not None
    assert latest_ready_review_summary.review_transition_count == 0
    assert latest_ready_review_summary.has_review_history is False
    latest_ready_provenance = summary.executable_activity[0].latest_ready_provenance
    assert latest_ready_provenance is not None
    assert latest_ready_provenance.artifact_ref_count == 1
    assert latest_ready_provenance.evidence_descriptor_count == 1
    assert summary.executable_activity[0].latest_run_id == "run-accepted"
    assert summary.executable_activity[0].latest_recorded_at == "2026-04-19T12:00:00Z"
    assert summary.executable_activity[0].has_activity is True
    assert summary.attention_queue.queue_depth == 1
    assert summary.attention_queue.items[0].run_id == "run-awaiting"
    assert summary.attention_queue.items[0].registration_ref == "advisor_brief.pack@v1"
    assert summary.attention_queue.items[0].supportability_status == "ACTION_REQUIRED"
    assert summary.attention_queue.items[0].review_state == "AWAITING_REVIEW"
    assert summary.attention_queue.items[0].runtime_state == "COMPLETED"
    assert summary.attention_queue.items[0].review_summary.review_transition_count == 0
    assert summary.attention_queue.items[0].review_summary.has_review_history is False
    assert summary.attention_queue.items[0].provenance.artifact_ref_count == 1
    assert summary.attention_queue.items[0].provenance.artifact_types == ["run_output_summary"]
    assert summary.attention_queue.items[0].provenance.evidence_descriptor_count == 1
    assert summary.attention_queue.items[0].provenance.evidence_types == ["evidence_0"]
    assert summary.task_flow_attention.heartbeat_status == "READY"


def test_build_workflow_pack_runtime_status_summary_defaults_include_all_executable_phase1_packs() -> (
    None
):
    summary = build_workflow_pack_runtime_status_summary()

    assert summary.registration_count == 5
    assert summary.registered_count == 4
    assert summary.execution_binding_count == 4
    assert summary.executable_registration_count == 4
    assert summary.executable_review_required_count == 4
    assert summary.registered_without_execution_binding_count == 0
    assert summary.executable_registration_refs == [
        "advisor_brief.pack@v1",
        "outcome_review_narrative.pack@v1",
        "twr_inspection_support_brief.pack@v1",
        "workspace_rationale.pack@v1",
    ]
    assert summary.executable_review_required_refs == [
        "advisor_brief.pack@v1",
        "outcome_review_narrative.pack@v1",
        "twr_inspection_support_brief.pack@v1",
        "workspace_rationale.pack@v1",
    ]


def test_build_workflow_pack_task_flow_attention_summary_surfaces_heartbeat_posture() -> None:
    summary = build_workflow_pack_task_flow_attention_summary(
        task_flows=[
            workflow_pack_task_flow_descriptor(
                task_flow_id="flow-review",
                flow_status=WorkflowPackTaskFlowStatus.WAITING_FOR_REVIEW,
                current_step_id="draft-brief",
                updated_at="2026-04-21T01:00:00Z",
            ),
            workflow_pack_task_flow_descriptor(
                task_flow_id="flow-blocked-stale",
                flow_status=WorkflowPackTaskFlowStatus.BLOCKED,
                current_step_id="draft-brief",
                updated_at="2026-04-19T01:00:00Z",
            ),
            workflow_pack_task_flow_descriptor(
                task_flow_id="flow-completed",
                flow_status=WorkflowPackTaskFlowStatus.COMPLETED,
                current_step_id=None,
                updated_at="2026-04-18T01:00:00Z",
            ).model_copy(
                update={"supportability_status": WorkflowPackRunSupportabilityStatus.READY}
            ),
        ],
        now_utc=datetime(2026, 4, 21, 3, 0, tzinfo=UTC),
    )

    assert summary.heartbeat_status == "ATTENTION_REQUIRED"
    assert summary.attention_count == 2
    assert summary.waiting_for_review_count == 1
    assert summary.blocked_count == 1
    assert summary.degraded_count == 2
    assert summary.stale_count == 1
    assert [item.task_flow_id for item in summary.items] == [
        "flow-review",
        "flow-blocked-stale",
    ]
    assert summary.items[0].attention_reasons == [
        "Task flow is waiting for bounded human review.",
        "Task flow supportability requires operator action.",
    ]
    assert summary.items[1].attention_reasons == [
        "Task flow is blocked and requires operator triage.",
        "Task flow supportability requires operator action.",
        "Task flow has not advanced within the heartbeat stale threshold.",
    ]


def test_build_workflow_pack_queue_attention_summary_surfaces_saturation_and_stale_posture() -> (
    None
):
    registration = get_workflow_pack_registration(pack_id="advisor_brief.pack", version="v1")
    assert registration is not None
    leases = [
        acquire_workflow_pack_queue_admission(registration=registration),
        acquire_workflow_pack_queue_admission(registration=registration),
    ]

    try:
        summary = build_workflow_pack_queue_attention_summary(
            now_utc=datetime.now(UTC) + timedelta(hours=1),
        )
    finally:
        for lease in leases:
            release_workflow_pack_queue_admission(lease.queue_item_id)

    assert summary.heartbeat_status == "ATTENTION_REQUIRED"
    assert summary.attention_count == 3
    assert summary.saturated_lane_count == 1
    assert summary.stale_item_count == 2
    assert summary.active_admission_count == 2
    assert summary.queue_source_mode == "memory"
    assert [item.attention_type for item in summary.items] == [
        "LANE_SATURATED",
        "QUEUE_ITEM_STALE",
        "QUEUE_ITEM_STALE",
    ]
    assert summary.items[0].workflow_pack_id == "advisor_brief.pack"
    assert summary.items[0].lane.value == "LATENCY_SENSITIVE"
    assert summary.items[0].active_count == 2
    assert summary.items[1].queue_item_id == leases[0].queue_item_id
    assert summary.items[1].admitted_at == leases[0].admitted_at
    assert any("Durable queue events now preserve" in line for line in summary.status_summary)


def test_build_workflow_pack_queue_attention_summary_surfaces_terminal_event_posture() -> None:
    registration = get_workflow_pack_registration(pack_id="advisor_brief.pack", version="v1")
    assert registration is not None
    timed_out_lease = acquire_workflow_pack_queue_admission(registration=registration)
    release_workflow_pack_queue_admission(
        timed_out_lease.queue_item_id,
        now_utc=datetime.now(UTC) + timedelta(minutes=10),
    )
    cancelled_lease = acquire_workflow_pack_queue_admission(registration=registration)
    cancel_workflow_pack_queue_admission(
        cancelled_lease.queue_item_id,
        actor=WorkflowPackQueueCancellationActor.OPERATOR,
        reason="Operator cancelled stale queue admission.",
        evidence_ref="support-ticket-queue-1",
    )
    record_workflow_pack_queue_event(
        queue_item_id="wpq_degraded_worker_001",
        event_type=WorkflowPackQueueEventType.ADMISSION_DEGRADED,
        workflow_pack_id="advisor_brief.pack",
        workflow_pack_version="v1",
        policy_id="queue-policy.advisor-brief.v1",
        lane=timed_out_lease.lane,
        state=WorkflowPackQueueState.DEGRADED,
        caller_app="lotus-gateway",
        correlation_id="corr-degraded-worker-001",
        tenant_id="tenant-sg-001",
        workflow_surface="advisor-brief-workspace",
        reason_code="WORKER_FAILURE",
        message="Workflow-pack queued worker execution degraded before completed handoff.",
    )

    summary = build_workflow_pack_queue_attention_summary()

    terminal_items = [
        item
        for item in summary.items
        if item.attention_type
        in {"QUEUE_ITEM_CANCELLED", "QUEUE_ITEM_TIMED_OUT", "QUEUE_ITEM_DEGRADED"}
    ]
    assert summary.heartbeat_status == "ATTENTION_REQUIRED"
    assert summary.terminal_event_count == 3
    assert [item.attention_type for item in terminal_items] == [
        "QUEUE_ITEM_DEGRADED",
        "QUEUE_ITEM_CANCELLED",
        "QUEUE_ITEM_TIMED_OUT",
    ]
    assert {item.active_count for item in terminal_items} == {0}


def test_build_workflow_pack_run_runtime_summary_counts_action_required_and_historical_posture(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.workflow_pack_runtime_status.build_workflow_pack_run_catalog",
        lambda: WorkflowPackRunCatalogResponse(
            service="lotus-ai",
            version="0.1.0",
            phase="foundation",
            run_store_mode="memory",
            run_count=5,
            awaiting_review_count=1,
            completed_count=5,
            ready_count=1,
            action_required_count=3,
            historical_count=1,
            latest_recorded_at="2026-04-19T12:00:00Z",
            runs=[
                build_workflow_pack_run_descriptor(
                    run_id="run-awaiting",
                    review_state=WorkflowPackRunReviewState.AWAITING_REVIEW,
                ),
                build_workflow_pack_run_descriptor(
                    run_id="run-accepted",
                    review_state=WorkflowPackRunReviewState.ACCEPTED,
                    allowed_review_actions=[WorkflowPackRunReviewActionType.SUPERSEDE],
                ),
                build_workflow_pack_run_descriptor(
                    run_id="run-rejected",
                    review_state=WorkflowPackRunReviewState.REJECTED,
                ),
                build_workflow_pack_run_descriptor(
                    run_id="run-failed",
                    runtime_state=WorkflowPackRunRuntimeState.FAILED,
                ),
                build_workflow_pack_run_descriptor(
                    run_id="run-superseded",
                    review_state=WorkflowPackRunReviewState.SUPERSEDED,
                    superseded_by_run_id="run-replacement",
                ),
            ],
            notes=["summary"],
        ),
    )

    summary = build_workflow_pack_run_runtime_summary()

    assert summary.run_count == 5
    assert summary.awaiting_review_count == 1
    assert summary.accepted_count == 1
    assert summary.rejected_count == 1
    assert summary.abandoned_count == 0
    assert summary.superseded_count == 1
    assert summary.failed_count == 1
    assert summary.expired_count == 0
    assert summary.action_required_count == 3
    assert summary.latest_recorded_at == "2026-04-19T12:00:00Z"


def test_build_workflow_pack_attention_queue_summary_limits_to_latest_actionable_runs(
    monkeypatch: MonkeyPatch,
) -> None:
    registered = get_workflow_pack_registration(pack_id="advisor_brief.pack", version="v1")
    binding = get_workflow_pack_execution_binding_descriptor(
        pack_id="advisor_brief.pack",
        version="v1",
    )

    assert registered is not None
    assert binding is not None

    monkeypatch.setattr(
        "app.services.workflow_pack_runtime_status.list_workflow_pack_registrations",
        lambda: [registered],
    )
    monkeypatch.setattr(
        "app.services.workflow_pack_runtime_status.list_workflow_pack_execution_binding_descriptors",
        lambda: [binding],
    )
    monkeypatch.setattr(
        "app.services.workflow_pack_runtime_status.build_workflow_pack_run_catalog",
        lambda: WorkflowPackRunCatalogResponse(
            service="lotus-ai",
            version="0.1.0",
            phase="foundation",
            run_store_mode="memory",
            run_count=6,
            awaiting_review_count=6,
            completed_count=6,
            ready_count=0,
            action_required_count=6,
            historical_count=0,
            latest_recorded_at="2026-04-19T16:00:00Z",
            runs=[
                build_workflow_pack_run_descriptor(
                    run_id=f"run-action-{index}",
                    review_state=WorkflowPackRunReviewState.AWAITING_REVIEW,
                    created_at=f"2026-04-19T1{index}:00:00Z",
                    evidence_descriptors_count=1,
                    artifact_refs_count=1,
                    latest_review_event_at=(
                        f"2026-04-19T0{index}:30:00Z" if index < 6 else "2026-04-19T16:30:00Z"
                    ),
                    latest_review_actor=f"review:banker.sg.{index}",
                    review_transition_count=index,
                )
                for index in range(1, 7)
            ],
            notes=["summary"],
        ),
    )

    summary = build_workflow_pack_runtime_status_summary()

    assert summary.attention_queue.queue_depth == 6
    assert summary.attention_queue.queue_limit == 5
    assert [item.run_id for item in summary.attention_queue.items] == [
        "run-action-6",
        "run-action-5",
        "run-action-4",
        "run-action-3",
        "run-action-2",
    ]
    assert (
        summary.attention_queue.items[0].review_summary.latest_review_actor == "review:banker.sg.6"
    )
    assert summary.attention_queue.items[0].review_summary.review_transition_count == 6
    assert summary.attention_queue.items[0].review_summary.has_review_history is True
    assert summary.attention_queue.items[0].provenance.artifact_ref_count == 1
    assert summary.attention_queue.items[0].provenance.evidence_descriptor_count == 1
    assert any(
        "use queue_depth to measure the full actionable backlog" in line
        for line in summary.attention_queue.status_summary
    )


def test_build_workflow_pack_runtime_status_summary_uses_descriptor_supportability_posture(
    monkeypatch: MonkeyPatch,
) -> None:
    registered = get_workflow_pack_registration(pack_id="advisor_brief.pack", version="v1")
    binding = get_workflow_pack_execution_binding_descriptor(
        pack_id="advisor_brief.pack",
        version="v1",
    )

    assert registered is not None
    assert binding is not None

    monkeypatch.setattr(
        "app.services.workflow_pack_runtime_status.list_workflow_pack_registrations",
        lambda: [registered],
    )
    monkeypatch.setattr(
        "app.services.workflow_pack_runtime_status.list_workflow_pack_execution_binding_descriptors",
        lambda: [binding],
    )
    monkeypatch.setattr(
        "app.services.workflow_pack_runtime_status.build_workflow_pack_run_catalog",
        lambda: WorkflowPackRunCatalogResponse(
            service="lotus-ai",
            version="0.1.0",
            phase="foundation",
            run_store_mode="memory",
            run_count=1,
            awaiting_review_count=0,
            completed_count=1,
            ready_count=0,
            action_required_count=1,
            historical_count=0,
            latest_recorded_at="2026-04-19T12:00:00Z",
            runs=[
                build_workflow_pack_run_descriptor(
                    run_id="run-accepted-action-required",
                    review_state=WorkflowPackRunReviewState.ACCEPTED,
                    created_at="2026-04-19T12:00:00Z",
                    evidence_descriptors_count=1,
                    artifact_refs_count=1,
                    supportability_status=WorkflowPackRunSupportabilityStatus.ACTION_REQUIRED,
                )
            ],
            notes=["summary"],
        ),
    )

    summary = build_workflow_pack_runtime_status_summary()

    assert summary.run_summary.action_required_count == 1
    assert summary.executable_activity[0].ready_count == 0
    assert summary.executable_activity[0].action_required_count == 1
    assert summary.executable_activity[0].latest_action_required_run_id == (
        "run-accepted-action-required"
    )
    assert summary.executable_activity[0].latest_ready_run_id is None
    assert summary.attention_queue.queue_depth == 1
    assert summary.attention_queue.items[0].run_id == "run-accepted-action-required"
    assert summary.attention_queue.items[0].supportability_status == "ACTION_REQUIRED"


def test_build_workflow_pack_runtime_status_summary_degrades_when_registry_store_not_ready(
    monkeypatch: MonkeyPatch,
) -> None:
    binding = get_workflow_pack_execution_binding_descriptor(
        pack_id="advisor_brief.pack",
        version="v1",
    )
    assert binding is not None

    monkeypatch.setattr(
        "app.services.workflow_pack_runtime_status.list_workflow_pack_execution_binding_descriptors",
        lambda: [binding],
    )
    monkeypatch.setattr(
        "app.services.workflow_pack_runtime_status.get_workflow_pack_registry_store_runtime_status",
        lambda: StoreRuntimeStatusDescriptor(
            mode="sqlalchemy",
            status=RuntimeReadinessStatus.MIGRATION_REQUIRED,
            database_configured=True,
            detail="Registry tables are missing.",
        ),
    )
    monkeypatch.setattr(
        "app.services.workflow_pack_runtime_status.get_workflow_pack_run_store_runtime_status",
        lambda: StoreRuntimeStatusDescriptor(
            mode="memory",
            status=RuntimeReadinessStatus.READY,
            database_configured=False,
            detail="Run store is ready.",
        ),
    )

    summary = build_workflow_pack_runtime_status_summary()

    assert summary.registration_count == 0
    assert summary.registered_count == 0
    assert summary.execution_binding_count == 1
    assert summary.executable_registration_count == 0
    assert summary.executable_registration_refs == []
    assert any(
        "Registry-backed execution counts are unavailable" in line
        for line in summary.status_summary
    )
    assert summary.queue_attention.heartbeat_status == "UNAVAILABLE"
    assert summary.queue_attention.queue_source_mode == "unavailable"
    assert summary.queue_attention.degraded_source_count == 1
    assert any(
        "blocking queue source status" in line for line in summary.queue_attention.status_summary
    )


def test_build_workflow_pack_runtime_status_summary_degrades_when_run_store_not_ready(
    monkeypatch: MonkeyPatch,
) -> None:
    registered = get_workflow_pack_registration(pack_id="advisor_brief.pack", version="v1")
    binding = get_workflow_pack_execution_binding_descriptor(
        pack_id="advisor_brief.pack",
        version="v1",
    )

    assert registered is not None
    assert binding is not None

    monkeypatch.setattr(
        "app.services.workflow_pack_runtime_status.list_workflow_pack_registrations",
        lambda: [registered],
    )
    monkeypatch.setattr(
        "app.services.workflow_pack_runtime_status.list_workflow_pack_execution_binding_descriptors",
        lambda: [binding],
    )
    monkeypatch.setattr(
        "app.services.workflow_pack_runtime_status.get_workflow_pack_registry_store_runtime_status",
        lambda: StoreRuntimeStatusDescriptor(
            mode="memory",
            status=RuntimeReadinessStatus.READY,
            database_configured=False,
            detail="Registry store is ready.",
        ),
    )
    monkeypatch.setattr(
        "app.services.workflow_pack_runtime_status.get_workflow_pack_run_store_runtime_status",
        lambda: StoreRuntimeStatusDescriptor(
            mode="sqlalchemy",
            status=RuntimeReadinessStatus.MIGRATION_REQUIRED,
            database_configured=True,
            detail="Run tables are missing.",
        ),
    )

    summary = build_workflow_pack_runtime_status_summary()

    assert summary.registration_count == 1
    assert summary.execution_binding_count == 1
    assert summary.executable_registration_count == 1
    assert summary.executable_activity == []
    assert summary.attention_queue.queue_depth == 0
    assert summary.run_summary.run_count == 0
    assert summary.run_summary.action_required_count == 0
    assert any(
        "Run-ledger-backed activity posture is unavailable" in line
        for line in summary.status_summary
    )
    assert any(
        "Current workflow-pack run store status is `MIGRATION_REQUIRED`." == line
        for line in summary.attention_queue.status_summary
    )
