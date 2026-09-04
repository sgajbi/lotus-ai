"""Ordered-fallback routing (issue #176, S3).

The candidate order is [configured primary, configured alternate]. A
transient primary failure fails over to the alternate within the same
execution; candidate-scoped preflight vetoes (a provider kill switch, an
open per-provider breaker) route to the alternate as rejections, not
fallbacks; request-scoped economics (quota, budget) are enforced once and
reject both candidates; and every outcome is recorded on the routing
decision with the fallback path named.
"""

import json
from email.message import Message
from io import BytesIO
from pathlib import Path
from urllib import error

import pytest
from fastapi import HTTPException

from app.config import settings
from app.contracts.capability_requirements import CapabilityRequirements
from app.contracts.kill_switches import KillSwitchActivationRequest, KillSwitchScope
from app.contracts.providers import (
    ProviderAdapterKind,
    ProviderExecutionRequest,
    ProviderFailureCategory,
    ProviderQuotaScope,
    RoutingStrategy,
)
from app.providers.base import ProviderExecutionError
from app.services.kill_switch_control import activate_kill_switch
from app.services.provider_execution_config import ProviderExecutionConfig
from app.services.provider_gateway import (
    ProviderGatewayUnavailableError,
    execute_text_generation,
)
from app.services.provider_operations_store import get_provider_operations_store
from app.services.routing_posture import build_routing_posture
from app.services.startup_policy import apply_startup_readiness_policy
from tests.support.log_collection import CollectingLogHandler
from tests.support.migration_runner import upgrade_database_to_head
from app.http.authenticated_caller import AuthenticatedCaller

ACTIVATION_CALLER = AuthenticatedCaller(
    caller_app="lotus-platform",
    trust_source="verified_service_jwt",
    credential_key_id="ops-key-alpha",
)


PRIMARY = "text.openai"
ALTERNATE = "text.claude"


def _ordered_fallback_settings() -> None:
    settings.provider_mode = "openai"
    settings.provider_rollout_state = "CANARY_ENABLED"
    settings.live_text_provider_id = PRIMARY
    settings.live_text_model_id = "gpt-5.4"
    settings.live_text_provider_api_key = "secret"
    settings.live_text_allowed_task_ids = "explain.v1"
    settings.routing_strategy = "ordered_fallback"
    settings.live_text_fallback_provider_id = ALTERNATE
    settings.live_text_fallback_model_id = "claude-sonnet-5"
    settings.live_text_fallback_api_base = "https://alternate.example/v1"
    settings.live_text_fallback_api_key = "secret-alternate"


def _request(**overrides: object) -> ProviderExecutionRequest:
    payload: dict[str, object] = {
        "task_id": "explain.v1",
        "caller_app": "lotus-manage",
        "tenant_id": "tenant-sg-001",
        "prompt_version": "foundation.explain.v1",
        "system_instructions": "Explain structured outputs conservatively.",
        "output_contract_notes": "Return explanation only.",
        "output_label": "EXPLANATION_ONLY",
        "safety_mode": "documented_only",
        "redaction_posture": "MINIMIZATION_REQUIRED",
        "context_summary": "Explain rebalance outcome",
        "context_payload": {"status": "BLOCKED"},
        "source_refs": ["lotus-manage:run:reb_001"],
        "timeout_ms": 4000,
        "retry_limit": 0,
        "max_output_tokens": 512,
    }
    payload.update(overrides)
    return ProviderExecutionRequest.model_validate(payload)


