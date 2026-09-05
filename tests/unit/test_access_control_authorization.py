from pathlib import Path

from app.contracts.access_control import (
    AuthorizationCapabilityType,
    AuthorizationOutcome,
)
from app.services.access_control_authorization import authorize_request
from tests.support.migration_runner import upgrade_database_to_head
from tests.support.runtime_settings import override_runtime_settings


def test_authorize_request_allows_registered_task_execution() -> None:
    decision = authorize_request(
        caller_app="lotus-manage",
        capability_type=AuthorizationCapabilityType.TASK_EXECUTION,
        tenant_id="tenant-sg-001",
        task_id="explain.v1",
    )

    assert decision.allowed is True
    assert decision.outcome == AuthorizationOutcome.ALLOWED


def test_authorize_request_allows_lotus_performance_first_use_case_task() -> None:
    decision = authorize_request(
        caller_app="lotus-performance",
        capability_type=AuthorizationCapabilityType.TASK_EXECUTION,
        tenant_id="tenant-sg-001",
        task_id="explain.v1",
    )

    assert decision.allowed is True
    assert decision.outcome == AuthorizationOutcome.ALLOWED


def test_authorize_request_allows_gateway_advisor_brief_task_without_tenant() -> None:
    decision = authorize_request(
        caller_app="lotus-gateway",
        capability_type=AuthorizationCapabilityType.TASK_EXECUTION,
        task_id="explain.v1",
    )

    assert decision.allowed is True
    assert decision.outcome == AuthorizationOutcome.ALLOWED


def test_authorize_request_blocks_unknown_caller() -> None:
    decision = authorize_request(
        caller_app="unknown-app",
        capability_type=AuthorizationCapabilityType.TASK_EXECUTION,
        task_id="explain.v1",
    )

    assert decision.allowed is False
    assert decision.outcome == AuthorizationOutcome.BLOCKED_UNKNOWN_CALLER


def test_authorize_request_blocks_missing_required_tenant() -> None:
    decision = authorize_request(
        caller_app="lotus-manage",
        capability_type=AuthorizationCapabilityType.TASK_EXECUTION,
        task_id="explain.v1",
    )

    assert decision.allowed is False
    assert decision.outcome == AuthorizationOutcome.BLOCKED_TENANT_REQUIRED


def test_authorize_request_blocks_restricted_tenant_mismatch() -> None:
    decision = authorize_request(
        caller_app="lotus-manage",
        capability_type=AuthorizationCapabilityType.TASK_EXECUTION,
        tenant_id="tenant-us-002",
        task_id="explain.v1",
    )

    assert decision.allowed is False
    assert decision.outcome == AuthorizationOutcome.BLOCKED_TENANT_NOT_ALLOWED


def test_async_submission_blocks_a_tenant_assertion_outside_the_caller_scope() -> None:
    """Issue #302: tenant attribution is caller-asserted source truth, so the
    assertion is accepted only inside the caller's authorized tenant scope -
    an application cannot attribute async work to a tenant its policy does
    not allow."""

    decision = authorize_request(
        caller_app="lotus-manage",
        capability_type=AuthorizationCapabilityType.ASYNC_SUBMISSION,
        tenant_id="tenant-us-002",
    )

    assert decision.allowed is False
    assert decision.outcome == AuthorizationOutcome.BLOCKED_TENANT_NOT_ALLOWED


def test_async_submission_allows_a_tenant_assertion_inside_the_caller_scope() -> None:
    decision = authorize_request(
        caller_app="lotus-manage",
        capability_type=AuthorizationCapabilityType.ASYNC_SUBMISSION,
        tenant_id="tenant-sg-001",
    )

    assert decision.allowed is True
    assert decision.outcome == AuthorizationOutcome.ALLOWED
    assert "authorized tenant scope" in decision.summary


def test_async_submission_requires_attribution_from_a_tenant_required_caller() -> None:
    """A caller whose policy demands tenant scope on its work must attribute
    async submissions too - unattributed work from such a caller would be a
    silent hole in the trust boundary."""

    decision = authorize_request(
        caller_app="lotus-manage",
        capability_type=AuthorizationCapabilityType.ASYNC_SUBMISSION,
    )

    assert decision.allowed is False
    assert decision.outcome == AuthorizationOutcome.BLOCKED_TENANT_REQUIRED


def test_async_submission_keeps_current_behaviour_for_an_unrestricted_caller() -> None:
    decision = authorize_request(
        caller_app="lotus-platform",
        capability_type=AuthorizationCapabilityType.ASYNC_SUBMISSION,
    )

    assert decision.allowed is True
    assert decision.outcome == AuthorizationOutcome.ALLOWED


def test_async_submission_blocks_an_unknown_caller() -> None:
    decision = authorize_request(
        caller_app="unregistered-app",
        capability_type=AuthorizationCapabilityType.ASYNC_SUBMISSION,
        tenant_id="tenant-sg-001",
    )

    assert decision.allowed is False
    assert decision.outcome == AuthorizationOutcome.BLOCKED_UNKNOWN_CALLER


