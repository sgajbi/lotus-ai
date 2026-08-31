from __future__ import annotations

from app.config import settings
from app.contracts.artifacts import ArtifactGovernanceStatusResponse
from app.services.artifact_activation_readiness import build_artifact_activation_readiness
from app.services.readiness_catalog import build_artifact_runbook_readiness
from app.services.artifact_runtime import build_artifact_runtime_status


def build_artifact_governance_status() -> ArtifactGovernanceStatusResponse:
    runtime_status = build_artifact_runtime_status()
    activation_readiness = build_artifact_activation_readiness()
    runbook_readiness = build_artifact_runbook_readiness()
    governance_summary = [
        runtime_status.status_summary[0],
        (
            activation_readiness.blocking_findings[0]
            if activation_readiness.blocking_findings
            else "Artifact activation currently has no technical blocker."
        ),
        (
            "Managed object-storage approval for production go-live remains blocked until artifact payload storage moves off local fallback backends."
            if settings.artifact_object_store_mode in {"memory", "filesystem"}
            else "Managed object-storage posture is aligned with production go-live expectations."
        ),
        (
            "Artifact runbook posture is complete."
            if runbook_readiness.runbook_ready
            else "Artifact runbook posture still has incomplete required items."
        ),
    ]
    blocking_area_count = int(bool(activation_readiness.blocking_findings)) + int(
        not runbook_readiness.runbook_ready
    )
    return ArtifactGovernanceStatusResponse(
        service=settings.service_name,
        version=settings.service_version,
        governance_ready=activation_readiness.activation_ready and runbook_readiness.runbook_ready,
        runtime_status=runtime_status,
        activation_readiness=activation_readiness,
        runbook_readiness=runbook_readiness,
        blocking_area_count=blocking_area_count,
        governance_summary=governance_summary,
    )
