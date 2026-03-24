from __future__ import annotations

from app.contracts.deployment_split import (
    DeploymentPlaneId,
    DeploymentRouteDescriptor,
    DeploymentRouteMode,
    DeploymentSplitStage,
)
from app.services.deployment_split_shared import resolve_deployment_split_posture


def build_split_route_descriptors(
    app_state: object | None = None,
) -> list[DeploymentRouteDescriptor]:
    posture = resolve_deployment_split_posture(app_state)
    return [
        resolve_retrieval_search_route(
            effective_stage=posture.effective_stage,
            degraded_findings=posture.retrieval_degraded_findings,
        ),
        resolve_retrieval_async_route(
            effective_stage=posture.effective_stage,
            degraded_findings=posture.retrieval_degraded_findings,
        ),
        resolve_evaluation_submission_route(
            effective_stage=posture.effective_stage,
            degraded_findings=posture.eval_degraded_findings,
        ),
        resolve_evaluation_async_route(
            effective_stage=posture.effective_stage,
            degraded_findings=posture.eval_degraded_findings,
        ),
    ]


def resolve_retrieval_search_route(
    *, effective_stage: DeploymentSplitStage, degraded_findings: list[str] | None = None
) -> DeploymentRouteDescriptor:
    return _resolve_route(
        route_id="retrieval_search_execution",
        split_plane=DeploymentPlaneId.RETRIEVAL,
        effective_stage=effective_stage,
        active_stages={
            DeploymentSplitStage.RETRIEVAL_SPLIT_ACTIVE,
            DeploymentSplitStage.RETRIEVAL_AND_EVALS_SPLIT_ACTIVE,
        },
        degraded_findings=degraded_findings or [],
        split_ready_detail=(
            "Retrieval search now resolves through a split-aware routing seam, but the effective execution path remains unified until retrieval plane activation is implemented."
        ),
        unified_detail=(
            "Retrieval search currently executes through the unified lotus-ai deployment."
        ),
    )


def resolve_retrieval_async_route(
    *, effective_stage: DeploymentSplitStage, degraded_findings: list[str] | None = None
) -> DeploymentRouteDescriptor:
    return _resolve_route(
        route_id="retrieval_async_execution",
        split_plane=DeploymentPlaneId.RETRIEVAL,
        effective_stage=effective_stage,
        active_stages={
            DeploymentSplitStage.RETRIEVAL_SPLIT_ACTIVE,
            DeploymentSplitStage.RETRIEVAL_AND_EVALS_SPLIT_ACTIVE,
        },
        degraded_findings=degraded_findings or [],
        split_ready_detail=(
            "Retrieval async execution now resolves through a split-aware routing seam, but retrieval jobs still execute under the unified deployment until retrieval plane activation is implemented."
        ),
        unified_detail=(
            "Retrieval async execution currently resolves through the unified lotus-ai deployment."
        ),
    )


def resolve_evaluation_submission_route(
    *, effective_stage: DeploymentSplitStage, degraded_findings: list[str] | None = None
) -> DeploymentRouteDescriptor:
    return _resolve_route(
        route_id="evaluation_run_submission",
        split_plane=DeploymentPlaneId.EVALS,
        effective_stage=effective_stage,
        active_stages={DeploymentSplitStage.RETRIEVAL_AND_EVALS_SPLIT_ACTIVE},
        degraded_findings=degraded_findings or [],
        split_ready_detail=(
            "Evaluation submission now resolves through a split-aware routing seam, but accepted runs still enter the unified deployment until eval plane activation is implemented."
        ),
        unified_detail=(
            "Evaluation submission currently resolves through the unified lotus-ai deployment."
        ),
    )


def resolve_evaluation_async_route(
    *, effective_stage: DeploymentSplitStage, degraded_findings: list[str] | None = None
) -> DeploymentRouteDescriptor:
    return _resolve_route(
        route_id="evaluation_async_execution",
        split_plane=DeploymentPlaneId.EVALS,
        effective_stage=effective_stage,
        active_stages={DeploymentSplitStage.RETRIEVAL_AND_EVALS_SPLIT_ACTIVE},
        degraded_findings=degraded_findings or [],
        split_ready_detail=(
            "Evaluation async execution now resolves through a split-aware routing seam, but worker-backed execution remains unified until eval plane activation is implemented."
        ),
        unified_detail=(
            "Evaluation async execution currently resolves through the unified lotus-ai deployment."
        ),
    )


def _resolve_route(
    *,
    route_id: str,
    split_plane: DeploymentPlaneId,
    effective_stage: DeploymentSplitStage,
    active_stages: set[DeploymentSplitStage],
    degraded_findings: list[str],
    split_ready_detail: str,
    unified_detail: str,
) -> DeploymentRouteDescriptor:
    split_ready_active = effective_stage in {
        DeploymentSplitStage.SPLIT_READY,
        DeploymentSplitStage.RETRIEVAL_SPLIT_ACTIVE,
        DeploymentSplitStage.RETRIEVAL_AND_EVALS_SPLIT_ACTIVE,
    }
    if effective_stage in active_stages:
        degraded = len(degraded_findings) > 0
        return DeploymentRouteDescriptor(
            route_id=route_id,
            owning_plane=split_plane,
            route_mode=DeploymentRouteMode.PLANE_SPLIT_ACTIVE,
            rollback_target_stage=DeploymentSplitStage.UNIFIED,
            degraded=degraded,
            degraded_findings=degraded_findings,
            detail=(
                f"{split_plane.value.capitalize()} plane routing is active for this flow, but the plane is currently degraded; operators should roll back to the unified stage if the degraded posture persists."
                if degraded
                else f"{split_plane.value.capitalize()} plane routing is active for this flow; operators should roll back to the unified stage if split-plane execution degrades."
            ),
        )
    if split_ready_active:
        return DeploymentRouteDescriptor(
            route_id=route_id,
            owning_plane=DeploymentPlaneId.RUNTIME,
            route_mode=DeploymentRouteMode.SPLIT_READY_UNIFIED,
            rollback_target_stage=DeploymentSplitStage.UNIFIED,
            degraded=False,
            degraded_findings=[],
            detail=split_ready_detail,
        )
    return DeploymentRouteDescriptor(
        route_id=route_id,
        owning_plane=DeploymentPlaneId.RUNTIME,
        route_mode=DeploymentRouteMode.UNIFIED_INTERNAL,
        rollback_target_stage=DeploymentSplitStage.UNIFIED,
        degraded=False,
        degraded_findings=[],
        detail=unified_detail,
    )