class _DispatchingAdapter:
    """Succeeds or fails per candidate, keyed by the config it receives."""

    def __init__(self, failing: dict[str, ProviderFailureCategory]) -> None:
        self.failing = failing
        self.executed_provider_ids: list[str] = []

    def execute(
        self, request: ProviderExecutionRequest, *, config: ProviderExecutionConfig
    ) -> object:
        provider_id = config.provider_id or "provider.unavailable"
        self.executed_provider_ids.append(provider_id)
        category = self.failing.get(provider_id)
        if category is not None:
            raise ProviderExecutionError(category=category, message=f"simulated {provider_id}")
        return type(
            "Response",
            (),
            {
                "provider_id": provider_id,
                "provider_mode": config.provider_mode,
                "adapter_kind": ProviderAdapterKind.OPENAI_LIVE,
                "failure_category": None,
                "timeout_ms": request.timeout_ms,
                "retry_count": 0,
                "max_output_tokens": request.max_output_tokens,
                "model_id": config.model_id,
                "provider_request_id": f"req_{provider_id}",
                "input_tokens": 10,
                "output_tokens": 20,
                "total_tokens": 30,
                "estimated_cost_usd": None,
                "stubbed": False,
                "message": f"served by {provider_id}",
                "structured_output": {},
            },
        )()


def _install_adapter(
    monkeypatch: pytest.MonkeyPatch, failing: dict[str, ProviderFailureCategory]
) -> _DispatchingAdapter:
    adapter = _DispatchingAdapter(failing)
    monkeypatch.setattr(
        "app.services.provider_gateway.resolve_text_generation_adapter",
        lambda mode: adapter,
    )
    return adapter


def test_primary_serves_when_healthy(monkeypatch: pytest.MonkeyPatch) -> None:
    _ordered_fallback_settings()
    adapter = _install_adapter(monkeypatch, failing={})

    response = execute_text_generation(_request())

    assert response.provider_id == PRIMARY
    assert adapter.executed_provider_ids == [PRIMARY]
    decision = response.routing_decision
    assert decision is not None
    assert decision.policy_id == "ordered_fallback_configured_alternate"
    assert decision.strategy is RoutingStrategy.ORDERED_FALLBACK
    assert [candidate.provider_id for candidate in decision.candidates] == [PRIMARY, ALTERNATE]
    assert all(candidate.rejection_reason is None for candidate in decision.candidates)
    assert decision.selected_provider_id == PRIMARY
    assert decision.fallback_path == []
    assert "first candidate in the enumerated universe served" in decision.selection_reason


def test_transient_primary_failure_falls_back_to_the_alternate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ordered_fallback_settings()
    adapter = _install_adapter(
        monkeypatch, failing={PRIMARY: ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR}
    )

    response = execute_text_generation(_request())

    assert response.provider_id == ALTERNATE
    assert response.message == f"served by {ALTERNATE}"
    assert adapter.executed_provider_ids == [PRIMARY, ALTERNATE]
    # The serving identity is the alternate's governed catalogue identity.
    assert response.model_catalogue_entry_id == f"{ALTERNATE}:claude-sonnet-5"

    decision = response.routing_decision
    assert decision is not None
    assert decision.selected_provider_id == ALTERNATE
    assert decision.selected_model_catalogue_entry_id == f"{ALTERNATE}:claude-sonnet-5"
    assert (
        decision.candidates[0].rejection_reason is ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR
    )
    assert decision.candidates[1].rejection_reason is None
    assert decision.fallback_path == [PRIMARY]
    assert "a later candidate served" in decision.selection_reason

    # Failure bookkeeping is keyed per provider: the primary's failure never
    # touches the alternate's breaker state.
    repository = get_provider_operations_store()
    primary_state = repository.get_degradation_state(
        degradation_key=f"live_text_generation:{PRIMARY}"
    )
    assert primary_state is not None
    assert primary_state.consecutive_failure_count == 1
    alternate_state = repository.get_degradation_state(
        degradation_key=f"live_text_generation:{ALTERNATE}"
    )
    assert alternate_state is not None
    assert alternate_state.consecutive_failure_count == 0


