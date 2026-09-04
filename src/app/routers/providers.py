from __future__ import annotations

from fastapi import APIRouter

from app.contracts.governed_actions import GovernedActionResponse
from app.contracts.provider_catalog import (
    ProviderCatalogResponse,
    ProviderOperatorProfileResponse,
    ProviderPolicyResponse,
)
from app.contracts.providers import (
    ProviderActivationReadinessResponse,
    ProviderBudgetPolicyResponse,
    ProviderEvidenceReadinessResponse,
    ProviderGovernanceStatusResponse,
    ProviderOperationsStatusResponse,
    ProviderQuotaPolicyResponse,
    ProviderRunbookReadinessResponse,
)
from app.contracts.provider_routing_posture import (
    RoutingPostureResponse,
)
from app.contracts.provider_operations import (
    ProviderOperationsControlHistoryResponse,
    ProviderOperationsResetApprovalRequest,
    ProviderOperationsResetApprovalResponse,
    ProviderOperationsResetIntentRequest,
)
from app.contracts.capability_requirements import CapabilityRequirements
from app.contracts.rate_cards import RateCardCatalogueResponse
from app.http.authenticated_caller import AuthenticatedCallerDependency
from app.services.provider_activation_readiness import build_provider_activation_readiness
from app.services.provider_budget_policy import build_provider_budget_policy
from app.services.provider_catalog import build_provider_catalog
from app.services.provider_evidence_readiness import build_provider_evidence_readiness
from app.services.provider_governance_status import build_provider_governance_status
from app.services.provider_operations_control import (
    approve_provider_operations_reset,
    request_provider_operations_reset,
    build_provider_operations_control_history,
)
from app.services.provider_operations_status import build_provider_operations_status
from app.services.provider_operator_profile import build_provider_operator_profile
from app.services.provider_policy import build_provider_policy
from app.services.provider_quota_policy import build_provider_quota_policy
from app.services.readiness_catalog import build_provider_runbook_readiness
from app.contracts.model_catalogue import (
    ServingPolicyChangeResponse,
    ServingPolicyIdentityAddApprovalRequest,
    ServingPolicyIdentityAddRequest,
    ServingPolicyIdentityRemovalRequest,
    ServingPolicyStatusResponse,
)
from app.services.serving_policy_control import (
    approve_serving_policy_identity_add,
    build_serving_policy_status,
    remove_serving_policy_identity,
    request_serving_policy_identity_add,
)
from app.services.rate_card_catalogue import build_rate_card_catalogue
from app.services.routing_posture import build_routing_posture

router = APIRouter(prefix="/platform/providers", tags=["platform"])


