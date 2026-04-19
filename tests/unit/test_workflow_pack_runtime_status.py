from _pytest.monkeypatch import MonkeyPatch

from app.contracts.workflow_pack_runs import (
    WorkflowPackRunCatalogResponse,
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
        summary.executable_activity[0].latest_action_required_recorded_at
        == "2026-04-19T11:00:00Z"
    )
    assert summary.executable_activity[0].latest_ready_run_id == "run-accepted"
    assert summary.executable_activity[0].latest_ready_recorded_at == "2026-04-19T12:00:00Z"
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