def test_open_primary_breaker_routes_to_the_alternate_at_preflight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ordered_fallback_settings()
    settings.live_text_degradation_enforced = True
    settings.live_text_degraded_failure_count_threshold = 1
    settings.live_text_circuit_open_failure_count_threshold = 1
    settings.live_text_circuit_open_seconds = 60
    adapter = _install_adapter(
        monkeypatch, failing={PRIMARY: ProviderFailureCategory.PROVIDER_TIMEOUT}
    )

    # First execution: the primary fails (opening its breaker), the alternate
    # serves within the same execution.
    first = execute_text_generation(_request())
    assert first.provider_id == ALTERNATE
    assert adapter.executed_provider_ids == [PRIMARY, ALTERNATE]

    # Second execution: the primary is rejected at preflight by its own open
    # breaker - no transport attempt - and the alternate serves. A preflight
    # rejection is not a fallback.
    second = execute_text_generation(_request())
    assert second.provider_id == ALTERNATE
    assert adapter.executed_provider_ids == [PRIMARY, ALTERNATE, ALTERNATE]

    decision = second.routing_decision
    assert decision is not None
    assert decision.candidates[0].rejection_reason is ProviderFailureCategory.CIRCUIT_OPEN
    assert decision.selected_provider_id == ALTERNATE
    assert decision.fallback_path == []
    assert "preflight" in decision.selection_reason


def test_kill_switch_on_the_primary_provider_routes_to_the_alternate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ordered_fallback_settings()
    database_url = f"sqlite:///{tmp_path / 'ordered-fallback-kill.db'}"
    upgrade_database_to_head(database_url)
    settings.kill_switch_store_mode = "sqlalchemy"
    settings.database_url = database_url
    adapter = _install_adapter(monkeypatch, failing={})

    activate_kill_switch(
        KillSwitchActivationRequest.model_validate(
            {
                "scope": KillSwitchScope.PROVIDER,
                "target": PRIMARY,
                "reason": "Incident LOTUS-5102: disable the primary provider.",
            }
        ),
        ACTIVATION_CALLER,
    )

    response = execute_text_generation(_request())

    assert response.provider_id == ALTERNATE
    assert adapter.executed_provider_ids == [ALTERNATE]
    decision = response.routing_decision
    assert decision is not None
    assert decision.candidates[0].rejection_reason is ProviderFailureCategory.KILL_SWITCH_ACTIVE
    assert decision.selected_provider_id == ALTERNATE
    assert decision.fallback_path == []


def test_request_scoped_quota_veto_rejects_both_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ordered_fallback_settings()
    settings.live_text_quota_enforced = True
    settings.live_text_task_quota_limits = "explain.v1=1"
    adapter = _install_adapter(monkeypatch, failing={})

    first = execute_text_generation(_request())
    assert first.provider_id == PRIMARY

    # One request consumed exactly one quota unit even with two candidates.
    quota = get_provider_operations_store().get_quota_state(
        scope=ProviderQuotaScope.TASK, scope_key="explain.v1"
    )
    assert quota is not None
    assert quota.request_count == 1

    with pytest.raises(HTTPException) as exc_info:
        execute_text_generation(_request())

    assert "QUOTA_EXCEEDED" in str(exc_info.value.detail)
    assert isinstance(exc_info.value, ProviderGatewayUnavailableError)
    decision = exc_info.value.routing_decision
    assert [candidate.rejection_reason for candidate in decision.candidates] == [
        ProviderFailureCategory.QUOTA_EXCEEDED,
        ProviderFailureCategory.QUOTA_EXCEEDED,
    ]
    assert decision.selected_provider_id is None
    assert adapter.executed_provider_ids == [PRIMARY]


def test_non_transient_primary_failure_refuses_without_trying_the_alternate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ordered_fallback_settings()
    adapter = _install_adapter(
        monkeypatch, failing={PRIMARY: ProviderFailureCategory.INVALID_LIVE_CONFIGURATION}
    )

    with pytest.raises(HTTPException) as exc_info:
        execute_text_generation(_request())

    assert "INVALID_LIVE_CONFIGURATION" in str(exc_info.value.detail)
    assert adapter.executed_provider_ids == [PRIMARY]
    assert isinstance(exc_info.value, ProviderGatewayUnavailableError)
    decision = exc_info.value.routing_decision
    assert (
        decision.candidates[0].rejection_reason
        is ProviderFailureCategory.INVALID_LIVE_CONFIGURATION
    )
    assert decision.selected_provider_id is None


