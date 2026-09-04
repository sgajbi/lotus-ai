"""The integrated 3+ candidate architecture proof (2026-09-05 steering).

One independently authored canonical scenario over deliberately difficult
topology - two same-provider deployment siblings plus a second-provider
candidate - proving the N-candidate control plane is closed under identity,
economics, capability, resilience and evidence:

    A: provider X / model alpha / deployment dep-1 -> billable retryable failure
    B: provider X / model alpha / deployment dep-2 -> bounded breaker block
    C: provider Y / model beta  / deployment dep-1 -> serves

with distinct canonical identities, correct per-candidate connection
material, independent breaker state, distinct exactly-once debits, the
request ceiling and one cumulative latency budget in force, the exact
serving-policy version and candidate identities on the routing record,
scope-aware capability evidence gating eligibility, and a deterministic
replay - no optimizer anywhere.
"""

from __future__ import annotations

import json
from io import BytesIO
from email.message import Message
from urllib import error

import pytest

from app.config import settings
from app.contracts.model_catalogue import (
    CapabilityEvidenceRecord,
    ModelCatalogueEntry,
    ModelCatalogueSeedSource,
    ModelLifecycleState,
    derive_model_catalogue_entry_id,
)
from app.contracts.providers import ProviderExecutionRequest, ProviderFailureCategory
from app.repositories.provider_operations_repository import ProviderDegradationStateRecord
from app.services.model_catalogue import upsert_model_catalogue_entry
from app.services.model_catalogue_store import get_model_catalogue_repository
from app.services.provider_operations_store import get_provider_operations_store
from tests.support.governed_control import GOVERNED_APPROVER, GOVERNED_REQUESTER

PROVIDER_X = "text.shared"
PROVIDER_Y = "text.other"
MODEL_ALPHA = "model-alpha"
MODEL_BETA = "model-beta"


def _catalogue(provider: str, family: str, deployment: str) -> ModelCatalogueEntry:
    entry = ModelCatalogueEntry(
        entry_id=derive_model_catalogue_entry_id(
            provider_id=provider, model_revision=family, deployment=deployment
        ),
        provider_id=provider,
        provider_mode="openai",
        model_family=family,
        model_revision=family,
        deployment=deployment,
        sku=None,
        lifecycle_state=ModelLifecycleState.APPROVED,
        revision_pinned=True,
        modalities=["text"],
        seed_source=ModelCatalogueSeedSource.SETTINGS_LIVE_TEXT,
        created_at="2026-09-01T00:00:00Z",
        last_updated_at="2026-09-01T00:00:00Z",
    )
    upsert_model_catalogue_entry(entry)
    stored = get_model_catalogue_repository().get_entry(entry.entry_id)
    assert stored is not None
    return stored


def _governed_add(entry_id: str) -> None:
    from app.contracts.model_catalogue import (
        ServingPolicyIdentityAddApprovalRequest,
        ServingPolicyIdentityAddRequest,
    )
    from app.services.serving_policy_control import (
        approve_serving_policy_identity_add,
        request_serving_policy_identity_add,
    )

    pending = request_serving_policy_identity_add(
        ServingPolicyIdentityAddRequest(entry_id=entry_id, reason="integrated proof"),
        GOVERNED_REQUESTER,
    )
    approve_serving_policy_identity_add(
        ServingPolicyIdentityAddApprovalRequest(
            action_id=pending.governed_action.action_id,
            action_hash=pending.governed_action.action_hash,
        ),
        GOVERNED_APPROVER,
    )


def _observed_evidence(entry: ModelCatalogueEntry, run_id: str) -> None:
    get_model_catalogue_repository().save_capability_evidence(
        CapabilityEvidenceRecord(
            evidence_id=f"capev_proof_{entry.candidate_id_v2[:12]}",
            candidate_id_v2=entry.candidate_id_v2,
            model_revision=entry.model_revision,
            dimension="supports_tool_calling",
            scope_type="GLOBAL",
            scope_key=None,
            fixture_id="capability_proof_examples",
            manifest_version="foundation.v1",
            evaluation_run_id=run_id,
            verdict="PASS",
            triggered_by="operator-a",
            recorded_at="2026-09-04T00:00:00Z",
        )
    )


def _request(execution_id: str) -> ProviderExecutionRequest:
    return ProviderExecutionRequest.model_validate(
        {
            "task_id": "explain.v1",
            "caller_app": "lotus-manage",
            "requested_by": "ops.user@lotus",
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
            "execution_id": execution_id,
            "requirements": {
                "tool_calling_required": True,
                "max_latency_ms": 60000,
                "max_estimated_cost_usd": 5.0,
            },
        }
    )


