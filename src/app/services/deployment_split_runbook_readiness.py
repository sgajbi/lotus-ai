from __future__ import annotations

from app.config import settings
from app.contracts.deployment_split import (
    DeploymentSplitRunbookReadinessItem,
    DeploymentSplitRunbookReadinessResponse,
)
from app.services.governance_readiness import summarize_activation_items


def build_deployment_split_runbook_readiness() -> DeploymentSplitRunbookReadinessResponse:
    items = [
        DeploymentSplitRunbookReadinessItem(
            runbook_id="split_stage_boundary",
            status="READY",
            required_for_activation=True,
            notes="Operator guidance now distinguishes unified, split-ready, retrieval-split active, and retrieval-and-evals-split active posture explicitly.",
        ),
        DeploymentSplitRunbookReadinessItem(
            runbook_id="unified_front_door_invariant",
            status="READY",
            required_for_activation=True,
            notes="The runtime plane remains the single external front door even when retrieval and eval planes activate internally.",
        ),
        DeploymentSplitRunbookReadinessItem(
            runbook_id="cross_plane_incident_triage",
            status="READY",
            required_for_activation=True,
            notes="Runbooks now direct operators to review deployment-split, observability, retrieval, and eval surfaces together during split-plane incidents.",
        ),
        DeploymentSplitRunbookReadinessItem(
            runbook_id="retrieval_plane_rollback",
            status="READY",
            required_for_activation=True,
            notes="Rollback guidance now explains when retrieval split degradation should trigger rollback to UNIFIED instead of hidden in-process fallback.",
        ),
        DeploymentSplitRunbookReadinessItem(
            runbook_id="eval_plane_rollback",
            status="READY",
            required_for_activation=True,
            notes="Rollback guidance now explains when eval split degradation should trigger rollback to UNIFIED instead of treating approval evidence drift as normal.",
        ),
        DeploymentSplitRunbookReadinessItem(
            runbook_id="cross_plane_observability_review",
            status="READY",
            required_for_activation=True,
            notes="Operator guidance now ties split-plane rollout review to observability runtime, incident-summary, and bounded artifact-backed evidence inspection.",
        ),
    ]
    required_item_count, completed_required_item_count = summarize_activation_items(items)
    return DeploymentSplitRunbookReadinessResponse(
        service=settings.service_name,
        version=settings.service_version,
        runbook_ready=required_item_count == completed_required_item_count,
        required_item_count=required_item_count,
        completed_required_item_count=completed_required_item_count,
        items=items,
    )