def test_both_candidates_failing_refuses_with_the_full_fallback_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ordered_fallback_settings()
    adapter = _install_adapter(
        monkeypatch,
        failing={
            PRIMARY: ProviderFailureCategory.PROVIDER_TIMEOUT,
            ALTERNATE: ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR,
        },
    )

    with pytest.raises(HTTPException) as exc_info:
        execute_text_generation(_request())

    assert "PROVIDER_UPSTREAM_ERROR" in str(exc_info.value.detail)
    assert adapter.executed_provider_ids == [PRIMARY, ALTERNATE]
    assert isinstance(exc_info.value, ProviderGatewayUnavailableError)
    decision = exc_info.value.routing_decision
    assert decision.candidates[0].rejection_reason is ProviderFailureCategory.PROVIDER_TIMEOUT
    assert (
        decision.candidates[1].rejection_reason is ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR
    )
    assert decision.selected_provider_id is None
    assert decision.fallback_path == [PRIMARY, ALTERNATE]


def test_partial_fallback_identity_refuses_execution_and_blocks_promoted_startup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ordered_fallback_settings()
    settings.live_text_fallback_model_id = None
    adapter = _install_adapter(monkeypatch, failing={})

    with pytest.raises(HTTPException) as exc_info:
        execute_text_generation(_request())

    assert "INVALID_LIVE_CONFIGURATION" in str(exc_info.value.detail)
    assert "partially configured" in str(exc_info.value.detail)
    assert adapter.executed_provider_ids == []

    # The same misconfiguration is a blocking startup finding in the promoted
    # profile: the enforce policy refuses startup before any request arrives.
    settings.runtime_profile = "promoted"
    settings.startup_readiness_policy = "enforce"
    with pytest.raises(RuntimeError, match="fallback identity is partially configured"):
        apply_startup_readiness_policy()


def test_all_live_text_kill_switch_rejects_both_candidates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ordered_fallback_settings()
    database_url = f"sqlite:///{tmp_path / 'ordered-fallback-kill-all.db'}"
    upgrade_database_to_head(database_url)
    settings.kill_switch_store_mode = "sqlalchemy"
    settings.database_url = database_url
    adapter = _install_adapter(monkeypatch, failing={})

    activate_kill_switch(
        KillSwitchActivationRequest.model_validate(
            {
                "scope": KillSwitchScope.ALL_LIVE_TEXT,
                "reason": "Incident LOTUS-5103: stop all live text execution.",
            }
        ),
        ACTIVATION_CALLER,
    )

    with pytest.raises(HTTPException) as exc_info:
        execute_text_generation(_request())

    # Zero eligible candidates: fail closed with every rejection recorded,
    # never a silent stub substitution.
    assert "KILL_SWITCH_ACTIVE" in str(exc_info.value.detail)
    assert adapter.executed_provider_ids == []
    assert isinstance(exc_info.value, ProviderGatewayUnavailableError)
    decision = exc_info.value.routing_decision
    assert [candidate.rejection_reason for candidate in decision.candidates] == [
        ProviderFailureCategory.KILL_SWITCH_ACTIVE,
        ProviderFailureCategory.KILL_SWITCH_ACTIVE,
    ]
    assert decision.selected_provider_id is None
    assert decision.fallback_path == []


