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
from tests.support.runtime_settings import override_runtime_settings
from tests.unit.test_task_executor import _request
from tests.support.caller_credentials import (
    generate_caller_signing_key,
    mint_caller_credential,
    public_keys_setting,
)


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
    assert body["expansion_policy"]["bounded_expansion_enabled"] is True
    assert body["expansion_policy"]["expansion_blocked"] is False
    assert len(body["expansion_policy"]["capability_rules"]) == 2
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
    assert body["expansion_policy"]["bounded_expansion_enabled"] is True
    assert text_policy["selected_adapter_kind"] == "STUB"
    assert text_policy["rejection_category"] == "UNSUPPORTED_MODE"
    assert text_policy["allowed_modes"] == [
        "disabled",
        "stub",
        "openai",
        "local_openai_compatible",
    ]
    assert embedding_policy["selected_adapter_kind"] == "STUB"
    assert embedding_policy["allowed_modes"] == ["disabled", "stub", "enabled"]


def test_provider_operator_profile_route(client: TestClient) -> None:
    response = client.get("/platform/providers/operator-profile")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["selected_profile_id"] == "stubbed_disabled"
    assert body["provider_mode"] == "disabled"
    assert body["live_execution_enabled"] is False
    assert any(profile["profile_id"] == "managed_openai" for profile in body["profiles"])
    assert any(profile["profile_id"] == "local_ollama" for profile in body["profiles"])
    assert "/ai/tasks/execute" in body["switching_steps"][-1]


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
    assert body["expansion_policy"]["expansion_blocked"] is False
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


# Two real EdDSA credentials for the governed reset flow (issue #157).
_REQUESTER_KEY = generate_caller_signing_key()
_APPROVER_KEY = generate_caller_signing_key()
_PUBLIC_KEYS = public_keys_setting(
    **{"provider-ops-alpha": _REQUESTER_KEY, "provider-ops-beta": _APPROVER_KEY}
)
_REQUESTER_HEADERS = {
    "Authorization": "Bearer "
    + mint_caller_credential(
        signing_key=_REQUESTER_KEY,
        key_id="provider-ops-alpha",
        subject="lotus-platform",
        expires_in_seconds=3600,
    )
}
_APPROVER_HEADERS = {
    "Authorization": "Bearer "
    + mint_caller_credential(
        signing_key=_APPROVER_KEY,
        key_id="provider-ops-beta",
        subject="lotus-platform",
        expires_in_seconds=3600,
    )
}


