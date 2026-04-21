from app.contracts.workflow_packs import (
    WorkflowPackActivationState,
    WorkflowPackCallerIdentityClass,
    WorkflowPackEligibilityEvaluationRequest,
    WorkflowPackEligibilityResult,
    WorkflowPackEnvironment,
    WorkflowPackRegistrationStatus,
)
from app.services.workflow_pack_activation import evaluate_workflow_pack_eligibility
from app.services.workflow_pack_registry import (
    get_workflow_pack_registration,
    save_workflow_pack_registration,
)


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
    assert response.tenant_scope_applied is False
    assert response.workflow_surface_applied is True
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
    assert response.workflow_surface_applied is False


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
    assert response.workflow_surface_applied is True


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
    assert response.workflow_surface_applied is True


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
    assert response.workflow_surface_applied is True


def test_evaluate_workflow_pack_eligibility_denies_out_of_scope_identity_class() -> None:
    response = evaluate_workflow_pack_eligibility(
        WorkflowPackEligibilityEvaluationRequest(
            pack_id="advisor_brief.pack",
            version="v1",
            caller_app="lotus-gateway",
            environment=WorkflowPackEnvironment.QA,
            caller_identity_class=WorkflowPackCallerIdentityClass.OPERATOR_SUPPORT,
            workflow_surface="advisor-brief-panel",
        )
    )

    assert response.allowed is False
    assert response.eligibility_result == WorkflowPackEligibilityResult.DENIED_CALLER_SCOPE
    assert any("identity class" in reason for reason in response.denial_reasons)


def test_evaluate_workflow_pack_eligibility_denies_paused_registration() -> None:
    registration = get_workflow_pack_registration(pack_id="advisor_brief.pack", version="v1")
    assert registration is not None
    save_workflow_pack_registration(
        registration.model_copy(
            update={
                "activation_state": WorkflowPackActivationState.PAUSED,
                "pause_state": "PAUSED_FROM_PILOT",
            }
        )
    )

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

    assert response.allowed is False
    assert response.eligibility_result == WorkflowPackEligibilityResult.DENIED_PAUSED


def test_evaluate_workflow_pack_eligibility_denies_dark_registered_version() -> None:
    registration = get_workflow_pack_registration(pack_id="advisor_brief.pack", version="v1")
    assert registration is not None
    save_workflow_pack_registration(
        registration.model_copy(
            update={
                "activation_state": WorkflowPackActivationState.DARK,
                "registration_status": WorkflowPackRegistrationStatus.REGISTERED,
                "pause_state": "NOT_PAUSED",
            }
        )
    )

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

    assert response.allowed is False
    assert response.eligibility_result == WorkflowPackEligibilityResult.DENIED_NOT_ACTIVE


def test_evaluate_workflow_pack_eligibility_denies_retired_registration() -> None:
    registration = get_workflow_pack_registration(pack_id="advisor_brief.pack", version="v1")
    assert registration is not None
    save_workflow_pack_registration(
        registration.model_copy(
            update={
                "activation_state": WorkflowPackActivationState.RETIRED,
                "registration_status": WorkflowPackRegistrationStatus.REGISTERED,
                "pause_state": "NOT_PAUSED",
            }
        )
    )

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

    assert response.allowed is False
    assert response.eligibility_result == WorkflowPackEligibilityResult.DENIED_RETIRED


def test_evaluate_workflow_pack_eligibility_denies_out_of_scope_tenant() -> None:
    registration = get_workflow_pack_registration(pack_id="advisor_brief.pack", version="v1")
    assert registration is not None
    save_workflow_pack_registration(
        registration.model_copy(
            update={
                "tenant_scope": ["tenant-a"],
            }
        )
    )

    response = evaluate_workflow_pack_eligibility(
        WorkflowPackEligibilityEvaluationRequest(
            pack_id="advisor_brief.pack",
            version="v1",
            caller_app="lotus-gateway",
            environment=WorkflowPackEnvironment.QA,
            caller_identity_class=WorkflowPackCallerIdentityClass.INTERNAL_SERVICE,
            tenant_id="tenant-b",
            workflow_surface="advisor-brief-panel",
        )
    )

    assert response.allowed is False
    assert response.eligibility_result == WorkflowPackEligibilityResult.DENIED_TENANT_SCOPE
    assert response.tenant_scope_applied is True
