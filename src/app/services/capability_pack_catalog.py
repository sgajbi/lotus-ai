from __future__ import annotations

from app.config import settings
from app.contracts.capability_packs import (
    CapabilityPackCatalogResponse,
    CapabilityPackDescriptor,
    CapabilityPackDetailResponse,
    CapabilityPackFamilyKind,
    CapabilityPackMaturityStage,
    CapabilityPackQualityExpectation,
    CapabilityPackUnsupportedInputBehavior,
)
from app.contracts.tasks import OutputLabel
from app.services.capability_pack_quality_gates import build_capability_pack_approval_gate


def build_capability_pack_catalog() -> CapabilityPackCatalogResponse:
    packs = _build_capability_packs()
    reusable_pack_count = sum(1 for pack in packs if pack.reusable_across_apps)
    approved_pack_count = sum(
        1 for pack in packs if pack.maturity_stage == CapabilityPackMaturityStage.APPROVED
    )
    return CapabilityPackCatalogResponse(
        service=settings.service_name,
        version=settings.service_version,
        phase=settings.delivery_phase,
        pack_count=len(packs),
        reusable_pack_count=reusable_pack_count,
        approved_pack_count=approved_pack_count,
        packs=packs,
        status_summary=[
            "Capability packs are now modeled as a separate app-facing product layer above the generic task catalog.",
            "The initial Slice 2 family now includes both commentary and explanation-oriented packs built on the existing explain.v1 runtime backbone.",
            "Slice 3 quality gates now reuse the governed evaluation runtime so pack quality evidence follows the same runtime-backed approval semantics as other rollout domains.",
            "Reusable and approved pack counts remain separate so downstream teams can distinguish broader product capability shape from currently rollout-ready runtime evidence.",
        ],
    )


def build_capability_pack_detail(pack_id: str) -> CapabilityPackDetailResponse:
    pack = get_capability_pack_by_id(pack_id)
    if pack is None:
        raise ValueError(f"Unknown capability pack: {pack_id}")

    return CapabilityPackDetailResponse(
        service=settings.service_name,
        version=settings.service_version,
        pack=pack,
        quality_expectations=_build_quality_expectations(pack_id=pack_id),
        unsupported_input_behaviors=_build_unsupported_input_behaviors(pack_id=pack_id),
        approval_gate=build_capability_pack_approval_gate(pack_id=pack_id),
        non_goals=_build_non_goals(pack_id=pack_id),
        status_summary=_build_detail_status_summary(pack_id=pack_id),
    )


def get_capability_pack_by_id(pack_id: str) -> CapabilityPackDescriptor | None:
    for pack in _build_capability_packs():
        if pack.pack_id == pack_id:
            return pack
    return None


def _build_capability_packs() -> list[CapabilityPackDescriptor]:
    return [
        _build_pack_descriptor(
            pack_id="analytics_commentary.pack.v1",
            family_id="analytics_commentary",
            family_kind=CapabilityPackFamilyKind.COMMENTARY,
            maturity_stage=CapabilityPackMaturityStage.REUSABLE,
            primary_task_id="explain.v1",
            output_label=OutputLabel.EXPLANATION_ONLY,
            current_anchor_use_case_id="lotus_performance.analytics_commentary.v1",
            reusable_across_apps=True,
            intended_downstream_patterns=[
                "Performance and attribution commentary over caller-supplied structured analytics facts.",
                "Risk or support commentary over precomputed structured deltas where the downstream app remains the owner of computed truth.",
            ],
            governance_surface_ids=[
                "/platform/capability-packs",
                "/platform/capability-packs/analytics_commentary.pack.v1",
                "/platform/capability-packs/analytics_commentary.pack.v1/adoption-template",
                "/platform/capability-packs/analytics_commentary.pack.v1/activation-readiness",
                "/platform/capability-packs/analytics_commentary.pack.v1/runbook-readiness",
                "/platform/capability-packs/analytics_commentary.pack.v1/observability-summary",
                "/platform/capability-packs/analytics_commentary.pack.v1/governance-status",
                "/platform/evals/runtime-status",
                "/platform/use-cases/first-production-use-case",
                "/platform/use-cases/first-production-use-case/readiness",
                "/platform/use-cases/first-production-use-case/governance-status",
            ],
            status_summary=[
                "The first commentary pack is anchored to the implemented lotus-performance analytics commentary path.",
                "The pack is now modeled as reusable because downstream onboarding, pack-native adoption templates, and a broader commentary-family contract now exist above the one-off use-case seam.",
                "This pack catalog is intentionally distinct from the generic task catalog so product-facing capability shape does not get conflated with raw task primitives.",
            ],
        ),
        _build_pack_descriptor(
            pack_id="decision_explanation.pack.v1",
            family_id="decision_explanation",
            family_kind=CapabilityPackFamilyKind.EXPLANATION,
            maturity_stage=CapabilityPackMaturityStage.EXPERIMENTAL,
            primary_task_id="explain.v1",
            output_label=OutputLabel.EXPLANATION_ONLY,
            current_anchor_use_case_id=None,
            reusable_across_apps=False,
            intended_downstream_patterns=[
                "Decision blocker explanations where the downstream app owns deterministic status and policy truth.",
                "Workflow or governance explanations that transform bounded structured findings into operator-facing rationale.",
            ],
            governance_surface_ids=[
                "/platform/capability-packs",
                "/platform/capability-packs/decision_explanation.pack.v1",
                "/platform/capability-packs/decision_explanation.pack.v1/adoption-template",
                "/platform/capability-packs/decision_explanation.pack.v1/activation-readiness",
                "/platform/capability-packs/decision_explanation.pack.v1/runbook-readiness",
                "/platform/capability-packs/decision_explanation.pack.v1/observability-summary",
                "/platform/capability-packs/decision_explanation.pack.v1/governance-status",
                "/platform/evals/runtime-status",
                "/platform/use-cases/onboarding-template",
            ],
            status_summary=[
                "The decision-explanation pack family is now modeled explicitly instead of leaving blocker-explanation use cases as future ad hoc wrappers around explain.v1.",
                "The pack remains experimental because it does not yet have an implemented anchor use case and broader pack-specific runtime evidence.",
                "Modeling the pack now keeps commentary and explanation product families visible without claiming broader rollout maturity prematurely.",
            ],
        ),
    ]


