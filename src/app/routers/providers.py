from __future__ import annotations

from fastapi import APIRouter

from app.contracts.providers import (
    ProviderActivationReadinessResponse,
    ProviderBudgetPolicyResponse,
    ProviderCatalogResponse,
    ProviderEvidenceReadinessResponse,
    ProviderGovernanceStatusResponse,
    ProviderOperationsControlActionRequest,
    ProviderOperationsControlActionResponse,
    ProviderOperationsControlHistoryResponse,
    ProviderOperationsStatusResponse,
    ProviderPolicyResponse,
    ProviderQuotaPolicyResponse,
    ProviderRunbookReadinessResponse,
)
from app.services.provider_activation_readiness import build_provider_activation_readiness
from app.services.provider_budget_policy import build_provider_budget_policy
from app.services.provider_catalog import build_provider_catalog
from app.services.provider_evidence_readiness import build_provider_evidence_readiness
from app.services.provider_governance_status import build_provider_governance_status
from app.services.provider_operations_control import (
    apply_provider_operations_control_action,
    build_provider_operations_control_history,
)
from app.services.provider_operations_status import build_provider_operations_status
from app.services.provider_policy import build_provider_policy
from app.services.provider_quota_policy import build_provider_quota_policy
from app.services.provider_runbook_readiness import build_provider_runbook_readiness

router = APIRouter(prefix="/platform/providers", tags=["platform"])


@router.get(
    "",
    response_model=ProviderCatalogResponse,
    operation_id="getProviderCatalog",
    summary="Get lotus-ai provider catalog",
    description=(
        "Returns the governed provider catalog for lotus-ai, including which provider paths are "
        "documented, disabled, or enabled for execution in the current phase."
    ),
    responses={
        200: {"description": "Provider catalog returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_provider_catalog_route() -> ProviderCatalogResponse:
    return build_provider_catalog()


@router.get(
    "/policy",
    response_model=ProviderPolicyResponse,
    operation_id="getProviderPolicy",
    summary="Get lotus-ai provider execution policy",
    description=(
        "Returns the governed provider execution policy for lotus-ai, including supported modes "
        "and rejection behavior for the current phase."
    ),
    responses={
        200: {"description": "Provider execution policy returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_provider_policy_route() -> ProviderPolicyResponse:
    return build_provider_policy()


@router.get(
    "/quota-policy",
    response_model=ProviderQuotaPolicyResponse,
    operation_id="getProviderQuotaPolicy",
    summary="Get lotus-ai provider quota policy",
    description=(
        "Returns the governed quota posture for lotus-ai live text-generation execution, "
        "including configured task, caller, tenant, and default quota scopes."
    ),
    responses={
        200: {"description": "Provider quota policy returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_provider_quota_policy_route() -> ProviderQuotaPolicyResponse:
    return build_provider_quota_policy()


@router.get(
    "/budget-policy",
    response_model=ProviderBudgetPolicyResponse,
    operation_id="getProviderBudgetPolicy",
    summary="Get lotus-ai provider budget policy",
    description=(
        "Returns the governed budget posture for lotus-ai live text-generation execution, "
        "including current tracked spend, configured soft and hard budgets, and current budget state."
    ),
    responses={
        200: {"description": "Provider budget policy returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_provider_budget_policy_route() -> ProviderBudgetPolicyResponse:
    return build_provider_budget_policy()


@router.get(
    "/operations-status",
    response_model=ProviderOperationsStatusResponse,
    operation_id="getProviderOperationsStatus",
    summary="Get lotus-ai provider operations status",
    description=(
        "Returns the combined live-provider operations posture for lotus-ai, including rollout, "
        "quota, budget, and degradation truth in one operator-facing summary."
    ),
    responses={
        200: {"description": "Provider operations status returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_provider_operations_status_route() -> ProviderOperationsStatusResponse:
    return build_provider_operations_status()


@router.get(
    "/control-plane-actions",
    response_model=ProviderOperationsControlHistoryResponse,
    operation_id="getProviderOperationsControlHistory",
    summary="Get lotus-ai provider operations control-plane history",
    description=(
        "Returns the recent governed provider-operations reset and recovery actions recorded for "
        "lotus-ai, including whether durable control-plane reset actions are currently supported."
    ),
    responses={
        200: {"description": "Provider operations control-plane history returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_provider_operations_control_history_route() -> (
    ProviderOperationsControlHistoryResponse
):
    return build_provider_operations_control_history()


@router.post(
    "/control-plane-actions/reset",
    response_model=ProviderOperationsControlActionResponse,
    operation_id="applyProviderOperationsControlAction",
    summary="Apply a lotus-ai provider operations control-plane reset action",
    description=(
        "Applies one governed provider-operations reset action and records durable operator "
        "reason and approval metadata for later review."
    ),
    responses={
        200: {"description": "Provider operations control-plane action applied successfully."},
        409: {
            "description": "Durable provider-operations control actions are not currently supported."
        },
        422: {"description": "Invalid provider-operations control action request."},
        500: {"description": "Unexpected server error."},
    },
)
async def apply_provider_operations_control_action_route(
    request: ProviderOperationsControlActionRequest,
) -> ProviderOperationsControlActionResponse:
    return apply_provider_operations_control_action(request)


@router.get(
    "/activation-readiness",
    response_model=ProviderActivationReadinessResponse,
    operation_id="getProviderActivationReadiness",
    summary="Get lotus-ai provider activation readiness",
    description=(
        "Returns whether lotus-ai provider execution is currently ready for live activation, "
        "along with the blocking findings and governed activation path for future rollout."
    ),
    responses={
        200: {"description": "Provider activation readiness returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_provider_activation_readiness_route() -> ProviderActivationReadinessResponse:
    return build_provider_activation_readiness()


@router.get(
    "/runbook-readiness",
    response_model=ProviderRunbookReadinessResponse,
    operation_id="getProviderRunbookReadiness",
    summary="Get lotus-ai provider runbook readiness",
    description=(
        "Returns the operational runbook readiness required before lotus-ai live provider "
        "execution can be activated in a governed environment."
    ),
    responses={
        200: {"description": "Provider runbook readiness returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_provider_runbook_readiness_route() -> ProviderRunbookReadinessResponse:
    return build_provider_runbook_readiness()


@router.get(
    "/evidence-readiness",
    response_model=ProviderEvidenceReadinessResponse,
    operation_id="getProviderEvidenceReadiness",
    summary="Get lotus-ai provider evidence readiness",
    description=(
        "Returns whether lotus-ai provider rollout is currently supported by the required "
        "evaluation, audit, failover, and rollback evidence for future live activation."
    ),
    responses={
        200: {"description": "Provider evidence readiness returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_provider_evidence_readiness_route() -> ProviderEvidenceReadinessResponse:
    return build_provider_evidence_readiness()


@router.get(
    "/governance-status",
    response_model=ProviderGovernanceStatusResponse,
    operation_id="getProviderGovernanceStatus",
    summary="Get lotus-ai provider governance status",
    description=(
        "Returns the combined technical and operational governance posture for lotus-ai live "
        "provider execution so rollout reviewers can assess activation readiness in one view."
    ),
    responses={
        200: {"description": "Provider governance status returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_provider_governance_status_route() -> ProviderGovernanceStatusResponse:
    return build_provider_governance_status()
