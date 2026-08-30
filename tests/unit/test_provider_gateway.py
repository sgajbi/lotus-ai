import pytest
from fastapi import HTTPException

from app.config import settings
from app.contracts.providers import (
    ProviderAdapterKind,
    ProviderExecutionRequest,
    ProviderFailureCategory,
)
from app.providers.base import ProviderExecutionError
from app.services.provider_gateway import execute_text_generation


def _request(**overrides: object) -> ProviderExecutionRequest:
    payload: dict[str, object] = {
        "task_id": "explain.v1",
        "caller_app": "lotus-manage",
        "requested_by": "ops.user@lotus",
        "tenant_id": "tenant-sg-001",
        "prompt_version": "foundation.explain.v1",
        "system_instructions": "Explain structured outputs conservatively.",
        "output_contract_notes": "Return explanation only. Avoid unsupported recommendations.",
        "output_label": "EXPLANATION_ONLY",
        "safety_mode": "documented_only",
        "redaction_posture": "MINIMIZATION_REQUIRED",
        "context_summary": "Explain rebalance outcome",
        "context_payload": {"status": "BLOCKED", "rule_count": 3},
        "source_refs": ["lotus-manage:run:reb_001"],
        "timeout_ms": 4000,
        "retry_limit": 0,
        "max_output_tokens": 512,
    }
    payload.update(overrides)
    return ProviderExecutionRequest.model_validate(payload)


def test_execute_text_generation_routes_through_stub_provider() -> None:
    response = execute_text_generation(_request())
    structured_output = response.structured_output
    assert isinstance(structured_output, dict)

    assert response.provider_id == "text.stub"
    assert response.provider_mode == "disabled"
    assert response.adapter_kind == ProviderAdapterKind.STUB
    assert response.failure_category is None
    assert response.timeout_ms == 4000
    assert response.retry_count == 0
    assert response.max_output_tokens == 512
    assert response.stubbed is True
    assert structured_output["provider_id"] == "text.stub"
    assert structured_output["adapter_kind"] == "STUB"
    assert structured_output["timeout_ms"] == 4000
    assert structured_output["retry_count"] == 0
    assert structured_output["max_output_tokens"] == 512
    assert structured_output["context_keys"] == ["rule_count", "status"]
    assert structured_output["output_label"] == "EXPLANATION_ONLY"
    assert structured_output["redaction_posture"] == "MINIMIZATION_REQUIRED"
    assert response.message == (
        "Stub execution completed for foundation-phase task explain.v1 requested by lotus-manage."
    )


def test_execute_text_generation_returns_source_grounded_advisor_brief_stub() -> None:
    response = execute_text_generation(
        _request(
            caller_app="lotus-gateway",
            context_summary="Draft client talking points from source performance facts.",
            context_payload={
                "portfolio": {"portfolio_id": "PB_SG_GLOBAL_BAL_001"},
                "period": {"period": "YTD"},
                "performance": {
                    "portfolio_return_pct": 1.25,
                    "benchmark_return_pct": 7.93,
                    "active_return_pct": -6.68,
                },
                "supportability": [
                    {"key": "portfolio_context", "value": "ready"},
                    {"key": "performance_context", "value": "ready"},
                ],
                "contribution": {"top_positions": [{"position_id": "AAPL US"}]},
                "attribution": {"top_effects": [{"key_label": "Asset Class / Equity"}]},
            },
            source_refs=[
                "lotus-gateway:workbench:PB_SG_GLOBAL_BAL_001:performance-summary:YTD",
            ],
        )
    )
    structured_output = response.structured_output
    assert isinstance(structured_output, dict)

    assert response.provider_id == "text.stub"
    assert response.stubbed is True
    assert response.message == (
        "PB_SG_GLOBAL_BAL_001 delivered 1.25% over YTD versus 7.93% for the benchmark, "
        "resulting in -6.68% active return. net flow was N/A and ending market value "
        "was N/A. largest contribution came from AAPL US (N/A). largest benchmark-relative "
        "attribution effect was Asset Class / Equity (N/A)."
    )
    assert structured_output["advisor_brief_status"] == "ready"
    assert structured_output["coverage_state"] == "ready"
    talking_points = structured_output["talking_points"]
    assert isinstance(talking_points, list)
    assert isinstance(talking_points[0], dict)
    assert talking_points[0]["headline"] == ("YTD active return was -6.68%.")
    assert structured_output["grounded_facts"] == [
        {
            "metric_label": "Portfolio Return",
            "metric_value": "1.25%",
            "source_ref": "lotus-gateway:workbench:PB_SG_GLOBAL_BAL_001:performance-summary:YTD",
        },
        {
            "metric_label": "Benchmark Return",
            "metric_value": "7.93%",
            "source_ref": "lotus-gateway:workbench:PB_SG_GLOBAL_BAL_001:performance-summary:YTD",
        },
        {
            "metric_label": "Active Return",
            "metric_value": "-6.68%",
            "source_ref": "lotus-gateway:workbench:PB_SG_GLOBAL_BAL_001:performance-summary:YTD",
        },
        {
            "metric_label": "Money-Weighted Return",
            "metric_value": "N/A",
            "source_ref": "lotus-gateway:workbench:PB_SG_GLOBAL_BAL_001:performance-summary:YTD",
        },
    ]