def _build_pack_descriptor(
    *,
    pack_id: str,
    family_id: str,
    family_kind: CapabilityPackFamilyKind,
    maturity_stage: CapabilityPackMaturityStage,
    primary_task_id: str,
    output_label: OutputLabel,
    current_anchor_use_case_id: str | None,
    reusable_across_apps: bool,
    intended_downstream_patterns: list[str],
    governance_surface_ids: list[str],
    status_summary: list[str],
) -> CapabilityPackDescriptor:
    approval_gate = build_capability_pack_approval_gate(pack_id=pack_id)
    return CapabilityPackDescriptor(
        pack_id=pack_id,
        family_id=family_id,
        family_kind=family_kind,
        maturity_stage=maturity_stage,
        primary_task_id=primary_task_id,
        output_label=output_label,
        current_anchor_use_case_id=current_anchor_use_case_id,
        reusable_across_apps=reusable_across_apps,
        intended_downstream_patterns=intended_downstream_patterns,
        governance_surface_ids=governance_surface_ids,
        adoption_template_endpoint=f"/platform/capability-packs/{pack_id}/adoption-template",
        quality_gate_domain_id=approval_gate.domain_id,
        quality_gate_ready=approval_gate.approval_ready,
        quality_evidence_state=approval_gate.evidence_state,
        status_summary=status_summary,
    )


def _build_quality_expectations(pack_id: str) -> list[CapabilityPackQualityExpectation]:
    if pack_id == "analytics_commentary.pack.v1":
        return [
            CapabilityPackQualityExpectation(
                expectation_id="grounded_to_caller_facts",
                description="Commentary must remain grounded in caller-supplied structured analytics facts and must not recompute or invent portfolio metrics.",
            ),
            CapabilityPackQualityExpectation(
                expectation_id="materiality_focused",
                description="Commentary should prioritize materially important findings instead of narrating every input field uniformly.",
            ),
            CapabilityPackQualityExpectation(
                expectation_id="explanation_only",
                description="Output must remain explanation-oriented and must not cross into advice, recommendation, or domain-authoritative decision language.",
            ),
        ]
    return [
        CapabilityPackQualityExpectation(
            expectation_id="grounded_to_deterministic_state",
            description="Explanations must remain grounded in caller-supplied deterministic workflow or governance state and must not infer hidden reasons.",
        ),
        CapabilityPackQualityExpectation(
            expectation_id="explicit_blocker_reasoning",
            description="Output should explain the bounded blocker or decision rationale clearly rather than summarizing unrelated context.",
        ),
        CapabilityPackQualityExpectation(
            expectation_id="supportable_language",
            description="Explanation wording should be supportable by operators and auditable against the structured input state.",
        ),
    ]


def _build_unsupported_input_behaviors(
    pack_id: str,
) -> list[CapabilityPackUnsupportedInputBehavior]:
    if pack_id == "analytics_commentary.pack.v1":
        return [
            CapabilityPackUnsupportedInputBehavior(
                behavior_id="missing_metric_deltas",
                description="If structured metric deltas are missing, the pack should refuse or degrade rather than invent missing analytics context.",
            ),
            CapabilityPackUnsupportedInputBehavior(
                behavior_id="unbounded_free_form_payload",
                description="If the caller sends an unbounded free-form analytics dump, the pack should reject the request as outside the bounded product contract.",
            ),
        ]
    return [
        CapabilityPackUnsupportedInputBehavior(
            behavior_id="missing_decision_state",
            description="If deterministic decision or blocker state is missing, the pack should refuse rather than infer hidden approval logic.",
        ),
        CapabilityPackUnsupportedInputBehavior(
            behavior_id="mixed_authoritative_sources",
            description="If conflicting authoritative states are supplied, the pack should degrade or refuse rather than choose between them silently.",
        ),
    ]


def _build_non_goals(pack_id: str) -> list[str]:
    if pack_id == "analytics_commentary.pack.v1":
        return [
            "Recomputing analytics or attribution inside lotus-ai.",
            "Generating investment advice or portfolio actions.",
            "Accepting generic free-form performance storytelling as equivalent to structured commentary inputs.",
        ]
    return [
        "Overriding deterministic downstream decision logic.",
        "Inventing unstructured rationale for hidden blocker causes.",
        "Acting as a general-purpose workflow chatbot.",
    ]


def _build_detail_status_summary(pack_id: str) -> list[str]:
    if pack_id == "analytics_commentary.pack.v1":
        return [
            "The analytics commentary pack now cleanly absorbs the existing lotus-performance first-use-case path into a broader reusable product family.",
            "Pack maturity is now modeled separately from rollout readiness, so runtime quality-gate and governance surfaces still determine whether this reusable pack is currently safe to activate more broadly.",
        ]
    return [
        "The decision-explanation pack family is now modeled explicitly so future blocker and rationale use cases can onboard against a named product capability instead of a raw task wrapper.",
        "The pack remains experimental until a concrete downstream anchor and broader reuse posture exist, even though dedicated pack-level evaluation evidence now exists.",
    ]
