from types import SimpleNamespace

from _pytest.monkeypatch import MonkeyPatch

from app.contracts.deployment_split import (
    DeploymentPlaneId,
    DeploymentSplitActivationReadinessResponse,
    DeploymentSplitRunbookReadinessResponse,
    DeploymentSplitRuntimeStatusResponse,
    DeploymentSplitStage,
)
from app.services.deployment_split_activation_readiness import (
    build_deployment_split_activation_readiness,
)
from app.services.deployment_split_governance import (
    build_deployment_split_governance_status,
)
from app.services.deployment_split_runbook_readiness import (
    build_deployment_split_runbook_readiness,
)


def _runtime_status(
    *,
    configured_stage: DeploymentSplitStage,
    effective_stage: DeploymentSplitStage,
    blocking_findings: list[str],
    degraded: bool,
    degraded_findings: list[str],
) -> DeploymentSplitRuntimeStatusResponse:
    return DeploymentSplitRuntimeStatusResponse(
        service="lotus-ai",
        version="0.1.0",
        configured_stage=configured_stage,
        effective_stage=effective_stage,
        front_door_plane=DeploymentPlaneId.RUNTIME,
        split_ready=effective_stage is not DeploymentSplitStage.UNIFIED,
        plane_count=3,
        separate_plane_count=0,
        route_count=4,
        planes=[],
        routes=[],
        blocking_findings=blocking_findings,
        degraded=degraded,
        degraded_findings=degraded_findings,
        status_summary=["runtime summary"],
    )


def test_deployment_split_activation_readiness_reports_stage_mismatch_as_blocking(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.deployment_split_activation_readiness.build_deployment_split_runtime_status",
        lambda _app_state=None: _runtime_status(
            configured_stage=DeploymentSplitStage.RETRIEVAL_SPLIT_ACTIVE,
            effective_stage=DeploymentSplitStage.SPLIT_READY,
            blocking_findings=["RFC-0020 production-baseline governance is not yet ready."],
            degraded=False,
            degraded_findings=[],
        ),
    )

    readiness = build_deployment_split_activation_readiness(None)

    assert readiness.activation_ready is False
    assert readiness.split_active is False
    assert "RFC-0020 production-baseline governance is not yet ready." in readiness.blocking_findings


def test_deployment_split_runbook_readiness_is_ready() -> None:
    readiness = build_deployment_split_runbook_readiness()

    assert readiness.runbook_ready is True
    assert readiness.required_item_count == readiness.completed_required_item_count
    assert any(item.runbook_id == "cross_plane_incident_triage" for item in readiness.items)


def test_deployment_split_governance_status_blocks_when_observability_is_not_ready(
    monkeypatch: MonkeyPatch,
) -> None:
    runtime_status = _runtime_status(
        configured_stage=DeploymentSplitStage.RETRIEVAL_AND_EVALS_SPLIT_ACTIVE,
        effective_stage=DeploymentSplitStage.RETRIEVAL_AND_EVALS_SPLIT_ACTIVE,
        blocking_findings=[],
        degraded=False,
        degraded_findings=[],
    )
    monkeypatch.setattr(
        "app.services.deployment_split_governance.build_deployment_split_runtime_status",
        lambda _app_state=None: runtime_status,
    )
    monkeypatch.setattr(
        "app.services.deployment_split_governance.build_deployment_split_activation_readiness",
        lambda _app_state=None: DeploymentSplitActivationReadinessResponse(
            service="lotus-ai",
            version="0.1.0",
            configured_stage=DeploymentSplitStage.RETRIEVAL_AND_EVALS_SPLIT_ACTIVE,
            effective_stage=DeploymentSplitStage.RETRIEVAL_AND_EVALS_SPLIT_ACTIVE,
            split_ready=True,
            split_active=True,
            activation_ready=True,
            degraded=False,
            blocking_findings=[],
            activation_path=["review deployment split runtime"],
        ),
    )
    monkeypatch.setattr(
        "app.services.deployment_split_governance.build_deployment_split_runbook_readiness",
        lambda: DeploymentSplitRunbookReadinessResponse(
            service="lotus-ai",
            version="0.1.0",
            runbook_ready=True,
            required_item_count=1,
            completed_required_item_count=1,
            items=[],
        ),
    )
    monkeypatch.setattr(
        "app.services.deployment_split_governance.build_observability_governance_status",
        lambda: SimpleNamespace(governance_ready=False),
    )

    governance = build_deployment_split_governance_status(None)

    assert governance.governance_ready is False
    assert governance.observability_governance_ready is False
    assert governance.blocking_area_count == 1
