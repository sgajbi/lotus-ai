from pathlib import Path
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.config import settings
from _pytest.monkeypatch import MonkeyPatch

from app.contracts.providers import (
    ProviderAdapterKind,
    ProviderExecutionResponse,
    ProviderFailureCategory,
)
from app.services.provider_budget_policy import record_provider_spend
from app.services.provider_degradation_state import record_provider_failure
from app.services.provider_operations_store import reset_provider_operations_store_cache
from app.services.provider_quota_policy import enforce_provider_quota
from app.services.provider_request_builder import build_provider_execution_request
from app.services.task_execution_pipeline import validate_task_request
from app.services.eval_async_execution import run_next_evaluation_execution_job
from app.services.eval_run_submission_service import submit_evaluation_run
from app.contracts.evals import EvaluationRunSubmissionRequest
from tests.support.migration_runner import upgrade_database_to_head
from tests.unit.test_task_executor import _request


def _budget_response(cost: float | None, *, stubbed: bool = False) -> ProviderExecutionResponse:
    return ProviderExecutionResponse(
        provider_id="text.openai",
        provider_mode="openai",
        adapter_kind=ProviderAdapterKind.OPENAI_LIVE,
        failure_category=None,
        timeout_ms=4000,
        retry_count=0,
        max_output_tokens=512,
        model_id="gpt-5.4",
        provider_request_id="req-budget-contract-1",
        input_tokens=100,
        output_tokens=200,
        total_tokens=300,
        estimated_cost_usd=cost,
        stubbed=stubbed,
        message="live response",
        structured_output={},
    )


def test_provider_catalog_route(client: TestClient) -> None:
    response = client.get("/platform/providers")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["provider_mode"] == "disabled"
    assert body["embedding_provider_mode"] == "disabled"
    assert body["text_generation_configuration"]["rollout_state"] == "STUB_DEFAULT"
    assert body["embedding_configuration"]["rollout_state"] == "DOCUMENTED_ONLY"
    assert body["text_generation_configuration"]["credential_status"] == "NOT_CONFIGURED"
    assert body["embedding_configuration"]["credential_status"] == "NOT_CONFIGURED"
    assert body["runtime_execution_enabled"] is False
    assert body["text_generation_runtime_execution_enabled"] is False
    assert body["embedding_runtime_execution_enabled"] is False
    assert any(provider["provider_id"] == "text.stub" for provider in body["providers"])
    assert any(
        provider["provider_id"] == "text.openai"
        and provider["adapter_kind"] == "OPENAI_LIVE"
        and provider["failure_category_on_use"] == "LIVE_EXECUTION_NOT_ENABLED"
        for provider in body["providers"]
    )
    assert any(
        provider["provider_id"] == "embeddings.openai"
        and provider["adapter_kind"] == "OPENAI_EMBEDDINGS_LIVE"
        and provider["failure_category_on_use"] == "LIVE_EXECUTION_NOT_ENABLED"
        for provider in body["providers"]
    )


def test_provider_policy_route(client: TestClient) -> None:
    response = client.get("/platform/providers/policy")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["text_generation_configuration"]["rollout_state"] == "STUB_DEFAULT"
    assert body["embedding_configuration"]["rollout_state"] == "DOCUMENTED_ONLY"
    text_policy = next(
        policy for policy in body["policies"] if policy["capability"] == "TEXT_GENERATION"
    )
    embedding_policy = next(
        policy for policy in body["policies"] if policy["capability"] == "EMBEDDINGS"
    )
    assert text_policy["selected_adapter_kind"] == "STUB"
    assert text_policy["rejection_category"] == "UNSUPPORTED_MODE"
    assert text_policy["allowed_modes"] == ["disabled", "stub", "openai"]
    assert embedding_policy["selected_adapter_kind"] == "STUB"
    assert embedding_policy["allowed_modes"] == ["disabled", "stub", "enabled"]