def test_fallback_configuration_findings_cover_each_misconfiguration() -> None:
    from app.services.provider_execution_config import (
        fallback_configuration_findings,
        resolve_provider_execution_config,
    )

    _ordered_fallback_settings()

    settings.live_text_fallback_provider_id = None
    settings.live_text_fallback_model_id = None
    settings.live_text_fallback_api_base = None
    findings = fallback_configuration_findings(resolve_provider_execution_config())
    assert any("none is configured" in finding for finding in findings)

    _ordered_fallback_settings()
    settings.live_text_fallback_provider_id = PRIMARY
    findings = fallback_configuration_findings(resolve_provider_execution_config())
    assert any("equals the primary provider" in finding for finding in findings)

    _ordered_fallback_settings()
    settings.routing_strategy = "weighted"
    findings = fallback_configuration_findings(resolve_provider_execution_config())
    assert any("unknown routing_strategy 'weighted'" in finding for finding in findings)

    _ordered_fallback_settings()
    assert fallback_configuration_findings(resolve_provider_execution_config()) == []


def test_routing_posture_names_both_candidates_under_ordered_fallback() -> None:
    _ordered_fallback_settings()

    posture = build_routing_posture()

    assert posture.strategy is RoutingStrategy.ORDERED_FALLBACK
    assert posture.policy_id == "ordered_fallback_configured_alternate"
    assert posture.candidate.provider_id == PRIMARY
    assert posture.fallback_candidate is not None
    assert posture.fallback_candidate.provider_id == ALTERNATE
    assert posture.fallback_candidate.model_catalogue_entry_id == f"{ALTERNATE}:claude-sonnet-5"
    assert posture.fallback_degradation is not None
    # The posture exposes the same derived universe the gateway enumerates
    # from - one authority, so the read cannot disagree with routing
    # (issue #244, U3).
    assert posture.candidate_universe is not None
    assert posture.candidate_universe.candidate_entry_ids == [
        f"{PRIMARY}:gpt-5.4",
        f"{ALTERNATE}:claude-sonnet-5",
    ]
    assert posture.candidate_universe.exclusions == []

    settings.routing_strategy = "fixed"
    fixed_posture = build_routing_posture()
    assert fixed_posture.strategy is RoutingStrategy.FIXED
    assert fixed_posture.fallback_candidate is None
    assert fixed_posture.fallback_degradation is None
    assert fixed_posture.candidate_universe is None


def test_real_transport_attributes_the_alternate_identity_end_to_end() -> None:
    """Issue #226: the REAL transport must stamp the serving candidate's
    configured identity - not the static adapter descriptor - on the
    response, the structured output, and the audit record. Fakes live only
    at the HTTP boundary (the transport post override seam)."""

    from app.contracts.audit_access import INTERNAL_AGGREGATE_AUDIT_SCOPE
    from app.contracts.tasks import (
        CallerMetadata,
        OutputLabel,
        TaskContextEnvelope,
        TaskExecutionRequest,
        TaskInputMode,
    )
    from app.providers.base import ProviderExecutionError
    from app.services.audit_store import get_audit_store
    from app.services.provider_execution_overrides import override_text_transport_post
    from app.services.task_executor import execute_task

    _ordered_fallback_settings()
    settings.live_text_provider_api_key = "primary-secret"

    calls: list[str] = []

    def transport_post(**kwargs: object) -> dict[str, object]:
        api_base = str(kwargs["api_base"])
        calls.append(api_base)
        if api_base == settings.live_text_api_base:
            raise ProviderExecutionError(
                category=ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR,
                message="simulated primary upstream failure",
            )
        return {
            "id": "resp_alternate_serving",
            "model": "claude-sonnet-5",
            "output_text": "Grounded explanation without figures.",
            "usage": {"input_tokens": 9, "output_tokens": 4, "total_tokens": 13},
        }

    with override_text_transport_post(transport_post):
        response = execute_task(
            TaskExecutionRequest(
                task_id="explain.v1",
                input_mode=TaskInputMode.STRUCTURED_CONTEXT,
                caller=CallerMetadata(
                    caller_app="lotus-manage",
                    correlation_id="corr-226-attribution",
                    tenant_id="tenant-sg-001",
                ),
                context=TaskContextEnvelope(
                    summary="Explain rebalance outcome",
                    payload={"status": "BLOCKED", "rule_count": 3},
                    source_refs=["lotus-manage:run:reb_001"],
                ),
                expected_output_label=OutputLabel.EXPLANATION_ONLY,
            )
        )

    assert len(calls) == 2
    assert response.audit.provider_id == ALTERNATE
    assert response.result.structured_output["provider_id"] == ALTERNATE
    assert response.audit.routing_decision is not None
    assert response.audit.routing_decision.selected_provider_id == ALTERNATE

    records = get_audit_store().list(scope=INTERNAL_AGGREGATE_AUDIT_SCOPE, limit=5)
    record = next(r for r in records if r.correlation_id == "corr-226-attribution")
    assert record.provider_id == ALTERNATE


