from __future__ import annotations

from typing import Literal

from pydantic import PrivateAttr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Promoted-profile hardening (issue #153 S2): protection defaults applied only
# to keys the operator did NOT set explicitly - explicit choices always win.
# Economic limits (quota numbers, budget dollars) are never invented here;
# promoted enables the enforcement flags and startup readiness blocks until
# the operator supplies the limits.
PROMOTED_PROFILE_DEFAULTS: dict[str, object] = {
    "provider_retry_limit": 2,
    "provider_failed_attempt_cost_posture": "conservative",
    "live_text_quota_enforced": True,
    "live_text_budget_enforced": True,
    "live_text_degradation_enforced": True,
    "live_text_degraded_failure_count_threshold": 3,
    "live_text_circuit_open_failure_count_threshold": 5,
    "live_text_circuit_open_seconds": 60,
    "provider_operations_store_mode": "sqlalchemy",
    "workflow_pack_admission_store_mode": "sqlalchemy",
    "readiness_probe_policy": "degrade",
    "startup_readiness_policy": "enforce",
}

# The promoted defaults that are PROTECTIONS (issue #233): for each of these,
# any explicit divergence from the promoted value is a weakening - the
# booleans only weaken to False, the store modes to per-process memory, the
# policies to non-blocking postures. Explicit override still wins, but it must
# be loud: a startup finding names every protection an operator overrode.
# The tuning values (retry limit, breaker thresholds/window) are deliberately
# not here - a different threshold is a choice, not a disabled protection.
PROMOTED_PROTECTION_FIELDS: frozenset[str] = frozenset(
    {
        "live_text_quota_enforced",
        "live_text_budget_enforced",
        "live_text_degradation_enforced",
        "provider_operations_store_mode",
        "workflow_pack_admission_store_mode",
        "readiness_probe_policy",
        "startup_readiness_policy",
        # Billing-truth posture (issue #232): actual_only can only understate
        # spend against the real bill, so weakening it in promoted must be loud.
        "provider_failed_attempt_cost_posture",
    }
)


class Settings(BaseSettings):
    # Bounded on purpose (issue #230): every profile gate in the runtime
    # compares against these two values, so a typo ("promted") would silently
    # get the lenient local tier everywhere. Unknown values refuse at
    # construction instead.
    runtime_profile: Literal["local", "promoted"] = "local"
    service_name: str = "lotus-ai"
    service_version: str = "0.1.0"
    delivery_phase: str = "foundation"
    provider_mode: str = "disabled"
    provider_rollout_state: str = "STUB_DEFAULT"
    live_text_provider_id: str | None = None
    live_text_model_id: str | None = None
    live_text_model_version: str | None = None
    live_text_provider_api_key: str | None = None
    routing_strategy: str = "fixed"
    live_text_fallback_provider_id: str | None = None
    live_text_fallback_model_id: str | None = None
    live_text_fallback_model_version: str | None = None
    live_text_fallback_api_base: str | None = None
    live_text_fallback_api_key: str | None = None
    live_embedding_provider_id: str | None = None
    live_embedding_model_id: str | None = None
    live_embedding_provider_api_key: str | None = None
    secret_source_mode: str = "local_or_unspecified"
    live_text_allowed_task_ids: str = ""
    live_text_api_base: str = "https://api.openai.com/v1"
    live_text_local_probe_timeout_ms: int = 1500
    live_text_local_probe_cache_seconds: int = 15
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
    provider_failed_attempt_cost_posture: str = "conservative"
    provider_max_output_tokens: int = 512
    live_text_temperature: float = 0.0
    live_text_top_p: float | None = None
    live_text_seed: int | None = None
    redaction_mode: str = "enforce"
    tracing_enabled: bool = False
    tracing_otlp_endpoint: str | None = None
    retrieval_mode: str = "disabled"
    embedding_provider_mode: str = "disabled"
    safety_mode: str = "documented_only"
    audit_store_mode: str = "memory"
    prompt_store_mode: str = "memory"
    retrieval_store_mode: str = "memory"
    access_control_store_mode: str = "memory"
    workflow_pack_registry_store_mode: str = "memory"
    provider_operations_store_mode: str = "memory"
    workflow_pack_admission_store_mode: str = "memory"
    workflow_pack_admission_lease_ttl_seconds: int = 3600
    provider_retention_confirmation_store_mode: str = "memory"
    async_runtime_store_mode: str = "memory"
    workflow_pack_run_store_mode: str = "memory"
    workflow_pack_task_flow_store_mode: str = "memory"
    workflow_pack_queue_event_store_mode: str = "memory"
    model_catalogue_store_mode: str = "memory"
    kill_switch_store_mode: str = "memory"
    rate_card_store_mode: str = "memory"
    log_level: str = "INFO"
    workflow_run_attestation_key_id: str | None = None
    workflow_run_attestation_rotation_epoch: int | None = None
    workflow_run_attestation_private_key_base64url: str | None = None
    workflow_run_attestation_key_not_before_utc: str | None = None
    workflow_run_attestation_key_not_after_utc: str | None = None
    workflow_run_attestation_rotated_public_keys_json: str = "[]"
    workflow_run_model_risk_inventory_json: str = "[]"
    workflow_run_attestation_ttl_seconds: int = 300
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
    deployment_split_stage: str = "unified"
    startup_readiness_policy: str = "warn"
    readiness_probe_policy: str = "observe"
    local_header_caller_identity_enabled: bool = False
    caller_trust_mode: str = "header"
    caller_jwt_issuer: str | None = None
    caller_jwt_audience: str | None = None
    caller_jwt_public_keys: str = ""
    # Maximum accepted credential validity window (exp - iat), issue #233: a
    # leaked token must not replay for an issuer-chosen unbounded lifetime.
    caller_jwt_max_lifetime_seconds: int = 3600
    http_allowed_hosts: str = "*"
    http_cors_allowed_origins: str = (
        "http://localhost,http://localhost:3000,http://127.0.0.1,http://127.0.0.1:3000"
    )
    http_cors_allowed_methods: str = "GET,POST,PUT,PATCH,DELETE,OPTIONS"
    http_cors_allowed_headers: str = (
        "Authorization,Content-Type,X-Correlation-Id,X-Caller-App,X-Tenant-Id"
    )
    http_cors_allow_credentials: bool = False
    http_secure_headers_enabled: bool = True
    http_hsts_enabled: bool = False
    http_hsts_max_age_seconds: int = 31536000
    http_max_request_body_bytes: int = 1048576
    database_url: str | None = None

    model_config = SettingsConfigDict(env_prefix="LOTUS_AI_", extra="ignore")

    _promoted_protection_overrides: list[str] = PrivateAttr(default_factory=list)

    @property
    def promoted_protection_overrides(self) -> list[str]:
        """Protections an operator explicitly weakened below the promoted default.

        Captured at construction, where ``model_fields_set`` is authoritative
        about what the operator actually set (issue #233): a pre-existing
        explicit weakening must not silently keep weaker posture. Empty
        outside the promoted profile.
        """

        return list(self._promoted_protection_overrides)

    @model_validator(mode="after")
    def _apply_runtime_profile_defaults(self) -> "Settings":
        if self.runtime_profile != "promoted":
            return self
        overrides: list[str] = []
        for field_name, promoted_value in PROMOTED_PROFILE_DEFAULTS.items():
            if field_name not in self.model_fields_set:
                setattr(self, field_name, promoted_value)
            elif (
                field_name in PROMOTED_PROTECTION_FIELDS
                and getattr(self, field_name) != promoted_value
            ):
                overrides.append(
                    f"promoted override: {field_name} is explicitly weakened to "
                    f"{getattr(self, field_name)!r} (promoted default {promoted_value!r}); "
                    "this protection is operator-overridden"
                )
        self._promoted_protection_overrides = overrides
        return self


settings = Settings()
