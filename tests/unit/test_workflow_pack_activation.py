from app.contracts.workflow_packs import (
    WorkflowPackCallerIdentityClass,
    WorkflowPackEligibilityEvaluationRequest,
    WorkflowPackEligibilityResult,
    WorkflowPackEnvironment,
)
from app.services.workflow_pack_activation import evaluate_workflow_pack_eligibility


def test_evaluate_workflow_pack_eligibility_allows_registered_pilot_scope() -> None:
    response = evaluate_workflow_pack_eligibility(
        WorkflowPackEligibilityEvaluationRequest(
            pack_id="advisor_brief.pack",
            version="v1",
            caller_app="lotus-gateway",
            environment=WorkflowPackEnvironment.QA,
            caller_identity_class=WorkflowPackCallerIdentityClass.INTERNAL_SERVICE,
            workflow_surface="advisor-brief-panel",
        )
    )

    assert response.allowed is True
    assert response.eligibility_result == WorkflowPackEligibilityResult.ALLOWED
    assert response.evaluated_registration_ref == "advisor_brief.pack@v1"
    assert response.denial_reasons == []


def test_evaluate_workflow_pack_eligibility_denies_unknown_registration() -> None:
    response = evaluate_workflow_pack_eligibility(
        WorkflowPackEligibilityEvaluationRequest(
            pack_id="unknown.pack",
            version="v1",
            caller_app="lotus-gateway",
            environment=WorkflowPackEnvironment.QA,
            caller_identity_class=WorkflowPackCallerIdentityClass.INTERNAL_SERVICE,
        )
    )

    assert response.allowed is False
    assert response.eligibility_result == WorkflowPackEligibilityResult.DENIED_NOT_REGISTERED


def test_evaluate_workflow_pack_eligibility_denies_discovered_version() -> None:
    response = evaluate_workflow_pack_eligibility(
        WorkflowPackEligibilityEvaluationRequest(
            pack_id="advisor_brief.pack",
            version="v2",
            caller_app="lotus-gateway",
            environment=WorkflowPackEnvironment.DEVELOPMENT,
            caller_identity_class=WorkflowPackCallerIdentityClass.INTERNAL_SERVICE,
            workflow_surface="advisor-brief-panel",
        )
    )

    assert response.allowed is False
    assert response.eligibility_result == WorkflowPackEligibilityResult.DENIED_VALIDATION_STATUS


def test_evaluate_workflow_pack_eligibility_denies_out_of_scope_environment() -> None:
    response = evaluate_workflow_pack_eligibility(
        WorkflowPackEligibilityEvaluationRequest(
            pack_id="advisor_brief.pack",
            version="v1",
            caller_app="lotus-gateway",
            environment=WorkflowPackEnvironment.PRODUCTION,
            caller_identity_class=WorkflowPackCallerIdentityClass.INTERNAL_SERVICE,
            workflow_surface="advisor-brief-panel",
        )
    )

    assert response.allowed is False
    assert response.eligibility_result == WorkflowPackEligibilityResult.DENIED_ENVIRONMENT_SCOPE


def test_evaluate_workflow_pack_eligibility_denies_out_of_scope_surface() -> None:
    response = evaluate_workflow_pack_eligibility(
        WorkflowPackEligibilityEvaluationRequest(
            pack_id="advisor_brief.pack",
            version="v1",
            caller_app="lotus-gateway",
            environment=WorkflowPackEnvironment.QA,
            caller_identity_class=WorkflowPackCallerIdentityClass.INTERNAL_SERVICE,
            workflow_surface="other-surface",
        )
    )

    assert response.allowed is False
    assert response.eligibility_result == WorkflowPackEligibilityResult.DENIED_SURFACE_SCOPE