def test_every_evidence_surface_names_the_serving_candidate(
    monkeypatch: pytest.MonkeyPatch, app_log_collector: CollectingLogHandler
) -> None:
    """Issue #237: one answer to "which provider served this execution".

    The #226 test above fakes at the transport post override, which returns
    before the transport emits any telemetry - so it can prove the audit
    record but is structurally blind to metrics, logs and spans. This one
    fakes at the true HTTP boundary instead, so the real telemetry path
    runs, and it covers the surfaces the issue listed as unverified:
    metrics labels, structured log lines, breaker/degradation evidence,
    and the identity the run ledger attests.

    The primary's breaker is left open by its own failure, so the two
    candidates hold genuinely different postures: evidence that reported
    the ambient provider would report the wrong one, visibly.
    """

    from prometheus_client import REGISTRY

    from app.contracts.tasks import (
        CallerMetadata,
        OutputLabel,
        TaskContextEnvelope,
        TaskExecutionRequest,
        TaskInputMode,
    )
    from app.services.provider_degradation_state import build_provider_degradation_status
    from app.services.task_executor import execute_task
    from app.services.task_execution_context_builder import build_task_execution_context
    from app.services.workflow_pack_registry import get_workflow_pack_registration
    from app.services.workflow_run_attestation_source import (
        capture_workflow_run_attestation_source,
    )

    _ordered_fallback_settings()
    settings.live_text_degradation_enforced = True
    settings.live_text_degraded_failure_count_threshold = 1
    settings.live_text_circuit_open_failure_count_threshold = 1
    settings.live_text_circuit_open_seconds = 60

    def _attempts(provider_id: str, model_id: str, outcome: str) -> float:
        return (
            REGISTRY.get_sample_value(
                "lotus_ai_provider_requests_total",
                {"provider_id": provider_id, "model_id": model_id, "outcome": outcome},
            )
            or 0.0
        )

    before_alternate = _attempts(ALTERNATE, "claude-sonnet-5", "success")
    before_primary = _attempts(PRIMARY, "gpt-5.4", "failed")

    class _Served:
        def __enter__(self) -> "_Served":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(
                {
                    "id": "resp_alternate_serving",
                    "model": "claude-sonnet-5",
                    "output_text": "Grounded explanation without figures.",
                    "usage": {"input_tokens": 9, "output_tokens": 4, "total_tokens": 13},
                }
            ).encode("utf-8")

    def _urlopen(request: object, timeout: float) -> object:
        url = str(getattr(request, "full_url", ""))
        if url.startswith(settings.live_text_api_base):
            raise error.HTTPError(
                url=url, code=503, msg="Service Unavailable", hdrs=Message(), fp=BytesIO(b"{}")
            )
        return _Served()

    monkeypatch.setattr("urllib.request.urlopen", _urlopen)

    request = TaskExecutionRequest(
        task_id="explain.v1",
        input_mode=TaskInputMode.STRUCTURED_CONTEXT,
        caller=CallerMetadata(
            caller_app="lotus-manage",
            correlation_id="corr-237-attribution",
            tenant_id="tenant-sg-001",
        ),
        context=TaskContextEnvelope(
            summary="Explain rebalance outcome",
            payload={"status": "BLOCKED", "rule_count": 3},
            source_refs=["lotus-manage:run:reb_001"],
        ),
        expected_output_label=OutputLabel.EXPLANATION_ONLY,
    )
    response = execute_task(request)

    # Already-correct surfaces (issue #226), re-pinned so they stay correct.
    assert response.audit.provider_id == ALTERNATE
    assert response.result.structured_output["provider_id"] == ALTERNATE
    assert response.audit.routing_decision is not None
    assert response.audit.routing_decision.selected_provider_id == ALTERNATE

    # Metrics: each attempt counted against the candidate that made it.
    assert _attempts(ALTERNATE, "claude-sonnet-5", "success") == before_alternate + 1
    assert _attempts(PRIMARY, "gpt-5.4", "failed") == before_primary + 1
    for descriptor_display_name in (
        "OpenAI Managed Text Provider",
        "Local OpenAI-Compatible Text Provider",
    ):
        assert (
            REGISTRY.get_sample_value(
                "lotus_ai_provider_requests_total",
                {
                    "provider_id": descriptor_display_name,
                    "model_id": "claude-sonnet-5",
                    "outcome": "success",
                },
            )
            is None
        )

    # Logs: the same two identities, in attempt order.
    attempts = app_log_collector.events("provider_attempt")
    assert [line["provider_id"] for line in attempts] == [PRIMARY, ALTERNATE]
    assert [line["outcome"] for line in attempts] == ["failed", "success"]
    assert [line["model_id"] for line in attempts] == ["gpt-5.4", "claude-sonnet-5"]

    # Breaker evidence: the serving candidate's posture, not the ambient one.
    # The primary's breaker opened on its failure, so these genuinely differ -
    # reading the ambient config here would report the primary's open circuit
    # as though it described the execution that actually succeeded.
    alternate_posture = build_provider_degradation_status(ALTERNATE)
    primary_posture = build_provider_degradation_status(PRIMARY)
    assert primary_posture.status != alternate_posture.status
    provider_evidence = next(
        descriptor
        for descriptor in response.evidence.descriptors
        if descriptor.evidence_type == "provider_resolution"
    )
    assert provider_evidence.attributes["provider_id"] == ALTERNATE
    assert provider_evidence.attributes["degradation_status"] == alternate_posture.status

    # Execution ledger: the attested identity is derived from the audit
    # record, so it inherits the serving candidate rather than re-deriving it.
    registration = get_workflow_pack_registration(pack_id="idea_explanation.pack", version="v1")
    assert registration is not None
    attestation = capture_workflow_run_attestation_source(
        run_id="wpr_237",
        # The registration supplies evaluator identity only; what is under
        # test here is which provider the attested record names.
        context=build_task_execution_context(request),
        response=response,
        registration=registration,
        model_risk_status="APPROVED",
        model_risk_approval_ref="mr-237",
    )
    assert attestation.provider_id == ALTERNATE
    assert attestation.model_id == "claude-sonnet-5"


