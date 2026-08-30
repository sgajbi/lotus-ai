"""Provider-call metrics (issue #152, slice 2).

The first AI-specific metrics lotus-ai emits: every provider attempt counts
toward `lotus_ai_provider_requests_total` (by provider, model and bounded
outcome) and observes `lotus_ai_provider_latency_seconds`. Instrumented at the
same transport seam as the `provider_attempt` log lines so logs and metrics
can never disagree about what happened.

All lotus-ai metric names live in METRIC_NAMES; the vocabulary guard test pins
every metric constructed under src/ to this registry, so names cannot drift
per-module. Metrics are telemetry: recording is fail-open like logging, the
service's one documented fail-open surface.
"""

from __future__ import annotations

from prometheus_client import Counter, Histogram

# Every custom metric name this service emits. The supportability gauge
# predates this registry and is included; new metrics join here first.
METRIC_NAMES = frozenset(
    {
        "lotus_ai_surface_supportability_state",
        "lotus_ai_provider_requests_total",
        "lotus_ai_provider_latency_seconds",
        "lotus_ai_kill_switch_actions_total",
    }
)

KILL_SWITCH_ACTIONS = frozenset(
    {"activated", "cleared", "expired", "refused_sync", "refused_intake"}
)

PROVIDER_ATTEMPT_OUTCOMES = frozenset({"success", "retry", "failed"})

_provider_requests_total = Counter(
    "lotus_ai_provider_requests_total",
    "Provider attempts by provider, model, and bounded outcome.",
    labelnames=("provider_id", "model_id", "outcome"),
)
_provider_latency_seconds = Histogram(
    "lotus_ai_provider_latency_seconds",
    "Provider attempt latency in seconds by provider and model.",
    labelnames=("provider_id", "model_id"),
)


_kill_switch_actions_total = Counter(
    "lotus_ai_kill_switch_actions_total",
    "Kill-switch lifecycle and enforcement actions by scope and semantics (issue #177 S4).",
    labelnames=("action", "scope", "semantics"),
)


def record_kill_switch_action(*, action: str, scope: str, semantics: str) -> None:
    """Record one kill-switch action; never raises (telemetry is fail-open)."""

    try:
        bounded_action = action if action in KILL_SWITCH_ACTIONS else "refused_sync"
        _kill_switch_actions_total.labels(
            action=bounded_action, scope=scope, semantics=semantics
        ).inc()
    except Exception:  # noqa: BLE001 - telemetry must never block a request
        pass


def record_provider_attempt(
    *,
    provider_id: str,
    model_id: str | None,
    outcome: str,
    latency_seconds: float,
) -> None:
    """Record one provider attempt; never raises (telemetry is fail-open)."""

    try:
        bounded_outcome = outcome if outcome in PROVIDER_ATTEMPT_OUTCOMES else "failed"
        model_label = model_id or "unknown"
        _provider_requests_total.labels(
            provider_id=provider_id, model_id=model_label, outcome=bounded_outcome
        ).inc()
        _provider_latency_seconds.labels(provider_id=provider_id, model_id=model_label).observe(
            latency_seconds
        )
    except Exception:  # noqa: BLE001 - telemetry must never block a request
        pass