def _verified_control_settings() -> None:
    settings.caller_trust_mode = "verified_service_jwt"
    settings.caller_jwt_issuer = "https://platform.lotus/issuer"
    settings.caller_jwt_audience = "lotus-ai"
    settings.caller_jwt_public_keys = _PUBLIC_KEYS


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

    _verified_control_settings()

    # Governed reset over HTTP (issue #157): the request step parks the intent
    # and no provider-operations state changes until a DISTINCT verified
    # credential approves the exact hash.
    pending = client.post(
        "/platform/providers/control-plane-actions/reset-requests",
        json={
            "action_type": "RESET_ALL_PROVIDER_OPERATIONS",
            "reason": "Clear durable provider controls after reviewed recovery.",
            "requested_by": "ops.user@lotus",
        },
        headers=_REQUESTER_HEADERS,
    )
    assert pending.status_code == 200
    action = pending.json()["governed_action"]
    assert action["status"] == "PENDING"
    # The failure recorded above is still counted: nothing was reset yet.
    quota_pending = client.get("/platform/providers/quota-policy", headers=_REQUESTER_HEADERS)
    assert quota_pending.json()["quotas"][0]["current_request_count"] == 1

    self_approval = client.post(
        "/platform/providers/control-plane-actions/reset-approvals",
        json={
            "action_type": "RESET_ALL_PROVIDER_OPERATIONS",
            "action_id": action["action_id"],
            "action_hash": action["action_hash"],
        },
        headers=_REQUESTER_HEADERS,
    )
    assert self_approval.status_code == 403

    response = client.post(
        "/platform/providers/control-plane-actions/reset-approvals",
        json={
            "action_type": "RESET_ALL_PROVIDER_OPERATIONS",
            "action_id": action["action_id"],
            "action_hash": action["action_hash"],
            "approved_by": "approver.user@lotus",
        },
        headers=_APPROVER_HEADERS,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["event"]["action_type"] == "RESET_ALL_PROVIDER_OPERATIONS"
    assert body["event"]["affected_record_count"] == 3
    assert body["event"]["authorization"]["caller_app"] == "lotus-platform"
    assert body["governed_action"]["requester_key_id"] == "provider-ops-alpha"
    assert body["governed_action"]["approver_key_id"] == "provider-ops-beta"
    assert "provider-ops-alpha" in body["event"]["requested_by"]
    assert "provider-ops-beta" in body["event"]["approved_by"]

    quota_response = client.get("/platform/providers/quota-policy", headers=_REQUESTER_HEADERS)
    budget_response = client.get("/platform/providers/budget-policy", headers=_REQUESTER_HEADERS)
    history_response = client.get(
        "/platform/providers/control-plane-actions", headers=_REQUESTER_HEADERS
    )

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
    assert body["required_item_count"] == 8
    # Honest catalog vocabulary (issue #284): documented posture is
    # DOCUMENTED_ONLY, an unwritten runbook is MISSING - nothing counts as
    # completed until a control is actually enforced.
    assert body["completed_required_item_count"] == 0
    assert body["items"][0]["runbook_id"] == "provider_operational_runbook"
    assert body["items"][0]["status"] == "DOCUMENTED_ONLY"
    assert body["items"][1]["status"] == "MISSING"
    assert body["items"][3]["runbook_id"] == "provider_spend_anomaly_response"
    assert body["items"][5]["runbook_id"] == "provider_embedding_rollout_and_recovery"
    assert body["items"][5]["status"] == "PARTIAL"
    assert body["items"][6]["runbook_id"] == "provider_degradation_and_circuit_response"


def test_provider_evidence_readiness_route(client: TestClient) -> None:
    response = client.get("/platform/providers/evidence-readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["evidence_ready"] is False
    assert body["required_item_count"] == 9
    assert body["completed_required_item_count"] == 7
    assert body["items"][0]["evidence_id"] == "provider_policy_fixture_pack"
    assert body["items"][0]["status"] == "READY"
    assert body["items"][1]["evidence_id"] == "provider_runtime_fixture_pack"
    assert body["items"][1]["status"] == "READY"
    assert body["items"][3]["evidence_id"] == "provider_operations_fixture_pack"
    assert body["items"][3]["status"] == "READY"
    assert body["items"][4]["evidence_id"] == "provider_degradation_fixture_pack"
    assert body["items"][4]["status"] == "READY"
    assert body["items"][5]["evidence_id"] == "provider_embedding_fixture_pack"
    assert body["items"][5]["status"] == "READY"
    assert body["items"][6]["evidence_id"] == "provider_regression_run_baseline"
    assert body["items"][6]["status"] == "READY"
    assert body["items"][7]["status"] == "FOUNDATION_STAGED"
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
    assert body["expansion_policy"]["bounded_expansion_enabled"] is True
    assert body["expansion_policy"]["expansion_blocked"] is False
    assert body["evidence_readiness"]["approval_gate"]["domain_id"] == "provider_execution"
    assert len(body["governance_summary"]) == 3


def test_provider_control_action_route_blocks_unauthorized_caller(
    client: TestClient, tmp_path: Path
) -> None:
    settings.provider_operations_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'lotus-ai-provider-ops-unauthorized-route.db'}"
    upgrade_database_to_head(settings.database_url)

    response = client.post(
        "/platform/providers/control-plane-actions/reset-requests",
        json={
            "action_type": "RESET_BUDGET",
            "reason": "Unauthorized budget reset attempt.",
        },
        headers={"X-Caller-App": "lotus-workbench"},
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


def test_routing_posture_route_reports_the_fixed_policy(client: TestClient) -> None:
    response = client.get("/platform/providers/routing-posture")

    assert response.status_code == 200
    body = response.json()
    assert body["policy_id"] == "fixed_configured_mode"
    assert body["policy_version"] == "v1"
    assert body["strategy"] == "FIXED"
    assert body["candidate"]["provider_mode"] == "disabled"
    assert body["enforcing_kill_switch_count"] == 0
    assert body["degradation"]["status"]
    assert body["candidate_universe"] is None
    assert body["capability_posture"] is None


def test_routing_posture_route_answers_capability_queries(client: TestClient) -> None:
    """Issue #244, S5 over HTTP: requirement query parameters add per-candidate
    eligibility verdicts computed over the derived universe."""

    with override_runtime_settings(
        provider_mode="openai",
        provider_rollout_state="CANARY_ENABLED",
        live_text_provider_id="text.openai",
        live_text_model_id="gpt-5.4",
        live_text_provider_api_key="secret",
        live_text_allowed_task_ids="explain.v1",
        routing_strategy="ordered_fallback",
        live_text_fallback_provider_id="text.anthropic",
        live_text_fallback_model_id="claude-sonnet-5",
        live_text_fallback_api_base="https://alternate.example/v1",
        live_text_fallback_api_key="secret-alternate",
        workflow_run_model_risk_inventory_json="[]",
    ):
        response = client.get("/platform/providers/routing-posture?structured_output_required=true")

        assert response.status_code == 200
        body = response.json()
        assert body["strategy"] == "ORDERED_FALLBACK"
        universe = body["candidate_universe"]
        assert universe is not None
        assert len(universe["candidate_entry_ids"]) == 2
        posture = body["capability_posture"]
        assert posture is not None
        assert posture["requirements"]["structured_output_required"] is True
        # Nothing is assessed in this fresh catalogue: unknown fails closed AS
        # unknown, per candidate, and nothing would be selected.
        assert [c["rejection_reason"] for c in posture["candidates"]] == [
            "CAPABILITY_UNKNOWN",
            "CAPABILITY_UNKNOWN",
        ]
        assert posture["would_select_entry_id"] is None


def test_rate_card_catalogue_route_reports_the_seeded_default(client: TestClient) -> None:
    from app.config import settings as app_settings
    from app.services.rate_card_store import reset_rate_card_store_cache

    original_input = app_settings.live_text_input_cost_per_1k_tokens
    original_output = app_settings.live_text_output_cost_per_1k_tokens
    try:
        reset_rate_card_store_cache()
        app_settings.live_text_input_cost_per_1k_tokens = None
        app_settings.live_text_output_cost_per_1k_tokens = None
        empty = client.get("/platform/providers/rate-cards")
        assert empty.status_code == 200
        assert empty.json()["cards"] == []

        app_settings.live_text_input_cost_per_1k_tokens = 0.02
        app_settings.live_text_output_cost_per_1k_tokens = 0.04
        body = client.get("/platform/providers/rate-cards").json()
    finally:
        app_settings.live_text_input_cost_per_1k_tokens = original_input
        app_settings.live_text_output_cost_per_1k_tokens = original_output
        reset_rate_card_store_cache()

    assert len(body["cards"]) == 1
    card = body["cards"][0]
    assert card["card_id"] == "default-live-text"
    assert card["scope_kind"] == "DEFAULT_LIVE_TEXT"
    assert card["input_cost_per_1k_tokens"] == 0.02
    assert card["currency"] == "USD"