def test_execute_text_generation_rejects_blocked_live_provider_mode() -> None:
    settings.provider_mode = "openai"

    with pytest.raises(HTTPException) as exc_info:
        execute_text_generation(_request(context_payload={"status": "BLOCKED"}, source_refs=[]))

    assert exc_info.value.status_code == 503
    assert "LIVE_EXECUTION_NOT_ENABLED" in str(exc_info.value.detail)

    settings.provider_mode = "disabled"


def test_execute_text_generation_rejects_blocked_local_live_provider_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings.provider_mode = "local_openai_compatible"
    settings.provider_rollout_state = "CANARY_ENABLED"
    settings.live_text_provider_id = "text.local"
    settings.live_text_model_id = "qwen3:8b"
    settings.live_text_api_base = "http://ollama:11434/v1"
    settings.live_text_allowed_task_ids = "explain.v1"
    monkeypatch.setattr(
        "app.services.provider_live_execution_state.build_local_openai_compatible_endpoint_status",
        lambda: type(
            "ProbeStatus",
            (),
            {
                "endpoint_reachable": False,
                "model_available": False,
                "blocking_reason": "Local OpenAI-compatible endpoint is not reachable.",
            },
        )(),
    )

    with pytest.raises(HTTPException) as exc_info:
        execute_text_generation(_request(context_payload={"status": "BLOCKED"}, source_refs=[]))

    assert exc_info.value.status_code == 503
    assert "LIVE_EXECUTION_NOT_ENABLED" in str(exc_info.value.detail)

    settings.provider_mode = "disabled"


def test_execute_text_generation_rejects_live_provider_when_quota_is_exceeded() -> None:
    class _LiveAdapter:
        def execute(self, request: ProviderExecutionRequest) -> object:
            return type(
                "Response",
                (),
                {
                    "provider_id": "text.openai",
                    "provider_mode": "openai",
                    "adapter_kind": ProviderAdapterKind.OPENAI_LIVE,
                    "failure_category": None,
                    "timeout_ms": request.timeout_ms,
                    "retry_count": 0,
                    "max_output_tokens": request.max_output_tokens,
                    "model_id": "gpt-5.4",
                    "provider_request_id": "req_quota_1",
                    "input_tokens": 10,
                    "output_tokens": 20,
                    "total_tokens": 30,
                    "estimated_cost_usd": 0.01,
                    "stubbed": False,
                    "message": "live response",
                    "structured_output": {},
                },
            )()

    settings.provider_mode = "openai"
    settings.provider_rollout_state = "CANARY_ENABLED"
    settings.live_text_provider_id = "text.openai"
    settings.live_text_model_id = "gpt-5.4"
    settings.live_text_provider_api_key = "secret"
    settings.live_text_allowed_task_ids = "explain.v1"
    settings.live_text_quota_enforced = True
    settings.live_text_task_quota_limits = "explain.v1=1"
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        "app.services.provider_gateway.resolve_text_generation_adapter",
        lambda mode: _LiveAdapter(),
    )

    first_response = execute_text_generation(_request())
    assert first_response.provider_id == "text.openai"

    with pytest.raises(HTTPException) as exc_info:
        execute_text_generation(_request())

    assert exc_info.value.status_code == 503
    assert "QUOTA_EXCEEDED" in str(exc_info.value.detail)
    monkeypatch.undo()


