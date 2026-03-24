from __future__ import annotations

from app.config import settings
from app.contracts.use_cases import (
    UseCaseApprovalCriterion,
    UseCaseOnboardingChecklistItem,
    UseCaseOnboardingTemplateResponse,
)


def build_use_case_onboarding_template() -> UseCaseOnboardingTemplateResponse:
    return UseCaseOnboardingTemplateResponse(
        service=settings.service_name,
        version=settings.service_version,
        template_id="bounded_explanation_only_onboarding.v1",
        based_on_use_case_id="lotus_performance.analytics_commentary.v1",
        downstream_pattern=(
            "Explanation-only commentary over caller-supplied structured domain facts, with the "
            "downstream app retaining business truth and final rendering."
        ),
        adoption_scope=[
            "Downstream commentary use cases built on precomputed structured analytics.",
            "Bounded support or reviewer explanation flows where the calling app owns deterministic truth.",
            "Early Lotus app onboarding where retrieval and broad live-provider expansion are intentionally out of scope.",
        ],
        checklist=[
            UseCaseOnboardingChecklistItem(
                checklist_id="contract_boundary_defined",
                phase="contract",
                required=True,
                notes="Define one bounded request shape with domain-owned structured fields and an explicit task plus output-label pairing.",
            ),
            UseCaseOnboardingChecklistItem(
                checklist_id="caller_policy_registered",
                phase="identity",
                required=True,
                notes="Register the downstream caller with the minimum task and tenant scope needed for the use case.",
            ),
            UseCaseOnboardingChecklistItem(
                checklist_id="runtime_eval_family_staged_and_passing",
                phase="evaluation",
                required=True,
                notes="Stage a dedicated runtime-backed evaluation fixture family and require a passing approval-gate posture before rollout.",
            ),
            UseCaseOnboardingChecklistItem(
                checklist_id="limited_rollout_support_path_reviewed",
                phase="operations",
                required=True,
                notes="Document rollback, support triage, unsupported-input handling, and shared ownership before limited rollout.",
            ),
            UseCaseOnboardingChecklistItem(
                checklist_id="observability_and_artifact_review_path_available",
                phase="operations",
                required=True,
                notes="Confirm bounded observability incident review and descriptor-first artifact inspection are available for the downstream path.",
            ),
            UseCaseOnboardingChecklistItem(
                checklist_id="broader_generation_deferred",
                phase="scope",
                required=False,
                notes="Broader drafting, retrieval expansion, or live-provider breadth should remain deferred until the bounded commentary path is proven.",
            ),
        ],
        approval_criteria=[
            UseCaseApprovalCriterion(
                criterion_id="approval_contract_boundary",
                criterion_name="Contract boundary remains bounded",
                evaluation_surface="/platform/use-cases/first-production-use-case",
                pass_condition="The use case is explanation-only, downstream-owned, and explicitly limited to structured domain facts.",
            ),
            UseCaseApprovalCriterion(
                criterion_id="approval_runtime_readiness",
                criterion_name="Runtime readiness is fully satisfied",
                evaluation_surface="/platform/use-cases/first-production-use-case/readiness",
                pass_condition="Caller identity, runtime-backed eval evidence, safety posture, audit durability, observability review, and artifact review all report ready.",
            ),
            UseCaseApprovalCriterion(
                criterion_id="approval_runbook_readiness",
                criterion_name="Operational runbook posture is complete",
                evaluation_surface="/platform/use-cases/first-production-use-case/runbook-readiness",
                pass_condition="Shared ownership, rollback, support review, and unsupported-input triage are all documented and marked ready.",
            ),
            UseCaseApprovalCriterion(
                criterion_id="approval_governance_summary",
                criterion_name="Governance summary is rollout-ready",
                evaluation_surface="/platform/use-cases/first-production-use-case/governance-status",
                pass_condition="The composed governance posture reports LIMITED_ROLLOUT_READY with no blocking areas.",
            ),
        ],
        lessons_learned=[
            "A real first-use-case template needs explicit support-review surfaces, not only a passing evaluation gate.",
            "Audit, observability, and artifact review need to be treated as onboarding dependencies instead of future operational extras.",
            "The first reusable template is strongest when it stays explanation-only and keeps domain truth fully outside lotus-ai.",
        ],
        non_goals=[
            "Authorizing free-form drafting or business-decision generation by default.",
            "Bypassing caller identity, runtime-backed evaluation, or runbook review for faster onboarding.",
            "Treating this template as approval for multi-app rollout without a use-case-specific review.",
        ],
        status_summary=[
            "The first production-use-case onboarding work now yields a reusable bounded integration template for later Lotus apps.",
            "This template is intentionally narrow: explanation-only, structured-input, caller-governed onboarding remains the default adoption pattern.",
        ],
    )
