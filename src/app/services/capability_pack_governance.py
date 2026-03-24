from __future__ import annotations

from app.config import settings
from app.contracts.capability_packs import (
    CapabilityPackCatalogGovernanceStatusResponse,
    CapabilityPackGovernanceStatusResponse,
    CapabilityPackGovernanceSummaryItem,
)
from app.services.capability_pack_activation_readiness import (
    build_capability_pack_activation_readiness,
)
from app.services.capability_pack_catalog import build_capability_pack_catalog
from app.services.capability_pack_observability import build_capability_pack_observability_summary
from app.services.capability_pack_quality_gates import build_capability_pack_approval_gate
from app.services.capability_pack_runbook_readiness import build_capability_pack_runbook_readiness
from app.services.governance_readiness import summarize_governance_flags


def build_capability_pack_governance_status(
    *, pack_id: str
) -> CapabilityPackGovernanceStatusResponse:
    activation_readiness = build_capability_pack_activation_readiness(pack_id=pack_id)
    runbook_readiness = build_capability_pack_runbook_readiness(pack_id=pack_id)
    observability = build_capability_pack_observability_summary(pack_id=pack_id)
    governance_ready, blocking_area_count = summarize_governance_flags(
        activation_readiness.activation_ready,
        runbook_readiness.runbook_ready,
        observability.observability_ready,
    )
    return CapabilityPackGovernanceStatusResponse(
        service=settings.service_name,
        version=settings.service_version,
        pack_id=pack_id,
        governance_ready=governance_ready,
        activation_readiness=activation_readiness,
        runbook_readiness=runbook_readiness,
        observability=observability,
        blocking_area_count=blocking_area_count,
        governance_summary=[
            (
                "Capability-pack governance is ready because activation, runbook, and observability surfaces are all currently ready."
                if governance_ready
                else "Capability-pack governance remains blocked until activation, runbook, and observability surfaces are all currently ready."
            ),
            (
                f"Runtime quality evidence currently reports '{build_capability_pack_approval_gate(pack_id=pack_id).evidence_state.value}'."
            ),
            (
                "Rollback and support expectations are anchored to the existing first-use-case path."
                if pack_id == "analytics_commentary.pack.v1"
                else "Rollback and support expectations remain blocked until a concrete downstream owner is documented."
            ),
        ],
    )


def build_capability_pack_catalog_governance_status() -> (
    CapabilityPackCatalogGovernanceStatusResponse
):
    catalog = build_capability_pack_catalog()
    pack_statuses = [
        build_capability_pack_governance_status(pack_id=pack.pack_id) for pack in catalog.packs
    ]
    ready_pack_count = sum(1 for status in pack_statuses if status.governance_ready)
    blocking_pack_count = len(pack_statuses) - ready_pack_count
    return CapabilityPackCatalogGovernanceStatusResponse(
        service=settings.service_name,
        version=settings.service_version,
        governance_ready=blocking_pack_count == 0,
        ready_pack_count=ready_pack_count,
        blocking_pack_count=blocking_pack_count,
        pack_summaries=[
            CapabilityPackGovernanceSummaryItem(
                pack_id=status.pack_id,
                governance_ready=status.governance_ready,
                blocking_area_count=status.blocking_area_count,
                quality_evidence_state=build_capability_pack_approval_gate(
                    pack_id=status.pack_id
                ).evidence_state,
            )
            for status in pack_statuses
        ],
        status_summary=[
            "Capability-pack governance now composes activation, runbook, and observability posture per pack instead of leaving product readiness implicit.",
            (
                "All currently modeled capability packs satisfy bounded governance posture."
                if blocking_pack_count == 0
                else f"{blocking_pack_count} currently modeled capability pack(s) remain blocked in governance review."
            ),
        ],
    )