def test_execute_text_generation_blocks_unauthorized_live_provider_caller() -> None:
    settings.provider_mode = "openai"
    settings.provider_rollout_state = "CANARY_ENABLED"
    settings.live_text_provider_id = "text.openai"
    settings.live_text_model_id = "gpt-5.4"
    settings.live_text_provider_api_key = "secret"
    settings.live_text_allowed_task_ids = "explain.v1"

    with pytest.raises(HTTPException) as exc_info:
        execute_text_generation(
            _request(
                caller_app="lotus-advise",
                tenant_id="tenant-us-002",
            )
        )

    assert exc_info.value.status_code == 403
    assert "not authorized for live provider execution" in str(exc_info.value.detail)

    settings.provider_mode = "disabled"


def test_execute_text_generation_routes_local_provider_through_live_controls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _LocalLiveAdapter:
        def execute(self, request: ProviderExecutionRequest) -> object:
            return type(
                "Response",
                (),
                {
                    "provider_id": "text.local",
                    "provider_mode": "local_openai_compatible",
                    "adapter_kind": ProviderAdapterKind.OPENAI_COMPATIBLE_LOCAL,
                    "failure_category": None,
                    "timeout_ms": request.timeout_ms,
                    "retry_count": 0,
                    "max_output_tokens": request.max_output_tokens,
                    "model_id": "qwen3:8b",
                    "provider_request_id": "req_local_1",
                    "input_tokens": 10,
                    "output_tokens": 20,
                    "total_tokens": 30,
                    "estimated_cost_usd": 0.0,
                    "stubbed": False,
                    "message": "local response",
                    "structured_output": {},
                },
            )()

    settings.provider_mode = "local_openai_compatible"
    settings.provider_rollout_state = "CANARY_ENABLED"
    settings.live_text_provider_id = "text.local"
    settings.live_text_model_id = "qwen3:8b"
    settings.live_text_api_base = "http://ollama:11434/v1"
    settings.live_text_allowed_task_ids = "explain.v1"
    monkeypatch.setattr(
        "app.services.provider_live_execution_state.build_local_openai_compatible_endpoint_status",
        lambda: type(
            "ProbeStatus",
            (),
            {
                "endpoint_reachable": True,
                "model_available": True,
                "blocking_reason": None,
            },
        )(),
    )
    monkeypatch.setattr(
        "app.services.provider_gateway.resolve_text_generation_adapter",
        lambda mode: _LocalLiveAdapter(),
    )

    response = execute_text_generation(_request())

    assert response.provider_id == "text.local"
    assert response.provider_mode == "local_openai_compatible"
    assert response.stubbed is False


def test_execute_text_generation_rejects_live_provider_when_budget_is_exceeded() -> None:
    class _LiveAdapter:
        def execute(self, request: ProviderExecutionRequest) -> object:
            return type(
                "Response",
                (),
                {
                    "provider_id": "text.openai",
                    "provider_mode": "openai",
                    "adapter_kind": ProviderAdapterKind.OPENAI_LIVE,
                    "failure_category": None,
                    "timeout_ms": request.timeout_ms,
                    "retry_count": 0,
                    "max_output_tokens": request.max_output_tokens,
                    "model_id": "gpt-5.4",
                    "provider_request_id": "req_budget_1",
                    "input_tokens": 10,
                    "output_tokens": 20,
                    "total_tokens": 30,
                    "estimated_cost_usd": 1.0,
                    "stubbed": False,
                    "message": "live response",
                    "structured_output": {},
                },
            )()

    settings.provider_mode = "openai"
    settings.provider_rollout_state = "CANARY_ENABLED"
    settings.live_text_provider_id = "text.openai"
    settings.live_text_model_id = "gpt-5.4"
    settings.live_text_provider_api_key = "secret"
    settings.live_text_allowed_task_ids = "explain.v1"
    settings.live_text_budget_enforced = True
    settings.live_text_input_cost_per_1k_tokens = 0.01
    settings.live_text_output_cost_per_1k_tokens = 0.03
    settings.live_text_hard_budget_usd = 1.0
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        "app.services.provider_gateway.resolve_text_generation_adapter",
        lambda mode: _LiveAdapter(),
    )

    first_response = execute_text_generation(_request())
    assert first_response.provider_id == "text.openai"

    with pytest.raises(HTTPException) as exc_info:
        execute_text_generation(_request())

    assert exc_info.value.status_code == 503
    assert "BUDGET_EXCEEDED" in str(exc_info.value.detail)
    monkeypatch.undo()