def test_provider_policy_route_reports_live_embedding_execution_when_enabled(
    client: TestClient,
) -> None:
    settings.embedding_provider_mode = "enabled"
    settings.live_embedding_provider_id = "embeddings.openai"
    settings.live_embedding_model_id = "text-embedding-3-large"
    settings.live_embedding_provider_api_key = "secret"

    response = client.get("/platform/providers/policy")

    assert response.status_code == 200
    body = response.json()
    embedding_policy = next(
        policy for policy in body["policies"] if policy["capability"] == "EMBEDDINGS"
    )
    assert body["embedding_configuration"]["rollout_state"] == "CANARY_ENABLED"
    assert embedding_policy["selected_adapter_kind"] == "OPENAI_EMBEDDINGS_LIVE"
    assert embedding_policy["live_execution_enabled"] is True


def test_provider_quota_policy_route(client: TestClient) -> None:
    response = client.get("/platform/providers/quota-policy")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["provider_mode"] == "disabled"
    assert body["quota_enforced"] is False
    assert body["configuration_valid"] is True
    assert body["matching_order"] == ["TENANT", "CALLER_APP", "TASK", "DEFAULT"]
    assert body["quotas"] == []


def test_provider_quota_policy_route_reports_durable_sql_backed_usage(
    client: TestClient, tmp_path: Path
) -> None:
    settings.provider_operations_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'lotus-ai-provider-ops.db'}"
    settings.live_text_quota_enforced = True
    settings.live_text_default_quota_limit = 3
    settings.live_text_task_quota_limits = "explain.v1=2"
    upgrade_database_to_head(settings.database_url)

    request = _request("explain.v1", expected_output_label=None)
    provider_request = build_provider_execution_request(context=validate_task_request(request))
    enforce_provider_quota(provider_request)

    response = client.get("/platform/providers/quota-policy")

    assert response.status_code == 200
    body = response.json()
    task_quota = next(quota for quota in body["quotas"] if quota["scope"] == "TASK")
    default_quota = next(quota for quota in body["quotas"] if quota["scope"] == "DEFAULT")
    assert task_quota["current_request_count"] == 1
    assert default_quota["current_request_count"] == 1


def test_provider_budget_policy_route(client: TestClient) -> None:
    response = client.get("/platform/providers/budget-policy")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["provider_mode"] == "disabled"
    assert body["budget_enforced"] is False
    assert body["configuration_valid"] is True
    assert body["budget_state"] == "NOT_ENFORCED"
    assert body["current_spend_usd"] == 0.0
    assert body["remaining_budget_usd"] is None


def test_provider_budget_policy_route_reports_durable_sql_backed_spend(
    client: TestClient, tmp_path: Path
) -> None:
    settings.provider_operations_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'lotus-ai-provider-budget.db'}"
    settings.live_text_budget_enforced = True
    settings.live_text_input_cost_per_1k_tokens = 0.01
    settings.live_text_output_cost_per_1k_tokens = 0.03
    settings.live_text_soft_budget_usd = 0.5
    settings.live_text_hard_budget_usd = 1.0
    upgrade_database_to_head(settings.database_url)

    record_provider_spend(_budget_response(0.75))

    response = client.get("/platform/providers/budget-policy")

    assert response.status_code == 200
    body = response.json()
    assert body["current_spend_usd"] == 0.75
    assert body["budget_state"] == "SOFT_LIMIT_REACHED"
    assert body["remaining_budget_usd"] == 0.25


def test_provider_operations_status_route(client: TestClient) -> None:
    response = client.get("/platform/providers/operations-status")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["provider_mode"] == "disabled"
    assert body["operations_state"] == "ROLLOUT_BLOCKED"
    assert body["runtime_execution_enabled"] is False
    assert body["rollout_blocked"] is True
    assert body["quota_policy"]["quota_enforced"] is False
    assert body["budget_policy"]["budget_enforced"] is False
    assert body["degradation_status"]["status"] == "DOCUMENTED_ONLY"
    assert len(body["summary"]) == 4
    assert "Current blocking or warning detail:" in body["summary"][-1]


def test_provider_operations_control_history_route(client: TestClient) -> None:
    response = client.get("/platform/providers/control-plane-actions")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["control_plane_store_mode"] == "memory"
    assert body["reset_actions_supported"] is False
    assert body["latest_events"] == []


