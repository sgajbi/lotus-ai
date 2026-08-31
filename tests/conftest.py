from __future__ import annotations

from collections.abc import Generator

import pytest

from app.config import settings
from app.services.audit_store import reset_audit_store_cache
from app.services.caller_policy_store import reset_caller_policy_store_cache
from app.services.async_delivery_queue import reset_async_delivery_queue_cache
from app.services.async_runtime_store import reset_async_runtime_store_cache
from app.services.artifact_store import reset_artifact_store_cache
from app.services.evaluation_runtime_store import reset_evaluation_runtime_store_cache
from app.services.local_openai_compatible_endpoint_probe import (
    reset_local_openai_compatible_endpoint_probe_cache,
)
from app.services.prompt_store import reset_prompt_store_cache
from app.services.provider_budget_policy import reset_provider_budget_state
from app.services.provider_degradation_state import reset_provider_degradation_state
from app.services.provider_operations_store import reset_provider_operations_store_cache
from app.services.kill_switch_store import reset_kill_switch_store_cache
from app.services.model_catalogue_store import reset_model_catalogue_store_cache
from app.services.rate_card_store import reset_rate_card_store_cache
from app.provider_retention_confirmations.store import (
    reset_provider_retention_confirmation_store_cache,
)
from app.services.provider_quota_policy import reset_provider_quota_counters
from app.services.retrieval_store import reset_retrieval_repository
from app.services.workflow_pack_registry import reset_workflow_pack_registry_state
from app.services.workflow_pack_queue_admission import reset_workflow_pack_queue_admission_state
from app.services.workflow_pack_queue_event_store import reset_workflow_pack_queue_event_store_cache
from app.services.workflow_pack_run_store import reset_workflow_pack_run_store_cache
from app.services.workflow_pack_task_flow_store import reset_workflow_pack_task_flow_store_cache
from app.workflow_pack_execution_idempotency.store import (
    reset_workflow_pack_execution_idempotency_store_cache,
)


@pytest.fixture(autouse=True)
def reset_runtime_settings() -> Generator[None, None, None]:
    original_values = {
        "provider_mode": settings.provider_mode,
        "provider_rollout_state": settings.provider_rollout_state,
        "live_text_provider_id": settings.live_text_provider_id,
        "live_text_model_id": settings.live_text_model_id,
        "live_text_provider_api_key": settings.live_text_provider_api_key,
        "live_embedding_provider_id": settings.live_embedding_provider_id,
        "live_embedding_model_id": settings.live_embedding_model_id,
        "live_embedding_provider_api_key": settings.live_embedding_provider_api_key,
        "live_text_allowed_task_ids": settings.live_text_allowed_task_ids,
        "live_text_api_base": settings.live_text_api_base,
        "live_text_local_probe_timeout_ms": settings.live_text_local_probe_timeout_ms,
        "live_text_local_probe_cache_seconds": settings.live_text_local_probe_cache_seconds,
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
        "retrieval_mode": settings.retrieval_mode,
        "embedding_provider_mode": settings.embedding_provider_mode,
        "safety_mode": settings.safety_mode,
        "redaction_mode": settings.redaction_mode,
        "tracing_enabled": settings.tracing_enabled,
        "tracing_otlp_endpoint": settings.tracing_otlp_endpoint,
        "audit_store_mode": settings.audit_store_mode,
        "prompt_store_mode": settings.prompt_store_mode,
        "retrieval_store_mode": settings.retrieval_store_mode,
        "access_control_store_mode": settings.access_control_store_mode,
        "workflow_pack_registry_store_mode": settings.workflow_pack_registry_store_mode,
        "provider_operations_store_mode": settings.provider_operations_store_mode,
        "runtime_profile": settings.runtime_profile,
        "provider_retry_limit": settings.provider_retry_limit,
        "live_text_hard_budget_usd": settings.live_text_hard_budget_usd,
        "live_text_default_quota_limit": settings.live_text_default_quota_limit,
        "live_text_quota_enforced": settings.live_text_quota_enforced,
        "live_text_budget_enforced": settings.live_text_budget_enforced,
        "live_text_degradation_enforced": settings.live_text_degradation_enforced,
        "provider_retention_confirmation_store_mode": (
            settings.provider_retention_confirmation_store_mode
        ),
        "async_runtime_store_mode": settings.async_runtime_store_mode,
        "workflow_pack_run_store_mode": settings.workflow_pack_run_store_mode,
        "workflow_pack_task_flow_store_mode": settings.workflow_pack_task_flow_store_mode,
        "workflow_pack_queue_event_store_mode": settings.workflow_pack_queue_event_store_mode,
        "async_cutover_state": settings.async_cutover_state,
        "async_queue_backend_mode": settings.async_queue_backend_mode,
        "async_queue_redis_url": settings.async_queue_redis_url,
        "async_queue_name": settings.async_queue_name,
        "async_worker_id": settings.async_worker_id,
        "async_worker_queue_poll_seconds": settings.async_worker_queue_poll_seconds,
        "async_worker_drain_enabled": settings.async_worker_drain_enabled,
        "evaluation_runtime_store_mode": settings.evaluation_runtime_store_mode,
        "artifact_store_mode": settings.artifact_store_mode,
        "artifact_object_store_mode": settings.artifact_object_store_mode,
        "artifact_object_store_root": settings.artifact_object_store_root,
        "startup_readiness_policy": settings.startup_readiness_policy,
        "readiness_probe_policy": settings.readiness_probe_policy,
        "local_header_caller_identity_enabled": settings.local_header_caller_identity_enabled,
        "http_allowed_hosts": settings.http_allowed_hosts,
        "http_cors_allowed_origins": settings.http_cors_allowed_origins,
        "http_cors_allowed_methods": settings.http_cors_allowed_methods,
        "http_cors_allowed_headers": settings.http_cors_allowed_headers,
        "http_cors_allow_credentials": settings.http_cors_allow_credentials,
        "http_secure_headers_enabled": settings.http_secure_headers_enabled,
        "http_hsts_enabled": settings.http_hsts_enabled,
        "http_hsts_max_age_seconds": settings.http_hsts_max_age_seconds,
        "http_max_request_body_bytes": settings.http_max_request_body_bytes,
        "kill_switch_store_mode": settings.kill_switch_store_mode,
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
        reset_caller_policy_store_cache()
        reset_provider_budget_state()
        reset_provider_degradation_state()
        reset_provider_quota_counters()
        reset_provider_operations_store_cache()
        reset_kill_switch_store_cache()
        reset_model_catalogue_store_cache()
        reset_rate_card_store_cache()
        reset_provider_retention_confirmation_store_cache()
        reset_local_openai_compatible_endpoint_probe_cache()
        reset_async_delivery_queue_cache()
        reset_async_runtime_store_cache()
        reset_evaluation_runtime_store_cache()
        reset_artifact_store_cache()
        reset_workflow_pack_registry_state()
        reset_workflow_pack_queue_admission_state()
        reset_workflow_pack_queue_event_store_cache()
        reset_workflow_pack_run_store_cache()
        reset_workflow_pack_task_flow_store_cache()
        reset_workflow_pack_execution_idempotency_store_cache()