def test_execute_text_generation_opens_circuit_after_repeated_provider_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _BrokenLiveAdapter:
        def execute(self, request: ProviderExecutionRequest) -> object:
            raise ProviderExecutionError(
                category=ProviderFailureCategory.PROVIDER_TIMEOUT,
                message="simulated timeout",
            )

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
    monkeypatch.setattr(
        "app.services.provider_gateway.resolve_text_generation_adapter",
        lambda mode: _BrokenLiveAdapter(),
    )

    with pytest.raises(HTTPException) as first_exc:
        execute_text_generation(_request())
    assert "PROVIDER_TIMEOUT" in str(first_exc.value.detail)

    with pytest.raises(HTTPException) as second_exc:
        execute_text_generation(_request())
    assert "PROVIDER_TIMEOUT" in str(second_exc.value.detail)

    with pytest.raises(HTTPException) as third_exc:
        execute_text_generation(_request())
    assert "CIRCUIT_OPEN" in str(third_exc.value.detail)


def test_execute_text_generation_routes_stub_mode_through_stub_provider() -> None:
    settings.provider_mode = "stub"

    response = execute_text_generation(
        _request(
            task_id="summarize.v1",
            caller_app="lotus-advise",
            prompt_version="foundation.summarize.v1",
            system_instructions="Summarize structured inputs conservatively.",
            output_contract_notes="Return draft summary only.",
            output_label="DRAFT",
            context_summary="Summarize proposal workflow",
            context_payload={"status": "PENDING_REVIEW"},
            source_refs=[],
        )
    )

    assert response.provider_id == "text.stub"
    assert response.provider_mode == "stub"
    assert response.adapter_kind == ProviderAdapterKind.STUB
    assert response.timeout_ms == 4000
    assert response.retry_count == 0
    assert response.max_output_tokens == 512
    assert response.stubbed is True
    structured_output = response.structured_output
    assert isinstance(structured_output, dict)
    assert structured_output["output_label"] == "DRAFT"

    settings.provider_mode = "disabled"


def test_execute_text_generation_rejects_adapter_execution_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _BrokenAdapter:
        def execute(self, request: ProviderExecutionRequest) -> object:
            raise ProviderExecutionError(
                category=ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR,
                message="simulated upstream failure",
            )

    settings.provider_mode = "stub"
    monkeypatch.setattr(
        "app.services.provider_gateway.resolve_text_generation_adapter",
        lambda mode: _BrokenAdapter(),
    )

    with pytest.raises(HTTPException) as exc_info:
        execute_text_generation(_request())

    assert exc_info.value.status_code == 503
    assert "PROVIDER_UPSTREAM_ERROR" in str(exc_info.value.detail)

    settings.provider_mode = "disabled"


