from _pytest.monkeypatch import MonkeyPatch

from app.contracts.artifacts import ArtifactObjectStoreRuntimeStatusDescriptor
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
from app.contracts.runtime_readiness import RuntimeReadinessStatus
from app.services.resilience_activation_readiness import build_resilience_activation_readiness
from app.services.resilience_drill_evidence import (
    _build_artifact_restore_review_item,
    _build_async_recovery_drill_item,
    _build_store_restore_validation_item,
    build_resilience_drill_evidence,
)
from app.services.resilience_governance import build_resilience_governance_status
from app.services.resilience_runtime import (
    _classify_artifact_object_dependency,
    _classify_retrieval_dependency,
    _resolve_recovery_state,
    _resolve_resilience_posture,
)


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
    assert governance.runbook_readiness.runbook_ready is False
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


def test_resilience_drill_evidence_marks_provider_and_retrieval_as_foundation_staged_when_only_staged(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.resilience_drill_evidence.build_provider_approval_gate_summary",
        lambda: type(
            "ProviderApprovalGate",
            (),
            {"evidence_state": EvaluationApprovalEvidenceState.STAGED_ONLY},
        )(),
    )
    monkeypatch.setattr(
        "app.services.resilience_drill_evidence.build_retrieval_approval_gate_summary",
        lambda: type(
            "RetrievalApprovalGate",
            (),
            {"evidence_state": EvaluationApprovalEvidenceState.NO_EVIDENCE},
        )(),
    )

    evidence = build_resilience_drill_evidence()

    assert any(
        item.drill_id == "provider_recovery_drill"
        and item.status is ResilienceDrillEvidenceState.FOUNDATION_STAGED
        for item in evidence.items
    )
    assert any(
        item.drill_id == "retrieval_recovery_drill"
        and item.status is ResilienceDrillEvidenceState.FOUNDATION_STAGED
        for item in evidence.items
    )


def test_resilience_drill_evidence_classifies_not_ready_partial_and_ready_paths() -> None:
    runtime_status = ResilienceRuntimeStatusResponse(
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
    )
    no_restore_plan = ResilienceRestorePlanResponse(
        service="lotus-ai",
        version="test",
        delivery_stage=ResilienceDeliveryStage.DRILL_VERIFIED,
        restore_step_count=0,
        restore_steps=[],
        restore_validation_summary=[],
        status_summary=[],
    )

    assert (
        _build_store_restore_validation_item(runtime_status, no_restore_plan).status
        is ResilienceDrillEvidenceState.NOT_READY
    )
    assert (
        _build_async_recovery_drill_item(
            type(
                "AsyncRuntime",
                (),
                {
                    "queue_backend": "redis_queue",
                    "worker_mode": "DEDICATED",
                    "degraded_findings": ["queue lag exceeds threshold"],
                },
            )()
        ).status
        is ResilienceDrillEvidenceState.PARTIAL
    )
    assert (
        _build_artifact_restore_review_item(
            type(
                "ArtifactRuntime",
                (),
                {
                    "metadata_store": type(
                        "MetadataStore",
                        (),
                        {"status": RuntimeReadinessStatus.READY},
                    )(),
                    "object_store": ArtifactObjectStoreRuntimeStatusDescriptor(
                        mode="s3",
                        status=RuntimeReadinessStatus.READY,
                        root_configured=True,
                        durable=True,
                        detail="ready",
                    ),
                    "object_store_mode": "s3",
                },
            )()
        ).status
        is ResilienceDrillEvidenceState.READY
    )
    assert (
        _build_artifact_restore_review_item(
            type(
                "ArtifactRuntime",
                (),
                {
                    "metadata_store": type(
                        "MetadataStore",
                        (),
                        {"status": RuntimeReadinessStatus.UNAVAILABLE},
                    )(),
                    "object_store": ArtifactObjectStoreRuntimeStatusDescriptor(
                        mode="filesystem",
                        status=RuntimeReadinessStatus.UNAVAILABLE,
                        root_configured=False,
                        durable=False,
                        detail="missing root",
                    ),
                    "object_store_mode": "filesystem",
                },
            )()
        ).status
        is ResilienceDrillEvidenceState.NOT_READY
    )


def test_resilience_runtime_classifiers_cover_steady_and_blocked_edges() -> None:
    blocked_artifact = _classify_artifact_object_dependency(
        mode="filesystem",
        root_configured=False,
        object_store_status=RuntimeReadinessStatus.CONFIGURATION_REQUIRED,
    )
    unknown_artifact = _classify_artifact_object_dependency(
        mode="s3",
        root_configured=False,
        object_store_status=RuntimeReadinessStatus.UNAVAILABLE,
    )
    retrieval = _classify_retrieval_dependency(
        retrieval_mode="enabled",
        execution_stage="INDEXING_DISABLED",
        split_route_degraded=False,
        findings=[],
        message="Retrieval indexing is disabled.",
    )

    assert blocked_artifact.recovery_state is ResilienceRecoveryState.DEGRADED
    assert unknown_artifact.recovery_classification is not None
    assert unknown_artifact.recovery_classification.name == "BLOCKED"
    assert retrieval.recovery_findings == ["Retrieval indexing is disabled."]
    assert (
        _resolve_resilience_posture([unknown_artifact])
        is ResiliencePosture.PARTIAL_RUNTIME_DURABILITY
    )
    assert _resolve_recovery_state([]) is ResilienceRecoveryState.STEADY
