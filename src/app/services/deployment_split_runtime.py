from __future__ import annotations

from app.config import settings
from app.contracts.deployment_split import (
    DeploymentPlaneId,
    DeploymentPlaneOwnershipDescriptor,
    DeploymentSplitRuntimeStatusResponse,
    DeploymentSplitStage,
)
from app.services.deployment_split_routing import build_split_route_descriptors
from app.services.deployment_split_shared import (
    resolve_deployment_split_posture,
)


def build_deployment_split_runtime_status(
    app_state: object | None = None,
) -> DeploymentSplitRuntimeStatusResponse:
    posture = resolve_deployment_split_posture(app_state)
    configured_stage = posture.configured_stage
    effective_stage = posture.effective_stage
    planes = _build_plane_descriptors(effective_stage)
    routes = build_split_route_descriptors(app_state)
    separate_plane_count = sum(1 for plane in planes if plane.separately_deployed)
    split_ready = effective_stage is not DeploymentSplitStage.UNIFIED

    status_summary = [
        (
            "Lotus-ai remains in the unified deployment stage."
            if effective_stage is DeploymentSplitStage.UNIFIED
            else (
                "Lotus-ai is currently operating in an active retrieval-and-evals split posture."
                if effective_stage is DeploymentSplitStage.RETRIEVAL_AND_EVALS_SPLIT_ACTIVE
                else (
                    "Lotus-ai is currently operating in an active retrieval-split posture."
                    if effective_stage is DeploymentSplitStage.RETRIEVAL_SPLIT_ACTIVE
                    else "Lotus-ai is currently operating in a split-ready posture without live plane cutover."
                )
            )
        ),
        "The runtime plane remains the single external front door while retrieval and eval planes are modeled as internal deployment seams.",
        (
            "Configured split stage is blocked by production-baseline or rollout prerequisites."
            if configured_stage is not effective_stage
            else (
                "Configured split stage currently matches the effective deployment-split posture, but one or more split planes are degraded."
                if posture.retrieval_degraded_findings or posture.eval_degraded_findings
                else "Configured split stage currently matches the effective deployment-split posture."
            )
        ),
        (
            "Operators should roll back to UNIFIED if degraded retrieval or eval split posture persists."
            if posture.retrieval_degraded_findings or posture.eval_degraded_findings
            else "Rollback to UNIFIED remains the first supported rollback target for all active split stages."
        ),
    ]

    return DeploymentSplitRuntimeStatusResponse(
        service=settings.service_name,
        version=settings.service_version,
        configured_stage=configured_stage,
        effective_stage=effective_stage,
        front_door_plane=DeploymentPlaneId.RUNTIME,
        split_ready=split_ready,
        plane_count=len(planes),
        separate_plane_count=separate_plane_count,
        route_count=len(routes),
        planes=planes,
        routes=routes,
        blocking_findings=posture.blocking_findings,
        degraded=bool(
            posture.retrieval_degraded_findings or posture.eval_degraded_findings
        ),
        degraded_findings=[
            *posture.retrieval_degraded_findings,
            *posture.eval_degraded_findings,
        ],
        status_summary=status_summary,
    )


def _build_plane_descriptors(
    effective_stage: DeploymentSplitStage,
) -> list[DeploymentPlaneOwnershipDescriptor]:
    return [
        DeploymentPlaneOwnershipDescriptor(
            plane_id=DeploymentPlaneId.RUNTIME,
            externally_addressable=True,
            separately_deployed=False,
            split_ready=True,
            owned_domains=[
                "external_contracts",
                "task_execution_orchestration",
                "provider_orchestration",
                "prompt_governance",
                "safety_enforcement",
                "authorization_controls",
                "top_level_platform_status",
            ],
            shared_responsibilities=[
                "audit_semantics",
                "artifact_lineage",
                "cross_plane_observability",
            ],
        ),
        DeploymentPlaneOwnershipDescriptor(
            plane_id=DeploymentPlaneId.RETRIEVAL,
            externally_addressable=False,
            separately_deployed=effective_stage
            in {
                DeploymentSplitStage.RETRIEVAL_SPLIT_ACTIVE,
                DeploymentSplitStage.RETRIEVAL_AND_EVALS_SPLIT_ACTIVE,
            },
            split_ready=effective_stage is not DeploymentSplitStage.UNIFIED,
            owned_domains=[
                "retrieval_search_execution",
                "retrieval_indexing",
                "retrieval_corpus_governance",
                "retrieval_async_work",
            ],
            shared_responsibilities=[
                "audit_semantics",
                "authorization_semantics",
                "artifact_lineage",
                "cross_plane_observability",
            ],
        ),
        DeploymentPlaneOwnershipDescriptor(
            plane_id=DeploymentPlaneId.EVALS,
            externally_addressable=False,
            separately_deployed=effective_stage
            is DeploymentSplitStage.RETRIEVAL_AND_EVALS_SPLIT_ACTIVE,
            split_ready=effective_stage is not DeploymentSplitStage.UNIFIED,
            owned_domains=[
                "evaluation_execution",
                "approval_evidence_generation",
                "evaluation_artifact_flows",
                "evaluation_runtime_status",
            ],
            shared_responsibilities=[
                "audit_semantics",
                "authorization_semantics",
                "artifact_lineage",
                "cross_plane_observability",
            ],
        ),
    ]
