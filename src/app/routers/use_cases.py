from __future__ import annotations

from fastapi import APIRouter

from app.contracts.use_cases import (
    FirstUseCaseGovernanceStatusResponse,
    FirstUseCaseReadinessResponse,
    FirstUseCaseRunbookReadinessResponse,
    FirstUseCaseRuntimeStatusResponse,
    UseCaseOnboardingTemplateResponse,
)
from app.services.first_use_case_governance import build_first_use_case_governance_status
from app.services.first_use_case_readiness import build_first_use_case_readiness
from app.services.readiness_catalog import build_first_use_case_runbook_readiness
from app.services.first_use_case_status import build_first_use_case_runtime_status
from app.services.use_case_onboarding_template import build_use_case_onboarding_template

router = APIRouter(prefix="/platform/use-cases", tags=["platform"])


@router.get(
    "/first-production-use-case",
    response_model=FirstUseCaseRuntimeStatusResponse,
    operation_id="getFirstProductionUseCaseStatus",
    summary="Get lotus-ai first production use-case contract status",
    description=(
        "Returns the currently selected first production-oriented downstream use case, including "
        "the bounded contract fields and ownership boundaries defined for onboarding."
    ),
    responses={
        200: {"description": "First production use-case status returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_first_production_use_case_status_route() -> FirstUseCaseRuntimeStatusResponse:
    return build_first_use_case_runtime_status()


@router.get(
    "/first-production-use-case/readiness",
    response_model=FirstUseCaseReadinessResponse,
    operation_id="getFirstProductionUseCaseReadiness",
    summary="Get lotus-ai first production use-case readiness status",
    description=(
        "Returns the bounded readiness posture for the selected first production-oriented use "
        "case, including caller identity, safety posture, and runtime-backed evaluation evidence."
    ),
    responses={
        200: {"description": "First production use-case readiness returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_first_production_use_case_readiness_route() -> FirstUseCaseReadinessResponse:
    return build_first_use_case_readiness()


@router.get(
    "/first-production-use-case/runbook-readiness",
    response_model=FirstUseCaseRunbookReadinessResponse,
    operation_id="getFirstProductionUseCaseRunbookReadiness",
    summary="Get lotus-ai first production use-case runbook readiness",
    description=(
        "Returns the bounded operational runbook readiness posture for the selected first "
        "production-oriented use case, including shared ownership, rollback, and support review paths."
    ),
    responses={
        200: {"description": "First production use-case runbook readiness returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_first_production_use_case_runbook_readiness_route() -> (
    FirstUseCaseRunbookReadinessResponse
):
    return build_first_use_case_runbook_readiness()


@router.get(
    "/first-production-use-case/governance-status",
    response_model=FirstUseCaseGovernanceStatusResponse,
    operation_id="getFirstProductionUseCaseGovernanceStatus",
    summary="Get lotus-ai first production use-case governance status",
    description=(
        "Returns the composed governance posture for the selected first production-oriented use "
        "case, combining bounded readiness and operational runbook review for limited rollout."
    ),
    responses={
        200: {"description": "First production use-case governance status returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_first_production_use_case_governance_status_route() -> (
    FirstUseCaseGovernanceStatusResponse
):
    return build_first_use_case_governance_status()


@router.get(
    "/onboarding-template",
    response_model=UseCaseOnboardingTemplateResponse,
    operation_id="getUseCaseOnboardingTemplate",
    summary="Get lotus-ai reusable downstream use-case onboarding template",
    description=(
        "Returns the reusable onboarding checklist, approval criteria, and lessons learned "
        "derived from the first bounded production-oriented downstream use case."
    ),
    responses={
        200: {"description": "Use-case onboarding template returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_use_case_onboarding_template_route() -> UseCaseOnboardingTemplateResponse:
    return build_use_case_onboarding_template()