# --- Capability eligibility (issue #244, S3) -------------------------------


def _assess_structured_output(provider_id: str, model_id: str, fact: bool) -> None:
    from app.contracts.model_catalogue import derive_model_catalogue_entry_id
    from app.services.model_catalogue import ensure_model_catalogue_seeded
    from app.services.model_catalogue_store import get_model_catalogue_repository

    ensure_model_catalogue_seeded()
    repository = get_model_catalogue_repository()
    entry_id = derive_model_catalogue_entry_id(
        provider_id=provider_id, model_revision=model_id, deployment=None
    )
    entry = repository.get_entry(entry_id)
    assert entry is not None
    repository.upsert_entry(entry.model_copy(update={"supports_structured_output": fact}))


def _requirements(**overrides: object) -> CapabilityRequirements:
    payload: dict[str, object] = {"structured_output_required": True}
    payload.update(overrides)
    return CapabilityRequirements.model_validate(payload)


def test_an_unassessed_capability_fails_closed_as_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unknown is not eligibility, and it refuses AS unknown: the rejection
    category is CAPABILITY_UNKNOWN, distinct from a fact the catalogue proves
    absent — laundering unknown into a confident answer in either direction is
    how capability claims rot."""

    _ordered_fallback_settings()
    adapter = _install_adapter(monkeypatch, failing={})

    with pytest.raises(ProviderGatewayUnavailableError) as exc_info:
        execute_text_generation(_request(requirements=_requirements()))

    decision = exc_info.value.routing_decision
    assert [c.rejection_reason for c in decision.candidates] == [
        ProviderFailureCategory.CAPABILITY_UNKNOWN,
        ProviderFailureCategory.CAPABILITY_UNKNOWN,
    ]
    assert adapter.executed_provider_ids == []
    assert decision.requirements_enforced_dimensions == ["structured_output_required"]
    assert decision.requirements_unenforced_dimensions == []


def test_a_proven_absent_capability_refuses_distinctly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ordered_fallback_settings()
    _install_adapter(monkeypatch, failing={})
    _assess_structured_output(PRIMARY, "gpt-5.4", False)

    with pytest.raises(ProviderGatewayUnavailableError) as exc_info:
        execute_text_generation(_request(requirements=_requirements()))

    decision = exc_info.value.routing_decision
    assert decision.candidates[0].rejection_reason is (
        ProviderFailureCategory.CAPABILITY_NOT_SUPPORTED
    )
    assert decision.candidates[1].rejection_reason is ProviderFailureCategory.CAPABILITY_UNKNOWN


def test_an_assessed_candidate_serves_while_the_unassessed_one_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The eligibility pipeline composes with the existing selection: the
    primary is rejected on capability grounds and the assessed alternate
    serves, recorded as a preflight rejection rather than a fallback."""

    _ordered_fallback_settings()
    adapter = _install_adapter(monkeypatch, failing={})
    _assess_structured_output(ALTERNATE, "claude-sonnet-5", True)

    response = execute_text_generation(
        _request(
            requirements=_requirements(max_estimated_cost_usd=0.50),
        )
    )

    assert response.provider_id == ALTERNATE
    assert adapter.executed_provider_ids == [ALTERNATE]
    decision = response.routing_decision
    assert decision is not None
    assert decision.candidates[0].rejection_reason is ProviderFailureCategory.CAPABILITY_UNKNOWN
    assert decision.selected_provider_id == ALTERNATE
    assert decision.fallback_path == []
    # The decision names what it holds: the cost ceiling is enforced by
    # pre-attempt admission over the durable attempt debits (issue #290).
    assert decision.requirements_enforced_dimensions == [
        "max_estimated_cost_usd",
        "structured_output_required",
    ]
    assert decision.requirements_unenforced_dimensions == []


