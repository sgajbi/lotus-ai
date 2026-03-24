from __future__ import annotations

from app.config import settings
from app.contracts.deployment_split import (
    DeploymentPlaneId,
    DeploymentPlaneOwnershipDescriptor,
    DeploymentSplitRuntimeStatusResponse,
    DeploymentSplitStage,
)
from app.services.production_baseline_governance import (
    build_production_baseline_governance_status,
)


def build_deployment_split_runtime_status(
    app_state: object | None = None,
) -> DeploymentSplitRuntimeStatusResponse:
    configured_stage = _resolve_configured_stage()
    blocking_findings: list[str] = []

    if configured_stage is DeploymentSplitStage.UNIFIED:
        effective_stage = DeploymentSplitStage.UNIFIED
    elif configured_stage is DeploymentSplitStage.SPLIT_READY:
        effective_stage, blocking_findings = _resolve_split_ready_effective_stage(app_state)
    else:
        effective_stage = DeploymentSplitStage.UNIFIED
        blocking_findings = [
            "Retrieval and eval plane activation are not yet implemented in the current RFC-0015 slice."
        ]

    planes = _build_plane_descriptors(effective_stage)
    separate_plane_count = sum(1 for plane in planes if plane.separately_deployed)
    split_ready = effective_stage is not DeploymentSplitStage.UNIFIED

    status_summary = [
        (
            "Lotus-ai remains in the unified deployment stage."
            if effective_stage is DeploymentSplitStage.UNIFIED
            else "Lotus-ai is currently operating in a split-ready posture without live plane cutover."
        ),
        "The runtime plane remains the single external front door while retrieval and eval planes are modeled as internal deployment seams.",
        (
            "Configured split stage is blocked by production-baseline or rollout prerequisites."
            if configured_stage is not effective_stage
            else "Configured split stage currently matches the effective deployment-split posture."
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
        planes=planes,
        blocking_findings=blocking_findings,
        status_summary=status_summary,
    )


def _resolve_configured_stage() -> DeploymentSplitStage:
    configured = settings.deployment_split_stage.strip().lower()
    mapping = {
        "unified": DeploymentSplitStage.UNIFIED,
        "split_ready": DeploymentSplitStage.SPLIT_READY,
        "retrieval_split_active": DeploymentSplitStage.RETRIEVAL_SPLIT_ACTIVE,
        "retrieval_and_evals_split_active": DeploymentSplitStage.RETRIEVAL_AND_EVALS_SPLIT_ACTIVE,
    }
    return mapping.get(configured, DeploymentSplitStage.UNIFIED)


def _resolve_split_ready_effective_stage(
    app_state: object | None,
) -> tuple[DeploymentSplitStage, list[str]]:
    production_baseline_governance = build_production_baseline_governance_status(app_state)
    if production_baseline_governance.governance_ready:
        return DeploymentSplitStage.SPLIT_READY, []
    return DeploymentSplitStage.UNIFIED, [
        "RFC-0020 production-baseline governance is not yet ready, so the platform cannot be treated as split-ready.",
        *production_baseline_governance.governance_summary,
    ]


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
