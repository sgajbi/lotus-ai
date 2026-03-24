from __future__ import annotations

from app.config import settings
from app.contracts.capability_packs import (
    CapabilityPackAdoptionChecklistItem,
    CapabilityPackAdoptionCriterion,
    CapabilityPackAdoptionTemplateResponse,
)
from app.services.capability_pack_catalog import get_capability_pack_by_id


def build_capability_pack_adoption_template(
    pack_id: str,
) -> CapabilityPackAdoptionTemplateResponse:
    pack = get_capability_pack_by_id(pack_id)
    if pack is None:
        raise ValueError(f"Unknown capability pack: {pack_id}")

    return CapabilityPackAdoptionTemplateResponse(
        service=settings.service_name,
        version=settings.service_version,
        template_id=f"{pack_id}.adoption-template.v1",
        pack_id=pack.pack_id,
        current_reference_use_case_id=pack.current_anchor_use_case_id,
        downstream_patterns=pack.intended_downstream_patterns,
        recommended_caller_apps=_build_recommended_caller_apps(pack_id=pack_id),
        checklist=_build_checklist(pack_id=pack_id),
        approval_criteria=_build_approval_criteria(pack_id=pack_id),
        lessons_learned=_build_lessons_learned(pack_id=pack_id),
        non_goals=_build_non_goals(pack_id=pack_id),
        status_summary=_build_status_summary(pack_id=pack_id),
    )


def _build_recommended_caller_apps(pack_id: str) -> list[str]:
    if pack_id == "analytics_commentary.pack.v1":
        return [
            "lotus-performance",
            "lotus-risk",
            "lotus-advise",
        ]
    return [
        "lotus-manage",
        "lotus-advise",
        "lotus-risk",
    ]


def _build_checklist(pack_id: str) -> list[CapabilityPackAdoptionChecklistItem]:
    shared_items = [
        CapabilityPackAdoptionChecklistItem(
            checklist_id="pack_contract_adopted",
            phase="contract",
            required=True,
            notes="Adopt the named capability pack contract instead of treating the downstream flow as a raw explain.v1 wrapper.",
        ),
        CapabilityPackAdoptionChecklistItem(
            checklist_id="caller_policy_registered",
            phase="identity",
            required=True,
            notes="Register the caller app with the minimum task, provider, and retrieval posture needed for the pack.",
        ),
        CapabilityPackAdoptionChecklistItem(
            checklist_id="pack_eval_family_passing",
            phase="evaluation",
            required=True,
            notes="Require the pack-specific runtime-backed evaluation family to reach a passing approval-gate posture before rollout.",
        ),
        CapabilityPackAdoptionChecklistItem(
            checklist_id="governance_surfaces_reviewed",
            phase="operations",
            required=True,
            notes="Review pack activation, observability, runbook, and governance surfaces instead of inferring readiness from generic platform status alone.",
        ),
        CapabilityPackAdoptionChecklistItem(
            checklist_id="unsupported_input_behavior_confirmed",
            phase="scope",
            required=True,
            notes="Confirm the downstream app can surface refusal, degraded, or incomplete-input outcomes without silently inventing missing facts.",
        ),
    ]
    if pack_id == "analytics_commentary.pack.v1":
        return shared_items + [
            CapabilityPackAdoptionChecklistItem(
                checklist_id="downstream_rendering_owned",
                phase="product",
                required=True,
                notes="Keep metric computation, materiality thresholds, and final rendering owned by the downstream analytics application.",
            )
        ]
    return shared_items + [
        CapabilityPackAdoptionChecklistItem(
            checklist_id="deterministic_decision_owner_defined",
            phase="product",
            required=True,
            notes="Document the deterministic downstream system that owns blocker truth, approval logic, and final operator action.",
        )
    ]