@router.get(
    "/routing-posture",
    response_model=RoutingPostureResponse,
    operation_id="getRoutingPosture",
    summary="Get the current routing posture",
    description=(
        "Returns the routing policy currently in force, the single candidate the fixed policy "
        "would bind for the next live execution (with its governed catalogue identity, "
        "lifecycle state and pinning), the circuit-breaker posture, enforcement flags, the "
        "count of currently enforcing kill switches, and - under the ordered strategy - the "
        "derived candidate universe with every reasoned exclusion. Optional capability "
        "requirement query parameters add per-candidate eligibility verdicts and the "
        "candidate the next such execution would select (issue #244, S5), computed with the "
        "exact check the gateway enforces. Per-request gates are evaluated per execution and "
        "recorded on its routing decision."
    ),
    responses={
        200: {"description": "Routing posture returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_routing_posture_route(
    structured_output_required: bool | None = None,
    tool_calling_required: bool | None = None,
    output_contract_key: str | None = None,
) -> RoutingPostureResponse:
    requirements: CapabilityRequirements | None = None
    if structured_output_required is not None or tool_calling_required is not None:
        requirements = CapabilityRequirements(
            structured_output_required=structured_output_required,
            tool_calling_required=tool_calling_required,
        )
    return build_routing_posture(requirements, output_contract_key=output_contract_key)


@router.get(
    "/rate-cards",
    response_model=RateCardCatalogueResponse,
    operation_id="getRateCardCatalogue",
    summary="Get the provider rate-card catalogue",
    description=(
        "Returns every stored rate card. Slice 1 carries the default live-text card the seed "
        "migrates from the legacy cost scalars; cost estimation resolves the effective card, "
        "so this catalogue is the source of cost truth."
    ),
    responses={
        200: {"description": "Rate-card catalogue returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_rate_card_catalogue_route() -> RateCardCatalogueResponse:
    return build_rate_card_catalogue()


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
    "/operator-profile",
    response_model=ProviderOperatorProfileResponse,
    operation_id="getProviderOperatorProfile",
    summary="Get lotus-ai provider operator profile",
    description=(
        "Returns the current operator-facing provider profile, supported switching targets, "
        "and the primary verification steps for confirming which live or stub path is active."
    ),
    responses={
        200: {"description": "Provider operator profile returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_provider_operator_profile_route() -> ProviderOperatorProfileResponse:
    return build_provider_operator_profile()


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


@router.get(
    "/serving-policy",
    response_model=ServingPolicyStatusResponse,
    operation_id="getServingPolicy",
    summary="Read the governed serving-policy artifact",
    description=(
        "The operative ordered serving identities and their version history "
        "(issue #295, S2). While no artifact exists, ordering honestly follows "
        "the configured primary/fallback pair and `current` is null."
    ),
    responses={
        200: {"description": "Current serving policy and version history."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_serving_policy_route(
    authenticated_caller: AuthenticatedCallerDependency,
) -> ServingPolicyStatusResponse:
    return build_serving_policy_status()


@router.post(
    "/serving-policy/identity-additions",
    response_model=GovernedActionResponse,
    operation_id="requestServingPolicyIdentityAdd",
    summary="Request adding an identity to the serving policy",
    description=(
        "Step one of the governed two-step addition (issue #295, S2): adding an "
        "identity widens what may serve, so a verified requester records the "
        "intent and the hash binds the full resulting order. Nothing changes "
        "until a DISTINCT verified credential approves."
    ),
    responses={
        200: {"description": "Addition recorded and pending approval."},
        403: {"description": "Caller is not authorized for provider control."},
        404: {"description": "No catalogue entry exists for the identity."},
        409: {"description": "The identity is ineligible or already in the order."},
        500: {"description": "Unexpected server error."},
    },
)
async def request_serving_policy_identity_add_route(
    request: ServingPolicyIdentityAddRequest,
    authenticated_caller: AuthenticatedCallerDependency,
) -> GovernedActionResponse:
    return request_serving_policy_identity_add(request, authenticated_caller)


@router.post(
    "/serving-policy/identity-addition-approvals",
    response_model=ServingPolicyChangeResponse,
    operation_id="approveServingPolicyIdentityAdd",
    summary="Approve a pending serving-policy addition",
    description=(
        "Step two (issue #295, S2): a verified credential DISTINCT from the "
        "requester approves the exact pending hash; the next immutable policy "
        "version becomes operative and records both credentials and the "
        "governed-action evidence reference."
    ),
    responses={
        200: {"description": "Policy version written; the identity may now serve."},
        403: {
            "description": "Not authorized, unverified, or the same credential as the requester."
        },
        404: {"description": "No pending action exists for the given id."},
        409: {"description": "The hash does not match, or the order changed since request."},
        500: {"description": "Unexpected server error."},
    },
)
async def approve_serving_policy_identity_add_route(
    request: ServingPolicyIdentityAddApprovalRequest,
    authenticated_caller: AuthenticatedCallerDependency,
) -> ServingPolicyChangeResponse:
    return approve_serving_policy_identity_add(request, authenticated_caller)


@router.post(
    "/serving-policy/identity-removals",
    response_model=ServingPolicyChangeResponse,
    operation_id="removeServingPolicyIdentity",
    summary="Remove an identity from the serving policy immediately",
    description=(
        "Risk-reducing, so the safety direction applies (issue #295, S2): one "
        "verified principal removes the identity immediately; the new version "
        "records approver as null - honestly single-principal."
    ),
    responses={
        200: {"description": "Policy version written; the identity no longer serves."},
        403: {"description": "Caller is not authorized for provider control."},
        404: {"description": "The identity is not in the serving order."},
        500: {"description": "Unexpected server error."},
    },
)
async def remove_serving_policy_identity_route(
    request: ServingPolicyIdentityRemovalRequest,
    authenticated_caller: AuthenticatedCallerDependency,
) -> ServingPolicyChangeResponse:
    return remove_serving_policy_identity(request, authenticated_caller)


@router.post(
    "/control-plane-actions/reset-requests",
    response_model=GovernedActionResponse,
    operation_id="requestProviderOperationsReset",
    summary="Request a provider operations reset",
    description=(
        "Step one of a governed reset (issue #157): records a pending reset intent under the "
        "requester's verified credential and returns the action hash a distinct verified "
        "credential must approve. Every reset is permissive - it re-opens a spending envelope "
        "or resumes traffic past breaker protection - so no provider-operations state changes "
        "until the approval executes."
    ),
    responses={
        200: {"description": "Reset intent recorded and pending approval."},
        403: {
            "description": "Caller is not authorized for provider control, or carries no "
            "verified credential."
        },
        409: {"description": "Durable provider-operations control actions are not supported."},
        422: {"description": "Invalid reset shape."},
        500: {"description": "Unexpected server error."},
    },
)
async def request_provider_operations_reset_route(
    request: ProviderOperationsResetIntentRequest,
    authenticated_caller: AuthenticatedCallerDependency,
) -> GovernedActionResponse:
    return request_provider_operations_reset(request, authenticated_caller)


@router.post(
    "/control-plane-actions/reset-approvals",
    response_model=ProviderOperationsResetApprovalResponse,
    operation_id="approveProviderOperationsReset",
    summary="Approve and execute a pending provider operations reset",
    description=(
        "Step two of a governed reset (issue #157): a verified credential DISTINCT from the "
        "requester's approves the exact pending action hash, which executes the reset and "
        "records the full request-approval-execution evidence chain."
    ),
    responses={
        200: {"description": "Reset executed under governed approval."},
        403: {
            "description": "Caller is not authorized, carries no verified credential, or is "
            "the same credential that requested the reset."
        },
        404: {"description": "No pending action exists."},
        409: {
            "description": "The action hash or shape does not match, or the action is not pending."
        },
        500: {"description": "Unexpected server error."},
    },
)
async def approve_provider_operations_reset_route(
    request: ProviderOperationsResetApprovalRequest,
    authenticated_caller: AuthenticatedCallerDependency,
) -> ProviderOperationsResetApprovalResponse:
    return approve_provider_operations_reset(request, authenticated_caller)


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