def test_a_declared_latency_ceiling_tightens_the_execution_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """max_latency_ms is genuinely ENFORCED: the transport cannot wait longer
    than the ceiling, because the request it executes carries the tightened
    timeout before any candidate runs."""

    _ordered_fallback_settings()
    seen_timeouts: list[int] = []

    class _TimeoutRecordingAdapter(_DispatchingAdapter):
        def execute(self, request, *, config):  # type: ignore[no-untyped-def]
            seen_timeouts.append(request.timeout_ms)
            return super().execute(request, config=config)

    adapter = _TimeoutRecordingAdapter(failing={})
    monkeypatch.setattr(
        "app.services.provider_gateway.resolve_text_generation_adapter",
        lambda mode: adapter,
    )
    _assess_structured_output(PRIMARY, "gpt-5.4", True)

    response = execute_text_generation(
        _request(
            timeout_ms=4000,
            requirements=_requirements(max_latency_ms=1500),
        )
    )

    assert response.provider_id == PRIMARY
    # The attempt timeout is the remaining governed budget at attempt start:
    # never above the caller's ceiling, allowing real-clock granularity below.
    assert len(seen_timeouts) == 1
    assert 1 <= seen_timeouts[0] <= 1500
    decision = response.routing_decision
    assert decision is not None
    assert "max_latency_ms" in decision.requirements_enforced_dimensions