def test_authorize_request_blocks_unapproved_retrieval_source() -> None:
    decision = authorize_request(
        caller_app="lotus-workbench",
        capability_type=AuthorizationCapabilityType.RETRIEVAL_EXECUTION,
        source_ids=["lotus-platform-standards"],
    )

    assert decision.allowed is False
    assert decision.outcome == AuthorizationOutcome.BLOCKED_RETRIEVAL_SOURCE_NOT_ALLOWED


def test_authorize_request_defaults_retrieval_scope_to_allowed_sources() -> None:
    decision = authorize_request(
        caller_app="lotus-workbench",
        capability_type=AuthorizationCapabilityType.RETRIEVAL_EXECUTION,
    )

    assert decision.allowed is True
    assert decision.effective_source_ids == ["lotus-platform-rfcs", "lotus-ai-architecture"]


def test_authorize_request_blocks_live_provider_for_disallowed_caller() -> None:
    decision = authorize_request(
        caller_app="lotus-advise",
        capability_type=AuthorizationCapabilityType.LIVE_PROVIDER_EXECUTION,
        tenant_id="tenant-us-002",
        task_id="explain.v1",
    )

    assert decision.allowed is False
    assert decision.outcome == AuthorizationOutcome.BLOCKED_LIVE_PROVIDER_NOT_ALLOWED


def test_authorize_request_allows_advise_singapore_tenant_for_canonical_workflows() -> None:
    decision = authorize_request(
        caller_app="lotus-advise",
        capability_type=AuthorizationCapabilityType.TASK_EXECUTION,
        tenant_id="tenant-sg-001",
        task_id="explain.v1",
    )

    assert decision.allowed is True
    assert decision.outcome == AuthorizationOutcome.ALLOWED


def test_authorize_request_allows_lotus_idea_review_gated_task() -> None:
    decision = authorize_request(
        caller_app="lotus-idea",
        capability_type=AuthorizationCapabilityType.TASK_EXECUTION,
        tenant_id="tenant-sg-001",
        task_id="explain.v1",
    )

    assert decision.allowed is True
    assert decision.outcome == AuthorizationOutcome.ALLOWED


def test_authorize_request_uses_sql_backed_registry_when_configured(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'access-control-authorization.db'}"
    upgrade_database_to_head(database_url)

    with override_runtime_settings(
        access_control_store_mode="sqlalchemy",
        database_url=database_url,
    ):
        decision = authorize_request(
            caller_app="lotus-gateway",
            capability_type=AuthorizationCapabilityType.TASK_EXECUTION,
            task_id="explain.v1",
        )

    assert decision.allowed is True
    assert decision.outcome == AuthorizationOutcome.ALLOWED


def test_authorize_request_allows_async_control_for_platform_caller() -> None:
    decision = authorize_request(
        caller_app="lotus-platform",
        capability_type=AuthorizationCapabilityType.ASYNC_CONTROL,
    )

    assert decision.allowed is True
    assert decision.outcome == AuthorizationOutcome.ALLOWED


def test_authorize_request_blocks_prompt_control_for_non_operator_caller() -> None:
    decision = authorize_request(
        caller_app="lotus-manage",
        capability_type=AuthorizationCapabilityType.PROMPT_CONTROL,
        tenant_id="tenant-sg-001",
        task_id="explain.v1",
    )

    assert decision.allowed is False
    assert decision.outcome == AuthorizationOutcome.BLOCKED_PROMPT_CONTROL_NOT_ALLOWED


def test_authorize_request_blocks_provider_control_for_unknown_caller() -> None:
    decision = authorize_request(
        caller_app="unknown-app",
        capability_type=AuthorizationCapabilityType.PROVIDER_CONTROL,
    )

    assert decision.allowed is False
    assert decision.outcome == AuthorizationOutcome.BLOCKED_UNKNOWN_CALLER


def test_authorize_request_blocks_async_control_without_tenant_noise_for_non_operator() -> None:
    decision = authorize_request(
        caller_app="lotus-manage",
        capability_type=AuthorizationCapabilityType.ASYNC_CONTROL,
    )

    assert decision.allowed is False
    assert decision.outcome == AuthorizationOutcome.BLOCKED_ASYNC_CONTROL_NOT_ALLOWED


def test_authorize_request_admits_lotus_idea_canonical_platform_tenant() -> None:
    """Issue #323: real Idea candidates carry the canonical platform tenant;
    the first live idea-explanation journey execution was refused because the
    caller policy admitted only the lotus-ai-local proof fixture tenant."""

    decision = authorize_request(
        caller_app="lotus-idea",
        capability_type=AuthorizationCapabilityType.TASK_EXECUTION,
        tenant_id="tenant-private-bank-sg",
        task_id="explain.v1",
    )

    assert decision.allowed is True


def test_authorize_request_still_blocks_lotus_idea_unadmitted_tenant() -> None:
    decision = authorize_request(
        caller_app="lotus-idea",
        capability_type=AuthorizationCapabilityType.TASK_EXECUTION,
        tenant_id="tenant-not-admitted",
        task_id="explain.v1",
    )

    assert decision.allowed is False
    assert decision.outcome == AuthorizationOutcome.BLOCKED_TENANT_NOT_ALLOWED
