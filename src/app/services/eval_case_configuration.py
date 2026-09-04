"""Hermetic per-case execution configuration for runtime evals.

Split from eval_runtime_execution when the module budget fired (issue
#312 S3): this family interprets a fixture case's input payload into
scoped configuration overrides - provider, prompt, probe, rate-card and
store state - applied for exactly one case and unwound afterwards. It
carries no run orchestration.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from contextlib import ExitStack
from dataclasses import replace
from typing import Iterator, cast


from app.config import settings
from app.contracts.providers import ProviderFailureCategory, ProviderQuotaScope
from app.services.local_openai_compatible_endpoint_probe import LocalOpenAICompatibleEndpointStatus
from app.services.prompt_store import reset_prompt_store_cache
from app.contracts.rate_cards import RateCard, RateCardScopeKind
from app.services.provider_usage_accounting import save_rate_card
from app.services.rate_card_store import reset_rate_card_store_cache
from app.services.runtime_mode_config import (
    override_runtime_mode_config,
    resolve_runtime_mode_config,
)
from app.services.provider_execution_config import (
    override_provider_execution_config,
    resolve_provider_execution_config,
)
from app.services.provider_execution_overrides import (
    hermetic_provider_execution,
    override_local_probe_status,
    override_text_transport_post,
)
from app.services.provider_degradation_state import (
    record_provider_failure,
    reset_provider_degradation_state,
)
from app.services.provider_operations_store import (
    override_provider_operations_store_mode,
    resolved_provider_operations_store_mode,
    get_provider_operations_store,
    reset_provider_operations_store_cache,
)
from app.services.provider_quota_policy import reset_provider_quota_counters
from app.services.retrieval_store import get_retrieval_repository, reset_retrieval_repository


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


# A self-describing non-credential reference (issue #148): it satisfies the
# key-presence validation for hermetic openai-mode cases, and because every
# case runs under hermetic_provider_execution() it can never reach a real
# network call. It is not a secret and must never be shaped like one.
EVAL_HERMETIC_CREDENTIAL_REF = "credential-ref:eval-hermetic"


def _raise_provider_execution_error(*, category: ProviderFailureCategory, message: str) -> Any:
    from app.providers.base import ProviderExecutionError

    raise ProviderExecutionError(category=category, message=message)


@contextmanager
def _apply_case_configuration(input_payload: dict[str, object]) -> Iterator[None]:
    try:
        with ExitStack() as stack:
            # Every case runs hermetically: the live network seams fail
            # closed unless the case installs an explicit override below.
            stack.enter_context(hermetic_provider_execution())
            reset_prompt_store_cache()
            reset_retrieval_repository()
            reset_provider_operations_store_cache()
            reset_provider_quota_counters()
            reset_provider_degradation_state()
            reset_rate_card_store_cache()
            runtime_modes = resolve_runtime_mode_config()
            if "retrieval_mode" in input_payload:
                runtime_modes = replace(
                    runtime_modes, retrieval_mode=str(input_payload["retrieval_mode"])
                )
            if "safety_mode" in input_payload:
                runtime_modes = replace(
                    runtime_modes, safety_mode=str(input_payload["safety_mode"])
                )
            if "embedding_provider_mode" in input_payload:
                runtime_modes = replace(
                    runtime_modes,
                    embedding_provider_mode=str(input_payload["embedding_provider_mode"]),
                )
            if "live_embedding_provider_id" in input_payload:
                runtime_modes = replace(
                    runtime_modes,
                    embedding_provider_id=(
                        str(input_payload["live_embedding_provider_id"])
                        if input_payload["live_embedding_provider_id"] is not None
                        else None
                    ),
                )
            if "live_embedding_model_id" in input_payload:
                runtime_modes = replace(
                    runtime_modes,
                    embedding_model_id=(
                        str(input_payload["live_embedding_model_id"])
                        if input_payload["live_embedding_model_id"] is not None
                        else None
                    ),
                )
            if "live_embedding_provider_api_key" in input_payload:
                runtime_modes = replace(
                    runtime_modes,
                    embedding_api_key=(
                        str(input_payload["live_embedding_provider_api_key"])
                        if input_payload["live_embedding_provider_api_key"] is not None
                        else None
                    ),
                )
            stack.enter_context(override_runtime_mode_config(runtime_modes))
            indexed_sources = input_payload.get("index_sources", [])
            if isinstance(indexed_sources, list):
                repository = get_retrieval_repository()
                for source_id in indexed_sources:
                    if isinstance(source_id, str):
                        repository.set_source_index_status(
                            source_id=source_id,
                            index_status="INDEXED",
                        )
            case_mode = str(
                input_payload.get(
                    "provider_mode",
                    input_payload.get("configured_mode", settings.provider_mode),
                )
            )
            case_rollout = str(input_payload.get("rollout_state", settings.provider_rollout_state))
            if (
                input_payload.get("provider_operations_store_mode") == "sqlalchemy"
                and settings.database_url
            ):
                stack.enter_context(override_provider_operations_store_mode("sqlalchemy"))
                reset_provider_operations_store_cache()
            live_execution_signals = any(
                key in input_payload
                for key in (
                    "request_limit",
                    "hard_budget_usd",
                    "tracked_spend_usd",
                    "recorded_spend_usd",
                    "degraded_failure_count_threshold",
                    "circuit_open_seconds",
                )
            )
            case_config = replace(
                resolve_provider_execution_config(),
                provider_mode=case_mode,
                rollout_state=case_rollout,
            )
            if case_mode == "openai" and (
                input_payload.get("rollout_state") in {"CANARY_ENABLED", "ROLLED_OUT"}
                or live_execution_signals
            ):
                case_config = replace(
                    case_config,
                    rollout_state=(
                        case_rollout if "rollout_state" in input_payload else "CANARY_ENABLED"
                    ),
                    provider_id="text.openai",
                    model_id="gpt-5.4",
                    api_key=EVAL_HERMETIC_CREDENTIAL_REF,
                    allowed_task_ids=str(input_payload.get("task_id", "")),
                )
            if case_mode == "local_openai_compatible":
                case_config = replace(
                    case_config,
                    rollout_state=(
                        case_rollout if "rollout_state" in input_payload else "CANARY_ENABLED"
                    ),
                    provider_id="text.local",
                    model_id=str(input_payload.get("live_text_model_id", "qwen3:8b")),
                    api_base=str(input_payload.get("live_text_api_base", "http://ollama:11434/v1")),
                    api_key=(
                        str(input_payload["live_text_provider_api_key"])
                        if input_payload.get("live_text_provider_api_key") is not None
                        else None
                    ),
                    allowed_task_ids=str(input_payload.get("task_id", "")),
                )
            enforcement = case_config.enforcement
            if "request_limit" in input_payload and input_payload.get("quota_scope") == "task":
                enforcement = replace(
                    enforcement,
                    quota_enforced=True,
                    task_quota_limits=(
                        f"{input_payload['task_id']}="
                        f"{int(cast(int | str, input_payload['request_limit']))}"
                    ),
                )
            if "hard_budget_usd" in input_payload:
                enforcement = replace(
                    enforcement,
                    budget_enforced=True,
                    hard_budget_usd=float(
                        cast(int | float | str, input_payload["hard_budget_usd"])
                    ),
                    soft_budget_usd=float(
                        cast(
                            int | float | str,
                            input_payload.get(
                                "recorded_spend_usd", input_payload.get("tracked_spend_usd", 0.5)
                            ),
                        )
                    ),
                )
            if "degraded_failure_count_threshold" in input_payload:
                enforcement = replace(
                    enforcement,
                    degradation_enforced=True,
                    degraded_failure_count_threshold=int(
                        cast(int | str, input_payload["degraded_failure_count_threshold"])
                    ),
                )
            if "circuit_open_failure_count_threshold" in input_payload:
                enforcement = replace(
                    enforcement,
                    circuit_open_failure_count_threshold=int(
                        cast(int | str, input_payload["circuit_open_failure_count_threshold"])
                    ),
                )
            if "circuit_open_seconds" in input_payload:
                enforcement = replace(
                    enforcement,
                    circuit_open_seconds=int(
                        cast(int | str, input_payload["circuit_open_seconds"])
                    ),
                )
                if "degraded_failure_count_threshold" not in input_payload:
                    # A circuit-posture case without explicit thresholds trips
                    # the breaker on the single recorded failure below.
                    enforcement = replace(
                        enforcement,
                        degradation_enforced=True,
                        degraded_failure_count_threshold=1,
                        circuit_open_failure_count_threshold=1,
                    )
            elif any(
                key in input_payload
                for key in (
                    "degraded_failure_count_threshold",
                    "circuit_open_failure_count_threshold",
                )
            ):
                enforcement = replace(enforcement, circuit_open_seconds=60)
            case_config = replace(case_config, enforcement=enforcement)
            stack.enter_context(override_provider_execution_config(case_config))
            if case_mode == "local_openai_compatible":
                local_probe_status = input_payload.get("local_probe_status")
                if isinstance(local_probe_status, dict):
                    stack.enter_context(
                        override_local_probe_status(
                            LocalOpenAICompatibleEndpointStatus(
                                endpoint_reachable=bool(
                                    local_probe_status.get("endpoint_reachable", False)
                                ),
                                model_available=bool(
                                    local_probe_status.get("model_available", False)
                                ),
                                configured_model_id=case_config.model_id,
                                blocking_reason=cast(
                                    str | None, local_probe_status.get("blocking_reason")
                                ),
                            )
                        )
                    )
                local_provider_response = input_payload.get("local_provider_response")
                if isinstance(local_provider_response, dict):
                    stack.enter_context(
                        override_text_transport_post(lambda **_: local_provider_response)
                    )
                local_provider_error = input_payload.get("local_provider_error")
                if isinstance(local_provider_error, dict):
                    failure_category = ProviderFailureCategory(
                        str(local_provider_error["failure_category"])
                    )
                    stack.enter_context(
                        override_text_transport_post(
                            lambda **_: _raise_provider_execution_error(
                                category=failure_category,
                                message=str(local_provider_error["message"]),
                            )
                        )
                    )
            if "request_limit" in input_payload and input_payload.get("quota_scope") == "task":
                get_provider_operations_store().increment_quota_state(
                    scope=ProviderQuotaScope.TASK,
                    scope_key=str(input_payload["task_id"]),
                    amount=int(cast(int | str, input_payload["request_limit"])),
                    updated_at=_utcnow_iso(),
                )
            if "hard_budget_usd" in input_payload:
                # The card is fixture data (issue #178 S3): budget cases
                # declare their rates in the fixture payload.
                fixture_rates = cast(dict[str, object], input_payload["rate_card"])
                seeded_at = _utcnow_iso()
                save_rate_card(
                    RateCard(
                        card_id="eval-hermetic-live-text",
                        scope_kind=RateCardScopeKind.DEFAULT_LIVE_TEXT,
                        currency="USD",
                        # monetary-float-ok markers: rate-card contract rates
                        # are float-typed by design (#178 S1).
                        input_cost_per_1k_tokens=float(  # monetary-float-ok: rate-card contract field is float-typed
                            cast(int | float | str, fixture_rates["input_cost_per_1k_tokens"])
                        ),
                        output_cost_per_1k_tokens=float(  # monetary-float-ok: rate-card contract field is float-typed
                            cast(int | float | str, fixture_rates["output_cost_per_1k_tokens"])
                        ),
                        effective_from_utc=None,
                        effective_to_utc=None,
                        created_at=seeded_at,
                        last_updated_at=seeded_at,
                    )
                )
                tracked_spend = float(
                    cast(
                        int | float | str,
                        input_payload.get(
                            "tracked_spend_usd", input_payload.get("recorded_spend_usd", 0.0)
                        ),
                    )
                )
                if tracked_spend > 0:
                    get_provider_operations_store().add_budget_spend(
                        budget_key="live_text_generation",
                        amount_usd=tracked_spend,
                        updated_at=_utcnow_iso(),
                    )
                    if resolved_provider_operations_store_mode() == "sqlalchemy":
                        reset_provider_operations_store_cache()
            if "degraded_failure_count_threshold" in input_payload:
                failure_count = int(
                    cast(int | str, input_payload["degraded_failure_count_threshold"])
                )
                for _ in range(failure_count):
                    record_provider_failure(ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR)
                if resolved_provider_operations_store_mode() == "sqlalchemy":
                    reset_provider_operations_store_cache()
            elif "circuit_open_seconds" in input_payload:
                record_provider_failure(ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR)
                if resolved_provider_operations_store_mode() == "sqlalchemy":
                    reset_provider_operations_store_cache()
            yield
    finally:
        reset_retrieval_repository()
        reset_prompt_store_cache()
        reset_provider_operations_store_cache()
        reset_provider_quota_counters()
        reset_provider_degradation_state()
        reset_rate_card_store_cache()
