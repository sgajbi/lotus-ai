from __future__ import annotations

from app.config import settings
from app.contracts.capability_packs import (
    CapabilityPackDescriptor,
    CapabilityPackRunbookReadinessItem,
    CapabilityPackRunbookReadinessResponse,
)
from app.services.capability_pack_catalog import get_capability_pack_by_id
from app.services.first_use_case_runbook_readiness import build_first_use_case_runbook_readiness
from app.services.use_case_onboarding_template import build_use_case_onboarding_template


def build_capability_pack_runbook_readiness(
    *, pack_id: str
) -> CapabilityPackRunbookReadinessResponse:
    _require_pack(pack_id=pack_id)
    if pack_id == "analytics_commentary.pack.v1":
        first_use_case_runbook = build_first_use_case_runbook_readiness()
        template = build_use_case_onboarding_template()
        items = [
            CapabilityPackRunbookReadinessItem(
                item_id="shared_support_path",
                status="READY" if first_use_case_runbook.runbook_ready else "BLOCKED",
                required_for_activation=True,
                notes=(
                    "The analytics commentary pack currently reuses the bounded first-use-case support, rollback, and escalation path."
                ),
            ),
            CapabilityPackRunbookReadinessItem(
                item_id="reusable_onboarding_template",
                status="READY" if len(template.checklist) > 0 else "BLOCKED",
                required_for_activation=True,
                notes="The reusable downstream onboarding template captures pack-oriented checklist and approval criteria.",
            ),
            CapabilityPackRunbookReadinessItem(
                item_id="downstream_owner_documented",
                status="READY",
                required_for_activation=True,
                notes="The current downstream owner remains lotus-performance through the first production use case.",
            ),
        ]
    else:
        items = [
            CapabilityPackRunbookReadinessItem(
                item_id="shared_support_path",
                status="BLOCKED",
                required_for_activation=True,
                notes="The decision explanation pack does not yet have a concrete downstream support and rollback path.",
            ),
            CapabilityPackRunbookReadinessItem(
                item_id="reusable_onboarding_template",
                status="READY",
                required_for_activation=True,
                notes="The reusable onboarding template exists, but it is not yet anchored to a concrete decision-explanation integration.",
            ),
            CapabilityPackRunbookReadinessItem(
                item_id="downstream_owner_documented",
                status="BLOCKED",
                required_for_activation=True,
                notes="No concrete downstream owner or operator path has been documented for this pack yet.",
            ),
        ]
    required_items = [item for item in items if item.required_for_activation]
    completed_required_item_count = sum(1 for item in required_items if item.status == "READY")
    runbook_ready = completed_required_item_count == len(required_items)
    return CapabilityPackRunbookReadinessResponse(
        service=settings.service_name,
        version=settings.service_version,
        pack_id=pack_id,
        runbook_ready=runbook_ready,
        required_item_count=len(required_items),
        completed_required_item_count=completed_required_item_count,
        items=items,
        status_summary=[
            (
                "Capability-pack runbook posture is ready for the current bounded pack."
                if runbook_ready
                else "Capability-pack runbook posture is not yet ready for the current bounded pack."
            )
        ],
    )


def _require_pack(*, pack_id: str) -> CapabilityPackDescriptor:
    pack = get_capability_pack_by_id(pack_id)
    if pack is None:
        raise ValueError(f"Unknown capability pack: {pack_id}")
    return pack
