from __future__ import annotations

from app.config import settings
from app.contracts.artifacts import (
    ArtifactRunbookReadinessItem,
    ArtifactRunbookReadinessResponse,
)


def build_artifact_runbook_readiness() -> ArtifactRunbookReadinessResponse:
    items = [
        ArtifactRunbookReadinessItem(
            runbook_id="artifact_retention_review",
            status="READY",
            required_for_activation=True,
            notes="Retention, archival posture, and descriptor-first artifact inspection are documented in the operator runbook.",
        ),
        ArtifactRunbookReadinessItem(
            runbook_id="artifact_incident_bundle_review",
            status="READY",
            required_for_activation=True,
            notes="Observability incident-bundle review now points to governed artifact refs instead of raw payload dumping.",
        ),
        ArtifactRunbookReadinessItem(
            runbook_id="artifact_archive_recovery",
            status="READY",
            required_for_activation=True,
            notes="Archive posture and recovery expectations are documented as reviewable metadata transitions rather than hidden filesystem cleanup.",
        ),
    ]
    return ArtifactRunbookReadinessResponse(
        service=settings.service_name,
        version=settings.service_version,
        runbook_ready=True,
        required_item_count=len(items),
        completed_required_item_count=len(items),
        items=items,
    )
