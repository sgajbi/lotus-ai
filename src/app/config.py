from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = "lotus-ai"
    service_version: str = "0.1.0"
    delivery_phase: str = "foundation"
    provider_mode: str = "disabled"
    provider_rollout_state: str = "STUB_DEFAULT"
    live_text_provider_id: str | None = None
    live_text_model_id: str | None = None
    live_text_provider_api_key: str | None = None
    live_text_allowed_task_ids: str = ""
    live_text_api_base: str = "https://api.openai.com/v1"
    live_text_input_cost_per_1k_tokens: float | None = None
    live_text_output_cost_per_1k_tokens: float | None = None
    live_text_quota_enforced: bool = False
    live_text_default_quota_limit: int | None = None
    live_text_task_quota_limits: str = ""
    live_text_caller_quota_limits: str = ""
    live_text_tenant_quota_limits: str = ""
    live_text_budget_enforced: bool = False
    live_text_soft_budget_usd: float | None = None
    live_text_hard_budget_usd: float | None = None
    live_text_degradation_enforced: bool = False
    live_text_degraded_failure_count_threshold: int | None = None
    live_text_circuit_open_failure_count_threshold: int | None = None
    live_text_circuit_open_seconds: int | None = None
    provider_timeout_ms: int = 4000
    provider_retry_limit: int = 0
    provider_max_output_tokens: int = 512
    retrieval_mode: str = "disabled"
    embedding_provider_mode: str = "disabled"
    safety_mode: str = "documented_only"
    audit_store_mode: str = "memory"
    prompt_store_mode: str = "memory"
    retrieval_store_mode: str = "memory"
    access_control_store_mode: str = "memory"
    provider_operations_store_mode: str = "memory"
    async_runtime_store_mode: str = "memory"
    async_cutover_state: str = "in_process_only"
    async_queue_backend_mode: str = "none"
    async_queue_redis_url: str | None = None
    async_queue_name: str = "lotus-ai:async:jobs"
    async_worker_id: str = "lotus-ai-worker-1"
    async_worker_queue_poll_seconds: int = 5
    async_worker_drain_enabled: bool = False
    evaluation_runtime_store_mode: str = "memory"
    artifact_store_mode: str = "memory"
    artifact_object_store_mode: str = "memory"
    artifact_object_store_root: str | None = None
    startup_readiness_policy: str = "warn"
    readiness_probe_policy: str = "observe"
    database_url: str | None = None

    model_config = SettingsConfigDict(env_prefix="LOTUS_AI_", extra="ignore")


settings = Settings()