def _build_approval_criteria(pack_id: str) -> list[CapabilityPackAdoptionCriterion]:
    base_route = f"/platform/capability-packs/{pack_id}"
    criteria = [
        CapabilityPackAdoptionCriterion(
            criterion_id="pack_contract_boundary",
            criterion_name="Pack contract boundary stays bounded",
            evaluation_surface=base_route,
            pass_condition="The pack remains explanation-only, grounded in bounded structured inputs, and does not expand into domain-authoritative decisions.",
        ),
        CapabilityPackAdoptionCriterion(
            criterion_id="pack_activation_readiness",
            criterion_name="Activation posture is ready",
            evaluation_surface=f"{base_route}/activation-readiness",
            pass_condition="The pack activation surface reports all required items complete with no blocking activation dependencies.",
        ),
        CapabilityPackAdoptionCriterion(
            criterion_id="pack_runbook_readiness",
            criterion_name="Runbook posture is ready",
            evaluation_surface=f"{base_route}/runbook-readiness",
            pass_condition="The pack runbook surface reports downstream ownership, support handling, and rollback posture ready for the intended adoption path.",
        ),
        CapabilityPackAdoptionCriterion(
            criterion_id="pack_governance_ready",
            criterion_name="Pack governance is rollout-ready",
            evaluation_surface=f"{base_route}/governance-status",
            pass_condition="The composed governance surface reports no blocking areas for the intended pack adoption path.",
        ),
    ]
    if pack_id == "analytics_commentary.pack.v1":
        criteria.append(
            CapabilityPackAdoptionCriterion(
                criterion_id="reference_use_case_truth",
                criterion_name="Reference use case remains truthful",
                evaluation_surface="/platform/use-cases/first-production-use-case/governance-status",
                pass_condition="The current lotus-performance reference path remains limited-rollout ready so downstream teams are reusing a live reference rather than a paper design.",
            )
        )
    return criteria


def _build_lessons_learned(pack_id: str) -> list[str]:
    if pack_id == "analytics_commentary.pack.v1":
        return [
            "The strongest commentary integrations reuse a named pack and keep deterministic analytics computation outside lotus-ai.",
            "Pack adoption is easier to support when quality gates, observability, and runbook review are inspected from pack-native surfaces instead of reconstructed from lower-level platform components.",
            "Commentary becomes reusable across apps only when unsupported-input posture is explicit rather than hidden in downstream presentation code.",
        ]
    return [
        "Decision-explanation reuse depends on keeping deterministic blocker truth outside lotus-ai and making that ownership explicit to operators.",
        "A named pack gives downstream teams a clearer adoption boundary than ad hoc explain.v1 wrapping, but rollout should stay blocked until there is a concrete anchored use case.",
        "Pack-oriented onboarding should defer broader drafting or recommendation behavior until the bounded explanation family is proven in production-shaped usage.",
    ]


def _build_non_goals(pack_id: str) -> list[str]:
    if pack_id == "analytics_commentary.pack.v1":
        return [
            "Treating the pack template as approval for free-form narrative generation over unbounded analytics payloads.",
            "Letting lotus-ai recompute analytics, attribution, or recommendation logic during pack adoption.",
            "Skipping pack governance review just because the underlying explain.v1 task is already available.",
        ]
    return [
        "Authorizing a decision-explanation rollout without a concrete downstream owner for deterministic blocker truth.",
        "Treating the pack template as approval for advice, action recommendation, or hidden-rule inference.",
        "Bypassing pack-specific evaluation and governance surfaces by relying on generic task availability.",
    ]


def _build_status_summary(pack_id: str) -> list[str]:
    if pack_id == "analytics_commentary.pack.v1":
        return [
            "Capability-pack adoption is now the preferred downstream onboarding path for commentary-style product integrations.",
            "The analytics commentary pack template is anchored to the implemented lotus-performance path so later teams start from a reusable product capability rather than a one-off use case.",
        ]
    return [
        "Decision-explanation adoption is now modeled as a pack-native onboarding path rather than a future ad hoc task wrapper.",
        "This template remains intentionally conservative because the pack still lacks a concrete implemented downstream anchor and should not be treated as rollout approval by itself.",
    ]
