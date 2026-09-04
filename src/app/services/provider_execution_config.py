"""Per-request provider execution configuration (issue #148, S2).

Production text-generation execution used to read ~10 ``settings`` attributes
at scattered points mid-request, which is why the evaluation runtime mutated
the process-wide settings singleton to run a case. This module gives the
execution path one immutable snapshot instead:

- ``resolve_provider_execution_config()`` builds a frozen config from
  ``settings`` - the production path - unless an execution-scoped override is
  installed, in which case the override IS the config.
- The evaluation runtime installs a per-case config through
  ``override_provider_execution_config`` (contextvar-scoped, like the seam
  overrides in ``provider_execution_overrides``), so a concurrent production
  request never observes an eval case's provider configuration.

The config deliberately carries only the text-generation execution surface:
mode, rollout, model identity, endpoint, credential, task allowlist, and the
execution controls (issue #151 sampling included). Enforcement thresholds
(quota/budget/degradation) remain settings-read until S3.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from app.config import settings


@dataclass(frozen=True)
class ProviderEnforcementThresholds:
    """Quota/budget/degradation enforcement posture for one execution (S3).

    Grouped rather than flattened onto the config: these are the operator's
    protection thresholds, not the model identity, and the config digest
    deliberately excludes them.
    """

    quota_enforced: bool
    default_quota_limit: int | None
    task_quota_limits: str
    caller_quota_limits: str
    tenant_quota_limits: str
    budget_enforced: bool
    soft_budget_usd: float | None
    hard_budget_usd: float | None
    degradation_enforced: bool
    degraded_failure_count_threshold: int | None
    circuit_open_failure_count_threshold: int | None
    circuit_open_seconds: int | None


@dataclass(frozen=True)
class ProviderExecutionConfig:
    provider_mode: str
    rollout_state: str
    provider_id: str | None
    model_id: str | None
    model_version: str | None
    api_base: str
    api_key: str | None
    allowed_task_ids: str
    timeout_ms: int
    retry_limit: int
    failed_attempt_cost_posture: str
    max_output_tokens: int
    temperature: float
    top_p: float | None
    seed: int | None
    enforcement: ProviderEnforcementThresholds
    routing_strategy: str = "fixed"
    fallback_provider_id: str | None = None
    fallback_model_id: str | None = None
    fallback_model_version: str | None = None
    fallback_api_base: str | None = None
    fallback_api_key: str | None = None
    # Hosting deployment identity (issue #303): participates in the catalogue
    # entry-id derivation exactly as the catalogue derives it, so a
    # deployment-scoped candidate binds, debits and audits under its own
    # governed identity. None for direct provider APIs - the settings pair
    # never sets it; only declared connection material can.
    deployment: str | None = None


_provider_execution_config_override: ContextVar[ProviderExecutionConfig | None] = ContextVar(
    "lotus_ai_provider_execution_config_override", default=None
)


@contextmanager
def override_provider_execution_config(config: ProviderExecutionConfig) -> Iterator[None]:
    token = _provider_execution_config_override.set(config)
    try:
        yield
    finally:
        _provider_execution_config_override.reset(token)


def get_provider_execution_config_override() -> ProviderExecutionConfig | None:
    return _provider_execution_config_override.get()


def resolve_provider_execution_config() -> ProviderExecutionConfig:
    override = _provider_execution_config_override.get()
    if override is not None:
        return override
    return ProviderExecutionConfig(
        provider_mode=settings.provider_mode,
        rollout_state=settings.provider_rollout_state,
        provider_id=settings.live_text_provider_id,
        model_id=settings.live_text_model_id,
        model_version=settings.live_text_model_version,
        api_base=settings.live_text_api_base,
        api_key=settings.live_text_provider_api_key,
        allowed_task_ids=settings.live_text_allowed_task_ids,
        timeout_ms=max(settings.provider_timeout_ms, 1),
        retry_limit=max(settings.provider_retry_limit, 0),
        failed_attempt_cost_posture=settings.provider_failed_attempt_cost_posture,
        max_output_tokens=max(settings.provider_max_output_tokens, 1),
        temperature=settings.live_text_temperature,
        top_p=settings.live_text_top_p,
        seed=settings.live_text_seed,
        enforcement=ProviderEnforcementThresholds(
            quota_enforced=settings.live_text_quota_enforced,
            default_quota_limit=settings.live_text_default_quota_limit,
            task_quota_limits=settings.live_text_task_quota_limits,
            caller_quota_limits=settings.live_text_caller_quota_limits,
            tenant_quota_limits=settings.live_text_tenant_quota_limits,
            budget_enforced=settings.live_text_budget_enforced,
            soft_budget_usd=settings.live_text_soft_budget_usd,
            hard_budget_usd=settings.live_text_hard_budget_usd,
            degradation_enforced=settings.live_text_degradation_enforced,
            degraded_failure_count_threshold=settings.live_text_degraded_failure_count_threshold,
            circuit_open_failure_count_threshold=(
                settings.live_text_circuit_open_failure_count_threshold
            ),
            circuit_open_seconds=settings.live_text_circuit_open_seconds,
        ),
        routing_strategy=settings.routing_strategy,
        fallback_provider_id=settings.live_text_fallback_provider_id,
        fallback_model_id=settings.live_text_fallback_model_id,
        fallback_model_version=settings.live_text_fallback_model_version,
        fallback_api_base=settings.live_text_fallback_api_base,
        fallback_api_key=settings.live_text_fallback_api_key,
    )


def fallback_identity_configured(config: ProviderExecutionConfig) -> bool:
    """True when the complete alternate identity is present.

    Provider, model, and endpoint are the required triple; the revision and
    the credential are optional exactly as they are for the primary identity.
    """

    return bool(
        config.fallback_provider_id and config.fallback_model_id and config.fallback_api_base
    )


def fallback_configuration_findings(config: ProviderExecutionConfig) -> list[str]:
    """Bounded misconfiguration statements for the ordered-fallback surface.

    All-or-nothing: a partially supplied alternate identity is a finding even
    under the fixed strategy, so the misconfiguration surfaces before an
    operator flips the strategy and discovers the alternate never existed.
    """

    findings: list[str] = []
    required = {
        "LOTUS_AI_LIVE_TEXT_FALLBACK_PROVIDER_ID": config.fallback_provider_id,
        "LOTUS_AI_LIVE_TEXT_FALLBACK_MODEL_ID": config.fallback_model_id,
        "LOTUS_AI_LIVE_TEXT_FALLBACK_API_BASE": config.fallback_api_base,
    }
    supplied = [name for name, value in required.items() if value]
    missing = [name for name, value in required.items() if not value]
    if supplied and missing:
        findings.append(
            "provider routing: the fallback identity is partially configured "
            f"(missing {', '.join(sorted(missing))}); supply the complete identity or none of it"
        )
    if config.routing_strategy == "ordered_fallback":
        if not supplied:
            findings.append(
                "provider routing: routing_strategy=ordered_fallback requires a complete "
                "fallback identity (provider, model, endpoint) and none is configured"
            )
        elif not missing and config.fallback_provider_id == config.provider_id:
            findings.append(
                "provider routing: the fallback provider identity equals the primary provider "
                "identity, which collapses per-candidate breaker bookkeeping into one key; "
                "configure a distinct alternate provider"
            )
    elif config.routing_strategy != "fixed":
        findings.append(
            f"provider routing: unknown routing_strategy '{config.routing_strategy}' "
            "(supported: fixed, ordered_fallback)"
        )
    return findings


def derive_fallback_execution_config(
    config: ProviderExecutionConfig,
) -> ProviderExecutionConfig | None:
    """The alternate candidate's execution config, or None when not configured.

    Identity and endpoint swap to the fallback quintet; sampling, timeouts,
    retry budget, task allowlist, and enforcement thresholds are shared - the
    alternate runs under the same protection posture as the primary. The
    derived config is a fixed-strategy config with no fallback of its own, so
    a fallback can never chain.
    """

    fallback_api_base = config.fallback_api_base
    if not fallback_identity_configured(config) or fallback_api_base is None:
        return None
    return ProviderExecutionConfig(
        provider_mode=config.provider_mode,
        rollout_state=config.rollout_state,
        provider_id=config.fallback_provider_id,
        model_id=config.fallback_model_id,
        model_version=config.fallback_model_version,
        api_base=fallback_api_base,
        api_key=config.fallback_api_key,
        allowed_task_ids=config.allowed_task_ids,
        timeout_ms=config.timeout_ms,
        retry_limit=config.retry_limit,
        failed_attempt_cost_posture=config.failed_attempt_cost_posture,
        max_output_tokens=config.max_output_tokens,
        temperature=config.temperature,
        top_p=config.top_p,
        seed=config.seed,
        enforcement=config.enforcement,
        routing_strategy="fixed",
    )


def compute_provider_config_sha256(
    *,
    provider_mode: str,
    provider_id: str | None,
    model_id: str | None,
    model_version: str | None,
    temperature: float,
    top_p: float | None,
    seed: int | None,
    max_output_tokens: int,
) -> str:
    """Digest of the resolved execution configuration (issue #151).

    Covers the model identity and the sampling configuration that shaped the
    call, so two audit rows with the same digest were produced under the same
    execution configuration - including deterministic stub executions. The
    credential is deliberately excluded.
    """

    canonical = json.dumps(
        {
            "provider_mode": provider_mode,
            "provider_id": provider_id,
            "model_id": model_id,
            "model_version": model_version,
            "temperature": temperature,
            "top_p": top_p,
            "seed": seed,
            "max_output_tokens": max_output_tokens,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