def test_provider_operations_status_route_reports_durable_sql_backed_circuit_state(
    client: TestClient, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    settings.provider_operations_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'lotus-ai-provider-degradation.db'}"
    settings.provider_mode = "openai"
    settings.provider_rollout_state = "CANARY_ENABLED"
    settings.live_text_provider_id = "text.openai"
    settings.live_text_model_id = "gpt-5.4"
    settings.live_text_provider_api_key = "secret"
    settings.live_text_allowed_task_ids = "explain.v1"
    settings.live_text_degradation_enforced = True
    settings.live_text_degraded_failure_count_threshold = 1
    settings.live_text_circuit_open_failure_count_threshold = 2
    settings.live_text_circuit_open_seconds = 60
    upgrade_database_to_head(settings.database_url)

    fixed_now = datetime(2026, 3, 23, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(
        "app.services.provider_degradation_state._utcnow",
        lambda: fixed_now,
    )

    record_provider_failure(ProviderFailureCategory.PROVIDER_TIMEOUT)
    record_provider_failure(ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR)
    reset_provider_operations_store_cache()

    response = client.get("/platform/providers/operations-status")

    assert response.status_code == 200
    body = response.json()
    assert body["operations_state"] == "CIRCUIT_OPEN"
    assert body["degradation_status"]["status"] == "CIRCUIT_OPEN"
    assert body["degradation_status"]["timeout_failure_count"] == 1
    assert body["degradation_status"]["upstream_error_failure_count"] == 1


def test_provider_operations_control_action_route_resets_durable_sql_backed_state(
    client: TestClient, tmp_path: Path
) -> None:
    settings.provider_operations_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'lotus-ai-provider-ops-reset.db'}"
    settings.live_text_quota_enforced = True
    settings.live_text_default_quota_limit = 2
    settings.live_text_budget_enforced = True
    settings.live_text_input_cost_per_1k_tokens = 0.01
    settings.live_text_output_cost_per_1k_tokens = 0.03
    settings.live_text_hard_budget_usd = 1.0
    settings.live_text_degradation_enforced = True
    settings.live_text_degraded_failure_count_threshold = 1
    settings.live_text_circuit_open_failure_count_threshold = 2
    settings.live_text_circuit_open_seconds = 60
    upgrade_database_to_head(settings.database_url)

    request = _request("explain.v1", expected_output_label=None)
    provider_request = build_provider_execution_request(context=validate_task_request(request))
    enforce_provider_quota(provider_request)
    record_provider_spend(_budget_response(0.75))
    record_provider_failure(ProviderFailureCategory.PROVIDER_TIMEOUT)

    response = client.post(
        "/platform/providers/control-plane-actions/reset",
        json={
            "action_type": "RESET_ALL_PROVIDER_OPERATIONS",
            "caller_app": "lotus-platform",
            "requested_by": "ops.user@lotus",
            "approved_by": "approver.user@lotus",
            "reason": "Clear durable provider controls after reviewed recovery.",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["event"]["action_type"] == "RESET_ALL_PROVIDER_OPERATIONS"
    assert body["event"]["affected_record_count"] == 3
    assert body["event"]["authorization"]["caller_app"] == "lotus-platform"

    quota_response = client.get("/platform/providers/quota-policy")
    budget_response = client.get("/platform/providers/budget-policy")
    history_response = client.get("/platform/providers/control-plane-actions")

    assert quota_response.status_code == 200
    assert budget_response.status_code == 200
    assert history_response.status_code == 200
    assert quota_response.json()["quotas"][0]["current_request_count"] == 0
    assert budget_response.json()["current_spend_usd"] == 0.0
    assert history_response.json()["latest_events"][0]["event_id"] == body["event"]["event_id"]
    assert (
        history_response.json()["latest_events"][0]["authorization"]["caller_app"]
        == "lotus-platform"
    )


def test_provider_activation_readiness_route(client: TestClient) -> None:
    response = client.get("/platform/providers/activation-readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["provider_mode"] == "disabled"
    assert body["embedding_provider_mode"] == "disabled"
    assert body["text_generation_configuration"]["rollout_state"] == "STUB_DEFAULT"
    assert body["text_generation_configuration"]["credential_status"] == "NOT_CONFIGURED"
    assert body["activation_ready"] is False
    assert len(body["blocking_findings"]) == 4
    assert len(body["activation_path"]) == 9
    assert "/platform/providers/quota-policy" in body["activation_path"][1]
    assert "/platform/providers/budget-policy" in body["activation_path"][2]
    assert "/platform/providers/operations-status" in body["activation_path"][3]
    assert "/platform/providers/control-plane-actions" in body["activation_path"][4]
    assert "/platform/providers/governance-status" in body["activation_path"][-1]


def test_provider_runbook_readiness_route(client: TestClient) -> None:
    response = client.get("/platform/providers/runbook-readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["runbook_ready"] is False
    assert body["required_item_count"] == 7
    assert body["completed_required_item_count"] == 1
    assert body["items"][0]["runbook_id"] == "provider_operational_runbook"
    assert body["items"][1]["status"] == "NOT_READY"
    assert body["items"][3]["runbook_id"] == "provider_spend_anomaly_response"
    assert body["items"][5]["runbook_id"] == "provider_degradation_and_circuit_response"


def test_provider_evidence_readiness_route(client: TestClient) -> None:
    response = client.get("/platform/providers/evidence-readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["evidence_ready"] is False
    assert body["required_item_count"] == 8
    assert body["completed_required_item_count"] == 6
    assert body["items"][0]["evidence_id"] == "provider_policy_fixture_pack"
    assert body["items"][0]["status"] == "READY"
    assert body["items"][1]["evidence_id"] == "provider_runtime_fixture_pack"
    assert body["items"][1]["status"] == "READY"
    assert body["items"][3]["evidence_id"] == "provider_operations_fixture_pack"
    assert body["items"][3]["status"] == "READY"
    assert body["items"][4]["evidence_id"] == "provider_degradation_fixture_pack"
    assert body["items"][4]["status"] == "READY"
    assert body["items"][5]["evidence_id"] == "provider_regression_run_baseline"
    assert body["items"][5]["status"] == "READY"
    assert body["items"][6]["status"] == "FOUNDATION_STAGED"
    assert body["approval_gate"]["domain_id"] == "provider_execution"
    assert body["approval_gate"]["evidence_state"] == "STAGED_ONLY"
    assert (
        body["approval_gate"]["latest_historical_baseline_run_id"]
        == "foundation_eval_2026_03_22_001"
    )


def test_provider_governance_status_route(client: TestClient) -> None:
    response = client.get("/platform/providers/governance-status")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["governance_ready"] is False
    assert body["blocking_area_count"] == 3
    assert body["activation_readiness"]["activation_ready"] is False
    assert body["runbook_readiness"]["runbook_ready"] is False
    assert body["evidence_readiness"]["evidence_ready"] is False
    assert body["evidence_readiness"]["approval_gate"]["domain_id"] == "provider_execution"
    assert len(body["governance_summary"]) == 3


def test_provider_control_action_route_blocks_unauthorized_caller(
    client: TestClient, tmp_path: Path
) -> None:
    settings.provider_operations_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'lotus-ai-provider-ops-unauthorized-route.db'}"
    upgrade_database_to_head(settings.database_url)

    response = client.post(
        "/platform/providers/control-plane-actions/reset",
        json={
            "action_type": "RESET_BUDGET",
            "caller_app": "lotus-workbench",
            "requested_by": "ops.user@lotus",
            "approved_by": "approver.user@lotus",
            "reason": "Unauthorized budget reset attempt.",
        },
    )

    assert response.status_code == 403


def test_provider_evidence_readiness_route_reports_partial_runtime_coverage(
    client: TestClient,
) -> None:
    submit_evaluation_run(
        EvaluationRunSubmissionRequest(
            fixture_id="provider_policy_examples",
            caller_app="lotus-platform",
            correlation_id="corr-provider-approval-001",
            triggered_by="operator-a",
        )
    )
    run_next_evaluation_execution_job(worker_id="worker-a")

    response = client.get("/platform/providers/evidence-readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["approval_gate"]["evidence_state"] == "RUNTIME_PARTIAL"
    assert body["approval_gate"]["approval_ready"] is False
