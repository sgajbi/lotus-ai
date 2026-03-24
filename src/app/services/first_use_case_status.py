from __future__ import annotations

from app.config import settings
from app.contracts.tasks import OutputLabel, TaskCategory
from app.contracts.use_cases import (
    FirstUseCaseContractField,
    FirstUseCaseOwnershipBoundary,
    FirstUseCaseRolloutPosture,
    FirstUseCaseRuntimeStatusResponse,
)
from app.services.capability_pack_catalog import get_capability_pack_by_id


def build_first_use_case_runtime_status() -> FirstUseCaseRuntimeStatusResponse:
    capability_pack = get_capability_pack_by_id("analytics_commentary.pack.v1")
    if capability_pack is None:
        raise RuntimeError("analytics_commentary.pack.v1 capability pack is not registered")

    return FirstUseCaseRuntimeStatusResponse(
        service=settings.service_name,
        version=settings.service_version,
        use_case_id="lotus_performance.analytics_commentary.v1",
        downstream_app="lotus-performance",
        capability_pack_id=capability_pack.pack_id,
        capability_pack_family_id=capability_pack.family_id,
        task_id="explain.v1",
        task_category=TaskCategory.EXPLAIN,
        output_label=OutputLabel.EXPLANATION_ONLY,
        rollout_posture=FirstUseCaseRolloutPosture.CONTRACT_DEFINED,
        contract_hardened=True,
        downstream_contract_fields=[
            FirstUseCaseContractField(
                field_name="analysis_scope",
                description="Identifies the bounded analytics slice being explained, such as period_return or attribution_change.",
            ),
            FirstUseCaseContractField(
                field_name="period_window",
                description="Structured period labels and comparison window owned by lotus-performance.",
            ),
            FirstUseCaseContractField(
                field_name="metric_deltas",
                description="Precomputed metric deltas or attribution changes to be explained without recomputation.",
            ),
            FirstUseCaseContractField(
                field_name="material_findings",
                description="Caller-curated highlights that define what changes are materially worth commentary.",
            ),
        ],
        ownership_boundaries=[
            FirstUseCaseOwnershipBoundary(
                owner="lotus-performance",
                responsibility="Owns analytics computation, metric truth, period selection, and final user-facing rendering.",
            ),
            FirstUseCaseOwnershipBoundary(
                owner="lotus-ai",
                responsibility="Transforms caller-supplied structured analytics into bounded explanation-only commentary with audit and evidence metadata.",
            ),
            FirstUseCaseOwnershipBoundary(
                owner="shared-operations",
                responsibility="Reviews rollout, support, and rollback posture across platform and downstream runbooks before broader activation.",
            ),
        ],
        dependency_summary=[
            "Caller identity and task authorization must allow lotus-performance to execute explain.v1.",
            "Prompt, safety, audit, observability, and artifact surfaces remain the governed runtime backbone for the use case.",
            "The use case is now explicitly anchored to analytics_commentary.pack.v1 so broader commentary-family product work can evolve without creating a parallel one-off use-case abstraction.",
            "Use-case readiness is tracked separately through /platform/use-cases/first-production-use-case/readiness, while limited-rollout governance is tracked through the paired runbook and governance endpoints.",
            "The first contract intentionally avoids retrieval dependency and does not require broader live-provider rollout to be considered defined.",
        ],
        non_goals=[
            "Recomputing or inferring portfolio analytics inside lotus-ai.",
            "Accepting free-form portfolio dumps instead of caller-curated structured analytics.",
            "Producing authoritative financial advice or portfolio decisions.",
        ],
        status_summary=[
            "The first production-oriented onboarding target is lotus-performance analytics commentary over caller-supplied structured facts.",
            "This use case now serves as the concrete anchor for the analytics_commentary capability pack rather than a standalone product abstraction.",
            "The request contract is intentionally narrow and explanation-only so rollout can be reviewed without delegating domain truth to lotus-ai.",
            "This runtime surface defines the contract and ownership boundary only; it does not claim rollout readiness, and runtime-backed onboarding plus limited-rollout governance are tracked separately.",
        ],
    )