def _http_503() -> error.HTTPError:
    return error.HTTPError(
        url="https://a.example/v1/responses",
        code=503,
        msg="upstream",
        hdrs=Message(),
        fp=BytesIO(b"{}"),
    )


class _SuccessResponse:
    def __enter__(self) -> "_SuccessResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return (
            b'{"id": "resp_proof", "model": "model-beta", "output_text": "OK",'
            b' "usage": {"input_tokens": 120, "output_tokens": 40, "total_tokens": 160}}'
        )


def test_the_integrated_three_candidate_architecture_proof(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # --- Governed setup: identities, material, policy, evidence, controls.
    monkeypatch.setenv("PROOF_KEY_A", "secret-a")
    monkeypatch.setenv("PROOF_KEY_B", "secret-b")
    monkeypatch.setenv("PROOF_KEY_C", "secret-c")
    settings.provider_mode = "openai"
    settings.provider_rollout_state = "CANARY_ENABLED"
    settings.live_text_provider_id = "text.openai"
    settings.live_text_model_id = "gpt-5.4"
    settings.live_text_provider_api_key = "pair-secret"
    settings.live_text_api_base = "https://api.openai.com/v1"
    settings.live_text_allowed_task_ids = "explain.v1"
    settings.routing_strategy = "ordered_fallback"
    settings.live_text_fallback_provider_id = "text.claude"
    settings.live_text_fallback_model_id = "claude-sonnet-5"
    settings.live_text_fallback_api_base = "https://alternate.example/v1"
    settings.live_text_input_cost_per_1k_tokens = 0.01
    settings.live_text_output_cost_per_1k_tokens = 0.03
    settings.live_text_budget_enforced = True
    settings.live_text_hard_budget_usd = 10.0
    settings.live_text_degradation_enforced = True
    settings.live_text_degraded_failure_count_threshold = 3
    settings.live_text_circuit_open_failure_count_threshold = 5
    settings.live_text_circuit_open_seconds = 300
    settings.provider_connections_json = json.dumps(
        [
            {
                "provider_id": PROVIDER_X,
                "model_id": MODEL_ALPHA,
                "api_base": "https://a.example/v1",
                "api_key_env": "PROOF_KEY_A",
                "deployment": "dep-1",
                "region": "eu-central",
            },
            {
                "provider_id": PROVIDER_X,
                "model_id": MODEL_ALPHA,
                "api_base": "https://b.example/v1",
                "api_key_env": "PROOF_KEY_B",
                "deployment": "dep-2",
                "region": "eu-west",
            },
            {
                "provider_id": PROVIDER_Y,
                "model_id": MODEL_BETA,
                "api_base": "https://c.example/v1",
                "api_key_env": "PROOF_KEY_C",
                "deployment": "dep-1",
                "region": "eu-central",
            },
        ]
    )

    candidate_a = _catalogue(PROVIDER_X, MODEL_ALPHA, "dep-1")
    candidate_b = _catalogue(PROVIDER_X, MODEL_ALPHA, "dep-2")
    candidate_c = _catalogue(PROVIDER_Y, MODEL_BETA, "dep-1")
    # All canonical candidate identities are distinct - deployment siblings
    # and the cross-provider candidate never collapse.
    assert (
        len({candidate_a.candidate_id_v2, candidate_b.candidate_id_v2, candidate_c.candidate_id_v2})
        == 3
    )

    for entry_id in (candidate_a.entry_id, candidate_b.entry_id, candidate_c.entry_id):
        _governed_add(entry_id)
    for index, entry in enumerate((candidate_a, candidate_b, candidate_c)):
        _observed_evidence(entry, run_id=f"evalrun_proof_{index}")

    # Candidate B carries an OPEN breaker from earlier trouble - keyed to
    # ITS canonical identity, so it must block B and only B.
    get_provider_operations_store().save_degradation_state(
        ProviderDegradationStateRecord(
            degradation_key=f"live_text_generation:{candidate_b.candidate_id_v2}",
            consecutive_failure_count=5,
            last_failure_category=ProviderFailureCategory.PROVIDER_TIMEOUT,
            circuit_open_until="2027-01-01T00:00:00+00:00",
            timeout_failure_count=5,
            rate_limited_failure_count=0,
            upstream_error_failure_count=0,
            updated_at="2026-09-04T00:00:00Z",
        )
    )

    calls: list[str] = []

    def _urlopen(request: object, timeout: float) -> object:
        url = str(getattr(request, "full_url", ""))
        calls.append(url)
        if url.startswith("https://a.example"):
            raise _http_503()
        if url.startswith("https://c.example"):
            return _SuccessResponse()
        raise AssertionError(f"unexpected provider call: {url}")

    monkeypatch.setattr("urllib.request.urlopen", _urlopen)
    monkeypatch.setattr("app.services.provider_retry_backoff._sleep", lambda delay: None)
    monkeypatch.setattr("app.services.provider_retry_backoff._jitter_source", lambda: 0.0)

    from app.services.provider_gateway import execute_text_generation

    # --- The bounded sequence: A billable-fails, B is blocked, C serves.
    response = execute_text_generation(_request("exec-proof-1"))

    assert response.provider_id == PROVIDER_Y
    assert response.model_catalogue_entry_id == candidate_c.entry_id
    # Connection material resolved per candidate and deployment stayed
    # intact: A's endpoint was called, then C's; B's endpoint NEVER.
    assert [url.split("/")[2] for url in calls] == ["a.example", "c.example"]

    decision = response.routing_decision
    assert decision is not None
    assert decision.serving_policy_version == 3
    # The policy's base order carries the configured pair, which lacks
    # tool-calling evidence: scope-aware capability gating (#312) excludes
    # both with the honest UNKNOWN - never widened, never guessed - before
    # the three-candidate sequence plays out.
    assert len(decision.candidates) == 5
    assert decision.candidates[0].rejection_reason is (ProviderFailureCategory.CAPABILITY_UNKNOWN)
    assert decision.candidates[1].rejection_reason is (ProviderFailureCategory.CAPABILITY_UNKNOWN)
    assert decision.candidates[2].rejection_reason is (
        ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR
    )
    assert decision.candidates[3].rejection_reason is ProviderFailureCategory.CIRCUIT_OPEN
    assert decision.candidates[4].rejection_reason is None
    assert decision.selected_provider_id == PROVIDER_Y

    # --- Exact attempt economics: two distinct debits, each exactly once,
    # bound to their canonical candidates, summing to the budget movement.
    rows = {
        row.debit_id: row
        for row in get_provider_operations_store().list_attempt_debits()
        if row.debit_id.startswith("adbt:exec-proof-1:")
    }
    assert set(rows) == {
        f"adbt:exec-proof-1:{candidate_a.entry_id}:0",
        f"adbt:exec-proof-1:{candidate_c.entry_id}:0",
    }
    debit_a = rows[f"adbt:exec-proof-1:{candidate_a.entry_id}:0"]
    debit_c = rows[f"adbt:exec-proof-1:{candidate_c.entry_id}:0"]
    assert debit_a.candidate_id_v2 == candidate_a.candidate_id_v2
    assert debit_c.candidate_id_v2 == candidate_c.candidate_id_v2
    assert debit_a.basis == "CONSERVATIVE_ESTIMATE"
    assert debit_c.basis == "ACTUAL_USAGE"
    budget = get_provider_operations_store().get_budget_state(budget_key="live_text_generation")
    assert budget is not None
    total_spend = round(debit_a.amount_usd + debit_c.amount_usd, 8)
    assert budget.current_spend_usd == total_spend
    # The request ceiling held (admission per candidate under one budget).
    assert total_spend < 5.0
    assert budget.current_spend_usd < 10.0

    # --- Breaker independence after the execution: A charged one failure on
    # its own key, B still open on its own key, C clean on success.
    store = get_provider_operations_store()
    state_a = store.get_degradation_state(
        degradation_key=f"live_text_generation:{candidate_a.candidate_id_v2}"
    )
    assert state_a is not None and state_a.consecutive_failure_count == 1
    state_b = store.get_degradation_state(
        degradation_key=f"live_text_generation:{candidate_b.candidate_id_v2}"
    )
    assert state_b is not None and state_b.circuit_open_until is not None
    state_c = store.get_degradation_state(
        degradation_key=f"live_text_generation:{candidate_c.candidate_id_v2}"
    )
    assert state_c is None or state_c.consecutive_failure_count == 0

    # --- Deterministic replay: identical inputs, policy and evidence yield
    # the identical decision shape for a fresh execution - policy order, no
    # optimizer, no hidden state beyond the recorded breaker/economics.
    replay = execute_text_generation(_request("exec-proof-2"))
    replay_decision = replay.routing_decision
    assert replay_decision is not None
    assert replay.provider_id == PROVIDER_Y
    assert replay_decision.serving_policy_version == 3
    assert [c.rejection_reason for c in replay_decision.candidates] == [
        c.rejection_reason for c in decision.candidates
    ]
    assert replay_decision.selected_provider_id == decision.selected_provider_id
