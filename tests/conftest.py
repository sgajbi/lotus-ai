from __future__ import annotations

from collections.abc import Generator

import pytest

from app.config import settings
from app.services.audit_store import reset_audit_store_cache
from app.services.async_runtime_store import reset_async_runtime_store_cache
from app.services.evaluation_runtime_store import reset_evaluation_runtime_store_cache
from app.services.prompt_store import reset_prompt_store_cache
from app.services.provider_budget_policy import reset_provider_budget_state
from app.services.provider_degradation_state import reset_provider_degradation_state
from app.services.provider_operations_store import reset_provider_operations_store_cache
from app.services.provider_quota_policy import reset_provider_quota_counters
from app.services.retrieval_store import reset_retrieval_repository


@pytest.fixture(autouse=True)
def reset_runtime_settings() -> Generator[None, None, None]:
    original_values = {
        "provider_mode": settings.provider_mode,
        "provider_rollout_state": settings.provider_rollout_state,
        "live_text_provider_id": settings.live_text_provider_id,
        "live_text_model_id": settings.live_text_model_id,
        "live_text_provider_api_key": settings.live_text_provider_api_key,
        "live_text_allowed_task_ids": settings.live_text_allowed_task_ids,
        "live_text_api_base": settings.live_text_api_base,
        "live_text_input_cost_per_1k_tokens": settings.live_text_input_cost_per_1k_tokens,
        "live_text_output_cost_per_1k_tokens": settings.live_text_output_cost_per_1k_tokens,
        "live_text_quota_enforced": settings.live_text_quota_enforced,
        "live_text_default_quota_limit": settings.live_text_default_quota_limit,
        "live_text_task_quota_limits": settings.live_text_task_quota_limits,
        "live_text_caller_quota_limits": settings.live_text_caller_quota_limits,
        "live_text_tenant_quota_limits": settings.live_text_tenant_quota_limits,
        "live_text_budget_enforced": settings.live_text_budget_enforced,
        "live_text_soft_budget_usd": settings.live_text_soft_budget_usd,
        "live_text_hard_budget_usd": settings.live_text_hard_budget_usd,
        "live_text_degradation_enforced": settings.live_text_degradation_enforced,
        "live_text_degraded_failure_count_threshold": settings.live_text_degraded_failure_count_threshold,
        "live_text_circuit_open_failure_count_threshold": settings.live_text_circuit_open_failure_count_threshold,
        "live_text_circuit_open_seconds": settings.live_text_circuit_open_seconds,
        "embedding_provider_mode": settings.embedding_provider_mode,
        "audit_store_mode": settings.audit_store_mode,
        "prompt_store_mode": settings.prompt_store_mode,
        "retrieval_store_mode": settings.retrieval_store_mode,
        "provider_operations_store_mode": settings.provider_operations_store_mode,
        "async_runtime_store_mode": settings.async_runtime_store_mode,
        "evaluation_runtime_store_mode": settings.evaluation_runtime_store_mode,
        "startup_readiness_policy": settings.startup_readiness_policy,
        "readiness_probe_policy": settings.readiness_probe_policy,
        "database_url": settings.database_url,
    }
    try:
        yield
    finally:
        for key, value in original_values.items():
            setattr(settings, key, value)
        reset_audit_store_cache()
        reset_prompt_store_cache()
        reset_retrieval_repository()
        reset_provider_budget_state()
        reset_provider_degradation_state()
        reset_provider_quota_counters()
        reset_provider_operations_store_cache()
        reset_async_runtime_store_cache()
        reset_evaluation_runtime_store_cache()
