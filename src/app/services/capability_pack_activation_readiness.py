from __future__ import annotations

from app.config import settings
from app.contracts.capability_packs import (
    CapabilityPackActivationReadinessItem,
    CapabilityPackActivationReadinessResponse,
    CapabilityPackDescriptor,
)
from app.services.capability_pack_catalog import get_capability_pack_by_id
from app.services.capability_pack_observability import build_capability_pack_observability_summary
from app.services.capability_pack_quality_gates import build_capability_pack_approval_gate


def build_capability_pack_activation_readiness(
    *, pack_id: str
) -> CapabilityPackActivationReadinessResponse:
    pack = _require_pack(pack_id=pack_id)
    approval_gate = build_capability_pack_approval_gate(pack_id=pack_id)
    observability = build_capability_pack_observability_summary(pack_id=pack_id)
    items = [
        CapabilityPackActivationReadinessItem(
            item_id="runtime_quality_gate",
            status="READY" if approval_gate.approval_ready else "BLOCKED",
            required_for_activation=True,
            notes=(
                f"Pack quality gate currently reports '{approval_gate.evidence_state.value}' across the governed runtime-backed fixture families."
            ),
        ),
        CapabilityPackActivationReadinessItem(
            item_id="downstream_anchor",
            status="READY" if pack.current_anchor_use_case_id is not None else "BLOCKED",
            required_for_activation=True,
            notes=(
                f"Current downstream anchor is '{pack.current_anchor_use_case_id}'."
                if pack.current_anchor_use_case_id is not None
                else "The pack does not yet have an implemented downstream anchor use case."
            ),
        ),
        CapabilityPackActivationReadinessItem(
            item_id="observability_review_surface",
            status="READY" if observability.observability_ready else "BLOCKED",
            required_for_activation=True,
            notes=(
                "Bounded observability and support-review surfaces are available for this pack."
                if observability.observability_ready
                else "Bounded observability and support-review surfaces are not yet available for this pack."
            ),
        ),
    ]
    required_items = [item for item in items if item.required_for_activation]
    completed_required_item_count = sum(1 for item in required_items if item.status == "READY")
    activation_ready = completed_required_item_count == len(required_items)
    return CapabilityPackActivationReadinessResponse(
        service=settings.service_name,
        version=settings.service_version,
        pack_id=pack_id,
        activation_ready=activation_ready,
        required_item_count=len(required_items),
        completed_required_item_count=completed_required_item_count,
        items=items,
        status_summary=[
            (
                "Capability-pack activation is ready because runtime quality, downstream anchor, and observability review surfaces are all present."
                if activation_ready
                else "Capability-pack activation remains blocked until runtime quality, downstream anchor, and observability review surfaces are all present."
            )
        ],
    )


def _require_pack(*, pack_id: str) -> CapabilityPackDescriptor:
    pack = get_capability_pack_by_id(pack_id)
    if pack is None:
        raise ValueError(f"Unknown capability pack: {pack_id}")
    return pack
