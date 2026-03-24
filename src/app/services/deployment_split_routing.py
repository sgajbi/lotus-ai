from __future__ import annotations

from app.contracts.deployment_split import (
    DeploymentPlaneId,
    DeploymentRouteDescriptor,
    DeploymentRouteMode,
    DeploymentSplitStage,
)
from app.services.deployment_split_shared import resolve_effective_deployment_split_stage


def build_split_route_descriptors(
    app_state: object | None = None,
) -> list[DeploymentRouteDescriptor]:
    effective_stage, _ = resolve_effective_deployment_split_stage(app_state)
    return [
        resolve_retrieval_search_route(effective_stage=effective_stage),
        resolve_retrieval_async_route(effective_stage=effective_stage),
        resolve_evaluation_submission_route(effective_stage=effective_stage),
        resolve_evaluation_async_route(effective_stage=effective_stage),
    ]


def resolve_retrieval_search_route(
    *, effective_stage: DeploymentSplitStage
) -> DeploymentRouteDescriptor:
    return _resolve_route(
        route_id="retrieval_search_execution",
        split_plane=DeploymentPlaneId.RETRIEVAL,
        effective_stage=effective_stage,
        active_stage=DeploymentSplitStage.RETRIEVAL_SPLIT_ACTIVE,
        split_ready_detail=(
            "Retrieval search now resolves through a split-aware routing seam, but the effective execution path remains unified until retrieval plane activation is implemented."
        ),
        unified_detail=(
            "Retrieval search currently executes through the unified lotus-ai deployment."
        ),
    )


def resolve_retrieval_async_route(
    *, effective_stage: DeploymentSplitStage
) -> DeploymentRouteDescriptor:
    return _resolve_route(
        route_id="retrieval_async_execution",
        split_plane=DeploymentPlaneId.RETRIEVAL,
        effective_stage=effective_stage,
        active_stage=DeploymentSplitStage.RETRIEVAL_SPLIT_ACTIVE,
        split_ready_detail=(
            "Retrieval async execution now resolves through a split-aware routing seam, but retrieval jobs still execute under the unified deployment until retrieval plane activation is implemented."
        ),
        unified_detail=(
            "Retrieval async execution currently resolves through the unified lotus-ai deployment."
        ),
    )


def resolve_evaluation_submission_route(
    *, effective_stage: DeploymentSplitStage
) -> DeploymentRouteDescriptor:
    return _resolve_route(
        route_id="evaluation_run_submission",
        split_plane=DeploymentPlaneId.EVALS,
        effective_stage=effective_stage,
        active_stage=DeploymentSplitStage.RETRIEVAL_AND_EVALS_SPLIT_ACTIVE,
        split_ready_detail=(
            "Evaluation submission now resolves through a split-aware routing seam, but accepted runs still enter the unified deployment until eval plane activation is implemented."
        ),
        unified_detail=(
            "Evaluation submission currently resolves through the unified lotus-ai deployment."
        ),
    )


def resolve_evaluation_async_route(
    *, effective_stage: DeploymentSplitStage
) -> DeploymentRouteDescriptor:
    return _resolve_route(
        route_id="evaluation_async_execution",
        split_plane=DeploymentPlaneId.EVALS,
        effective_stage=effective_stage,
        active_stage=DeploymentSplitStage.RETRIEVAL_AND_EVALS_SPLIT_ACTIVE,
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
    active_stage: DeploymentSplitStage,
    split_ready_detail: str,
    unified_detail: str,
) -> DeploymentRouteDescriptor:
    if effective_stage is active_stage:
        return DeploymentRouteDescriptor(
            route_id=route_id,
            owning_plane=split_plane,
            route_mode=DeploymentRouteMode.PLANE_SPLIT_ACTIVE,
            rollback_target_stage=DeploymentSplitStage.UNIFIED,
            detail=(
                f"{split_plane.value.capitalize()} plane routing is active for this flow; operators should roll back to the unified stage if split-plane execution degrades."
            ),
        )
    if effective_stage is DeploymentSplitStage.SPLIT_READY:
        return DeploymentRouteDescriptor(
            route_id=route_id,
            owning_plane=DeploymentPlaneId.RUNTIME,
            route_mode=DeploymentRouteMode.SPLIT_READY_UNIFIED,
            rollback_target_stage=DeploymentSplitStage.UNIFIED,
            detail=split_ready_detail,
        )
    return DeploymentRouteDescriptor(
        route_id=route_id,
        owning_plane=DeploymentPlaneId.RUNTIME,
        route_mode=DeploymentRouteMode.UNIFIED_INTERNAL,
        rollback_target_stage=DeploymentSplitStage.UNIFIED,
        detail=unified_detail,
    )
