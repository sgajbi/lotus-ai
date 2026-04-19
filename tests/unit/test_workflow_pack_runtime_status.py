from _pytest.monkeypatch import MonkeyPatch

from app.contracts.workflow_pack_runs import (
    WorkflowPackRunCatalogResponse,
    WorkflowPackRunDescriptor,
    WorkflowPackRunReviewActionType,
    WorkflowPackRunReviewState,
    WorkflowPackRunRuntimeState,
)
from app.contracts.workflow_packs import WorkflowPackExecutionMode, WorkflowPackRegistrationStatus
from app.services.workflow_pack_bindings import get_workflow_pack_execution_binding_descriptor
from app.services.workflow_pack_registry import get_workflow_pack_registration
from app.services.workflow_pack_runtime_status import (
    build_workflow_pack_run_runtime_summary,
    build_workflow_pack_runtime_status_summary,
)


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
    assert summary.executable_activity[0].latest_run_id is None
    assert summary.executable_activity[0].has_activity is False
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
            latest_recorded_at="2026-04-19T12:00:00Z",
            runs=[
                _build_run(
                    run_id="run-awaiting",
                    review_state=WorkflowPackRunReviewState.AWAITING_REVIEW,
                    created_at="2026-04-19T11:00:00Z",
                ),
                _build_run(
                    run_id="run-accepted",
                    review_state=WorkflowPackRunReviewState.ACCEPTED,
                    allowed_review_actions=[WorkflowPackRunReviewActionType.SUPERSEDE],
                    created_at="2026-04-19T12:00:00Z",
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
    assert summary.executable_activity[0].latest_run_id == "run-accepted"
    assert summary.executable_activity[0].latest_recorded_at == "2026-04-19T12:00:00Z"
    assert summary.executable_activity[0].has_activity is True


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
            latest_recorded_at="2026-04-19T12:00:00Z",
            runs=[
                _build_run(
                    run_id="run-awaiting",
                    review_state=WorkflowPackRunReviewState.AWAITING_REVIEW,
                ),
                _build_run(
                    run_id="run-accepted",
                    review_state=WorkflowPackRunReviewState.ACCEPTED,
                    allowed_review_actions=[WorkflowPackRunReviewActionType.SUPERSEDE],
                ),
                _build_run(
                    run_id="run-rejected",
                    review_state=WorkflowPackRunReviewState.REJECTED,
                ),
                _build_run(
                    run_id="run-failed",
                    runtime_state=WorkflowPackRunRuntimeState.FAILED,
                ),
                _build_run(
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


def _build_run(
    *,
    run_id: str,
    runtime_state: WorkflowPackRunRuntimeState = WorkflowPackRunRuntimeState.COMPLETED,
    review_state: WorkflowPackRunReviewState = WorkflowPackRunReviewState.NOT_REVIEW_REQUIRED,
    allowed_review_actions: list[WorkflowPackRunReviewActionType] | None = None,
    superseded_by_run_id: str | None = None,
    created_at: str = "2026-04-19T10:00:00Z",
) -> WorkflowPackRunDescriptor:
    return WorkflowPackRunDescriptor(
        run_id=run_id,
        pack_id="advisor_brief.pack",
        pack_family="advisor_brief",
        pack_version="v1",
        registration_ref="advisor_brief.pack@v1",
        task_id="explain.v1",
        request_id=f"req-{run_id}",
        caller_app="lotus-gateway",
        correlation_id=f"corr-{run_id}",
        tenant_id=None,
        workflow_surface="advisor-brief-workspace",
        workflow_authority_owner="lotus-gateway",
        runtime_state=runtime_state,
        review_state=review_state,
        allowed_review_actions=allowed_review_actions or [],
        review_required=review_state is not WorkflowPackRunReviewState.NOT_REVIEW_REQUIRED,
        provider_mode="catalog_only",
        stubbed=True,
        output_preview="preview",
        structured_output_keys=["advisor_brief_status"],
        evidence_descriptors=[],
        artifact_refs=[],
        supersedes_run_id=None,
        superseded_by_run_id=superseded_by_run_id,
        created_at=created_at,
        completed_at=created_at,
        last_updated_at=created_at,
    )