def test_execute_text_generation_stamps_catalogue_identity_on_live_responses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.model_catalogue_store import reset_model_catalogue_store_cache

    reset_model_catalogue_store_cache()

    class _LiveAdapter:
        def execute(self, request: ProviderExecutionRequest) -> object:
            return type(
                "Response",
                (),
                {
                    "provider_id": "text.openai",
                    "provider_mode": "openai",
                    "adapter_kind": ProviderAdapterKind.OPENAI_LIVE,
                    "failure_category": None,
                    "timeout_ms": request.timeout_ms,
                    "retry_count": 0,
                    "max_output_tokens": request.max_output_tokens,
                    "model_id": "gpt-5.4",
                    "provider_request_id": "req_catalogue_1",
                    "input_tokens": 10,
                    "output_tokens": 20,
                    "total_tokens": 30,
                    "estimated_cost_usd": None,
                    "stubbed": False,
                    "message": "live response",
                    "structured_output": {},
                },
            )()

    monkeypatch.setattr(settings, "provider_mode", "openai")
    monkeypatch.setattr(settings, "provider_rollout_state", "CANARY_ENABLED")
    monkeypatch.setattr(settings, "live_text_provider_id", "text.openai")
    monkeypatch.setattr(settings, "live_text_model_id", "gpt-5.4")
    monkeypatch.setattr(settings, "live_text_model_version", None)
    monkeypatch.setattr(settings, "live_text_provider_api_key", "secret")
    monkeypatch.setattr(settings, "live_text_allowed_task_ids", "explain.v1")
    monkeypatch.setattr(settings, "live_text_quota_enforced", False)
    monkeypatch.setattr(settings, "live_text_budget_enforced", False)
    monkeypatch.setattr(settings, "live_text_degradation_enforced", False)
    monkeypatch.setattr(settings, "workflow_run_model_risk_inventory_json", "[]")
    monkeypatch.setattr(
        "app.services.provider_gateway.resolve_text_generation_adapter",
        lambda mode: _LiveAdapter(),
    )

    response = execute_text_generation(_request())

    # The transport only knows settings strings; the gateway stamps the
    # governed identity, including the honest unpinned posture.
    assert response.model_catalogue_entry_id == "text.openai:gpt-5.4"
    assert response.model_revision_pinned is False
    assert response.model_version == "gpt-5.4"
    reset_model_catalogue_store_cache()


def test_execute_text_generation_refuses_a_retired_catalogue_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.contracts.model_catalogue import ModelLifecycleState
    from app.services.model_catalogue import ensure_model_catalogue_seeded
    from app.services.model_catalogue_store import (
        get_model_catalogue_repository,
        reset_model_catalogue_store_cache,
    )

    reset_model_catalogue_store_cache()
    monkeypatch.setattr(settings, "provider_mode", "openai")
    monkeypatch.setattr(settings, "provider_rollout_state", "CANARY_ENABLED")
    monkeypatch.setattr(settings, "live_text_provider_id", "text.openai")
    monkeypatch.setattr(settings, "live_text_model_id", "gpt-5.4")
    monkeypatch.setattr(settings, "live_text_model_version", None)
    monkeypatch.setattr(settings, "live_text_provider_api_key", "secret")
    monkeypatch.setattr(settings, "live_text_allowed_task_ids", "explain.v1")
    monkeypatch.setattr(settings, "live_text_quota_enforced", False)
    monkeypatch.setattr(settings, "live_text_budget_enforced", False)
    monkeypatch.setattr(settings, "live_text_degradation_enforced", False)
    monkeypatch.setattr(settings, "workflow_run_model_risk_inventory_json", "[]")

    ensure_model_catalogue_seeded()
    repository = get_model_catalogue_repository()
    seeded = repository.get_entry("text.openai:gpt-5.4")
    assert seeded is not None
    repository.upsert_entry(
        seeded.model_copy(update={"lifecycle_state": ModelLifecycleState.RETIRED})
    )

    adapter_calls: list[str] = []

    def _record_adapter_resolution(mode: object) -> object:
        adapter_calls.append("resolved")
        return None

    monkeypatch.setattr(
        "app.services.provider_gateway.resolve_text_generation_adapter",
        _record_adapter_resolution,
    )

    with pytest.raises(HTTPException) as exc_info:
        execute_text_generation(_request())

    assert exc_info.value.status_code == 503
    assert "MODEL_LIFECYCLE_INELIGIBLE" in str(exc_info.value.detail)
    assert adapter_calls == [], "a lifecycle-ineligible model must be refused before the adapter"
    reset_model_catalogue_store_cache()
