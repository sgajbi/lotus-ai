from _pytest.monkeypatch import MonkeyPatch

from app.contracts.evals import EvaluationApprovalEvidenceState
from app.contracts.resilience import (
    ResilienceActivationReadinessResponse,
    ResilienceDeliveryStage,
    ResilienceDrillEvidenceResponse,
    ResilienceDrillEvidenceState,
    ResiliencePosture,
    ResilienceRecoveryState,
    ResilienceRestorePlanResponse,
    ResilienceRunbookReadinessResponse,
    ResilienceRuntimeStatusResponse,
)
from app.services.resilience_activation_readiness import build_resilience_activation_readiness
from app.services.resilience_drill_evidence import build_resilience_drill_evidence
from app.services.resilience_governance import build_resilience_governance_status


def test_resilience_drill_evidence_is_not_ready_by_default() -> None:
    evidence = build_resilience_drill_evidence()

    assert evidence.drill_evidence_ready is False
    assert evidence.required_item_count == 5
    assert evidence.completed_required_item_count < evidence.required_item_count
    assert any(
        item.drill_id == "async_runtime_recovery_drill"
        and item.status is ResilienceDrillEvidenceState.FOUNDATION_STAGED
        for item in evidence.items
    )


def test_resilience_activation_and_governance_block_without_current_drill_evidence() -> None:
    activation = build_resilience_activation_readiness()
    governance = build_resilience_governance_status()

    assert activation.delivery_stage is ResilienceDeliveryStage.DRILL_VERIFIED
    assert activation.activation_ready is False
    assert any("drill" in finding.lower() for finding in activation.blocking_findings)
    assert governance.governance_ready is False
    assert governance.runbook_readiness.runbook_ready is True
    assert governance.drill_evidence.drill_evidence_ready is False
    assert governance.blocking_area_count >= 1


def test_resilience_governance_can_report_ready_when_all_inputs_are_ready(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.resilience_governance.build_resilience_runtime_status",
        lambda: ResilienceRuntimeStatusResponse(
            service="lotus-ai",
            version="test",
            delivery_stage=ResilienceDeliveryStage.DRILL_VERIFIED,
            recovery_state=ResilienceRecoveryState.STEADY,
            posture=ResiliencePosture.INVENTORIED_PROD_SHAPED,
            dependency_count=0,
            authoritative_dependency_count=0,
            restart_survivable_dependency_count=0,
            dependencies=[],
            recovery_attention_dependency_count=0,
            recovery_findings=[],
            blocking_findings=[],
            status_summary=["ready"],
        ),
    )
    monkeypatch.setattr(
        "app.services.resilience_governance.build_resilience_restore_plan",
        lambda: ResilienceRestorePlanResponse(
            service="lotus-ai",
            version="test",
            delivery_stage=ResilienceDeliveryStage.DRILL_VERIFIED,
            restore_step_count=4,
            restore_steps=[],
            restore_validation_summary=[],
            status_summary=[],
        ),
    )
    monkeypatch.setattr(
        "app.services.resilience_governance.build_resilience_drill_evidence",
        lambda: ResilienceDrillEvidenceResponse(
            service="lotus-ai",
            version="test",
            drill_evidence_ready=True,
            required_item_count=1,
            completed_required_item_count=1,
            items=[],
        ),
    )
    monkeypatch.setattr(
        "app.services.resilience_governance.build_resilience_activation_readiness",
        lambda: ResilienceActivationReadinessResponse(
            service="lotus-ai",
            version="test",
            delivery_stage=ResilienceDeliveryStage.DRILL_VERIFIED,
            recovery_state=ResilienceRecoveryState.STEADY,
            activation_ready=True,
            blocking_findings=[],
            activation_path=[],
        ),
    )
    monkeypatch.setattr(
        "app.services.resilience_governance.build_resilience_runbook_readiness",
        lambda: ResilienceRunbookReadinessResponse(
            service="lotus-ai",
            version="test",
            runbook_ready=True,
            required_item_count=1,
            completed_required_item_count=1,
            items=[],
        ),
    )

    governance = build_resilience_governance_status()

    assert governance.governance_ready is True
    assert governance.blocking_area_count == 0


def test_resilience_drill_evidence_marks_runtime_backed_provider_and_retrieval_as_ready(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.resilience_drill_evidence.build_provider_approval_gate_summary",
        lambda: type(
            "ProviderApprovalGate",
            (),
            {"evidence_state": EvaluationApprovalEvidenceState.RUNTIME_PASS},
        )(),
    )
    monkeypatch.setattr(
        "app.services.resilience_drill_evidence.build_retrieval_approval_gate_summary",
        lambda: type(
            "RetrievalApprovalGate",
            (),
            {"evidence_state": EvaluationApprovalEvidenceState.RUNTIME_PASS},
        )(),
    )

    evidence = build_resilience_drill_evidence()

    assert any(
        item.drill_id == "provider_recovery_drill"
        and item.status is ResilienceDrillEvidenceState.READY
        for item in evidence.items
    )
    assert any(
        item.drill_id == "retrieval_recovery_drill"
        and item.status is ResilienceDrillEvidenceState.READY
        for item in evidence.items
    )
