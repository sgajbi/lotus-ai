from __future__ import annotations

import json
from datetime import UTC, datetime

from app.contracts.artifacts import ArtifactDescriptor
from app.contracts.observability import DomainIncidentSummaryResponse
from app.services.artifact_payloads import persist_or_reuse_json_artifact


def persist_observability_incident_bundle(
    *, summary: DomainIncidentSummaryResponse
) -> ArtifactDescriptor:
    payload = json.dumps(
        {
            "domain_id": summary.domain_id.value,
            "telemetry": summary.telemetry.model_dump(mode="json"),
            "incident_evidence_items": [
                item.model_dump(mode="json", exclude={"artifact_refs"})
                for item in summary.incident_evidence_items
            ],
            "linked_endpoints": summary.linked_endpoints,
            "summary": summary.summary,
        },
        sort_keys=True,
    ).encode("utf-8")
    return persist_or_reuse_json_artifact(
        domain="observability",
        artifact_type="incident_bundle",
        source_object_kind="observability_domain_summary",
        source_object_id=summary.domain_id.value,
        created_at=_utcnow(),
        created_by="observability_runtime",
        payload_json=payload,
        retention_posture="retained_for_review",
    )


def _utcnow() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
