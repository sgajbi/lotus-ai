"""The governed serving-policy artifact (issue #295, S2).

Adding an identity is governed two-step through the #157 primitive with the
hash binding the full resulting order; removal is immediate under one
verified principal with the approver honestly null; the candidate universe
follows the policy order and records its version; and a third genuinely
interchangeable identity serves through the existing gateway with every
fence honoured - the steering's north-star proof.
"""

import json

import pytest
from fastapi import HTTPException

from app.config import settings
from app.contracts.model_catalogue import (
    ModelCatalogueEntry,
    ModelCatalogueSeedSource,
    ModelLifecycleState,
    ServingPolicyIdentityAddApprovalRequest,
    ServingPolicyIdentityAddRequest,
    ServingPolicyIdentityRemovalRequest,
    derive_model_catalogue_entry_id,
)
from app.contracts.providers import (
    CandidateUniverseExclusionReason,
    ProviderAdapterKind,
    ProviderFailureCategory,
)
from app.providers.base import ProviderExecutionError
from app.services.model_catalogue import (
    current_serving_order,
    derive_candidate_universe,
    upsert_model_catalogue_entry,
)
from app.services.provider_execution_config import resolve_provider_execution_config
from app.services.serving_policy_control import (
    approve_serving_policy_identity_add,
    build_serving_policy_status,
    remove_serving_policy_identity,
    request_serving_policy_identity_add,
)
from tests.support.governed_control import GOVERNED_APPROVER, GOVERNED_REQUESTER
from tests.unit.test_ordered_fallback_routing import (
    ALTERNATE,
    PRIMARY,
    _install_adapter,
    _ordered_fallback_settings,
    _request,
)

THIRD_PROVIDER = "text.regional"
THIRD_MODEL = "claude-sonnet-5"
THIRD_REVISION = "claude-sonnet-5-regional"


def _third_entry_id() -> str:
    return derive_model_catalogue_entry_id(
        provider_id=THIRD_PROVIDER, model_revision=THIRD_REVISION, deployment=None
    )


def _catalogue_third_identity(
    state: ModelLifecycleState = ModelLifecycleState.APPROVED,
) -> str:
    entry_id = _third_entry_id()
    upsert_model_catalogue_entry(
        ModelCatalogueEntry(
            entry_id=entry_id,
            provider_id=THIRD_PROVIDER,
            provider_mode="openai",
            model_family=THIRD_MODEL,
            model_revision=THIRD_REVISION,
            deployment=None,
            sku=None,
            lifecycle_state=state,
            revision_pinned=True,
            modalities=["text"],
            seed_source=ModelCatalogueSeedSource.SETTINGS_LIVE_TEXT,
            created_at="2026-09-01T00:00:00Z",
            last_updated_at="2026-09-01T00:00:00Z",
        )
    )
    return entry_id


def _declare_third_connection() -> None:
    settings.provider_connections_json = json.dumps(
        [
            {
                "provider_id": THIRD_PROVIDER,
                "model_id": THIRD_MODEL,
                "model_version": THIRD_REVISION,
                "api_base": "https://regional.example/v1",
            }
        ]
    )


def _governed_add(entry_id: str) -> None:
    pending = request_serving_policy_identity_add(
        ServingPolicyIdentityAddRequest(entry_id=entry_id, reason="Widen governed serving."),
        GOVERNED_REQUESTER,
    )
    approve_serving_policy_identity_add(
        ServingPolicyIdentityAddApprovalRequest(
            action_id=pending.governed_action.action_id,
            action_hash=pending.governed_action.action_hash,
        ),
        GOVERNED_APPROVER,
    )


def test_identity_add_is_governed_two_step_and_binds_the_resulting_order() -> None:
    _ordered_fallback_settings()
    entry_id = _catalogue_third_identity()

    pending = request_serving_policy_identity_add(
        ServingPolicyIdentityAddRequest(entry_id=entry_id, reason="Widen governed serving."),
        GOVERNED_REQUESTER,
    )
    # Nothing changed at the request step.
    assert build_serving_policy_status().current is None
    assert pending.governed_action.status.value == "PENDING"

    with pytest.raises(HTTPException) as refused:
        approve_serving_policy_identity_add(
            ServingPolicyIdentityAddApprovalRequest(
                action_id=pending.governed_action.action_id,
                action_hash=pending.governed_action.action_hash,
            ),
            GOVERNED_REQUESTER,
        )
    assert refused.value.status_code == 403
    assert "distinct" in refused.value.detail

    changed = approve_serving_policy_identity_add(
        ServingPolicyIdentityAddApprovalRequest(
            action_id=pending.governed_action.action_id,
            action_hash=pending.governed_action.action_hash,
        ),
        GOVERNED_APPROVER,
    )
    policy = changed.policy
    assert policy.version == 1
    assert policy.ordered_entry_ids[-1] == entry_id
    assert policy.action == "IDENTITY_ADD"
    assert policy.requested_by_key_id == "ops-key-alpha"
    assert policy.approver_key_id == "ops-key-beta"
    assert policy.governed_action_id == pending.governed_action.action_id

    # Idempotent guard: the identity cannot be added twice.
    with pytest.raises(HTTPException) as duplicate:
        request_serving_policy_identity_add(
            ServingPolicyIdentityAddRequest(entry_id=entry_id, reason="again"),
            GOVERNED_REQUESTER,
        )
    assert duplicate.value.status_code == 409


def test_an_uncatalogued_or_ineligible_identity_cannot_be_requested() -> None:
    _ordered_fallback_settings()

    with pytest.raises(HTTPException) as missing:
        request_serving_policy_identity_add(
            ServingPolicyIdentityAddRequest(entry_id="entry-ghost", reason="r"),
            GOVERNED_REQUESTER,
        )
    assert missing.value.status_code == 404

    retired = _catalogue_third_identity(state=ModelLifecycleState.RETIRED)
    with pytest.raises(HTTPException) as ineligible:
        request_serving_policy_identity_add(
            ServingPolicyIdentityAddRequest(entry_id=retired, reason="r"),
            GOVERNED_REQUESTER,
        )
    assert ineligible.value.status_code == 409


def test_a_policy_change_between_request_and_approval_refuses_the_stale_hash() -> None:
    """The hash binds the FULL resulting order: removing an identity after
    the request changes the rebuilt payload, so the stale approval refuses
    rather than executing against an order nobody reviewed."""

    _ordered_fallback_settings()
    entry_id = _catalogue_third_identity()
    _governed_add(entry_id)

    fourth = derive_model_catalogue_entry_id(
        provider_id="text.fourth", model_revision="model-4", deployment=None
    )
    upsert_model_catalogue_entry(
        ModelCatalogueEntry(
            entry_id=fourth,
            provider_id="text.fourth",
            provider_mode="openai",
            model_family="model-4",
            model_revision="model-4",
            deployment=None,
            sku=None,
            lifecycle_state=ModelLifecycleState.APPROVED,
            revision_pinned=True,
            modalities=["text"],
            seed_source=ModelCatalogueSeedSource.SETTINGS_LIVE_TEXT,
            created_at="2026-09-01T00:00:00Z",
            last_updated_at="2026-09-01T00:00:00Z",
        )
    )
    pending = request_serving_policy_identity_add(
        ServingPolicyIdentityAddRequest(entry_id=fourth, reason="add fourth"),
        GOVERNED_REQUESTER,
    )
    remove_serving_policy_identity(
        ServingPolicyIdentityRemovalRequest(entry_id=entry_id, reason="contain"),
        GOVERNED_REQUESTER,
    )

    with pytest.raises(HTTPException) as stale:
        approve_serving_policy_identity_add(
            ServingPolicyIdentityAddApprovalRequest(
                action_id=pending.governed_action.action_id,
                action_hash=pending.governed_action.action_hash,
            ),
            GOVERNED_APPROVER,
        )
    assert stale.value.status_code == 409


def test_removal_is_immediate_single_principal_with_null_approver() -> None:
    _ordered_fallback_settings()
    entry_id = _catalogue_third_identity()
    _governed_add(entry_id)

    changed = remove_serving_policy_identity(
        ServingPolicyIdentityRemovalRequest(entry_id=entry_id, reason="Contain regression."),
        GOVERNED_REQUESTER,
    )
    policy = changed.policy
    assert policy.version == 2
    assert entry_id not in policy.ordered_entry_ids
    assert policy.action == "IDENTITY_REMOVE"
    assert policy.approver_key_id is None
    assert policy.requested_by_key_id == "ops-key-alpha"

    with pytest.raises(HTTPException) as absent:
        remove_serving_policy_identity(
            ServingPolicyIdentityRemovalRequest(entry_id=entry_id, reason="again"),
            GOVERNED_REQUESTER,
        )
    assert absent.value.status_code == 404


def test_universe_follows_the_policy_order_and_records_its_version() -> None:
    _ordered_fallback_settings()
    _declare_third_connection()
    entry_id = _catalogue_third_identity()
    _governed_add(entry_id)

    order, version = current_serving_order()
    assert order[-1] == entry_id
    assert version == 1

    universe = derive_candidate_universe(resolve_provider_execution_config())
    assert universe.serving_policy_version == 1
    assert universe.candidate_entry_ids == order
    assert len(universe.candidate_entry_ids) == 3


def test_a_policy_identity_without_connection_material_is_a_reasoned_exclusion() -> None:
    _ordered_fallback_settings()
    entry_id = _catalogue_third_identity()
    _governed_add(entry_id)
    # No declared connection material for the third identity.
    settings.provider_connections_json = "[]"

    universe = derive_candidate_universe(resolve_provider_execution_config())
    assert entry_id not in universe.candidate_entry_ids
    exclusion = next(e for e in universe.exclusions if e.entry_id == entry_id)
    assert exclusion.reason is CandidateUniverseExclusionReason.CONNECTION_MATERIAL_MISSING


def test_the_third_identity_serves_when_earlier_candidates_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The steering's north-star proof: three genuinely interchangeable
    governed candidates enter the universe, and when the first two fail
    transiently the third serves - without any consumer naming a provider,
    with the policy version on the decision."""

    _ordered_fallback_settings()
    _declare_third_connection()
    entry_id = _catalogue_third_identity()
    _governed_add(entry_id)
    adapter = _install_adapter(
        monkeypatch,
        failing={
            PRIMARY: ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR,
            ALTERNATE: ProviderFailureCategory.PROVIDER_TIMEOUT,
        },
    )

    from app.services.provider_gateway import execute_text_generation

    response = execute_text_generation(_request())

    assert response.provider_id == THIRD_PROVIDER
    assert adapter.executed_provider_ids == [PRIMARY, ALTERNATE, THIRD_PROVIDER]
    decision = response.routing_decision
    assert decision is not None
    assert len(decision.candidates) == 3
    assert decision.selected_provider_id == THIRD_PROVIDER
    assert decision.serving_policy_version == 1


class _ModelKeyedAdapter:
    """Fails per (provider, model) - two same-provider candidates run through
    one adapter, so provider-keyed failure injection cannot tell them apart."""

    def __init__(self, failing: dict[tuple[str, str], ProviderFailureCategory]) -> None:
        self.failing = failing
        self.executed: list[tuple[str, str]] = []

    def execute(self, request: object, *, config: object) -> object:
        provider_id = getattr(config, "provider_id", None) or "provider.unavailable"
        model_id = getattr(config, "model_id", None) or "model.unavailable"
        self.executed.append((provider_id, model_id))
        category = self.failing.get((provider_id, model_id))
        if category is not None:
            raise ProviderExecutionError(
                category=category, message=f"simulated {provider_id}/{model_id}"
            )
        return type(
            "Response",
            (),
            {
                "provider_id": provider_id,
                "provider_mode": getattr(config, "provider_mode", "openai"),
                "adapter_kind": ProviderAdapterKind.OPENAI_LIVE,
                "failure_category": None,
                "timeout_ms": getattr(request, "timeout_ms", 4000),
                "retry_count": 0,
                "max_output_tokens": getattr(request, "max_output_tokens", 512),
                "model_id": model_id,
                "provider_request_id": f"req_{model_id}",
                "input_tokens": 10,
                "output_tokens": 20,
                "total_tokens": 30,
                "estimated_cost_usd": None,
                "stubbed": False,
                "message": f"served by {provider_id}/{model_id}",
                "structured_output": {},
            },
        )()


def test_a_sibling_model_failure_never_excludes_a_healthy_same_provider_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Issue #304: breaker health is CANDIDATE health. Same-provider model
    candidates are normal serving topology; before the candidate-scoped
    breaker key, model-A's repeated failures opened the PROVIDER breaker and
    excluded healthy model-B at preflight - this test run against the
    provider-keyed breaker is the recorded proof of that exclusion, and
    against the candidate-scoped key it proves the fix: B serves while A
    stays refused by its own breaker."""

    _ordered_fallback_settings()
    settings.live_text_degradation_enforced = True
    settings.live_text_degraded_failure_count_threshold = 1
    settings.live_text_circuit_open_failure_count_threshold = 1
    settings.live_text_circuit_open_seconds = 60

    sibling_revision = "gpt-5.4-mini"
    sibling_id = derive_model_catalogue_entry_id(
        provider_id=PRIMARY, model_revision=sibling_revision, deployment=None
    )
    upsert_model_catalogue_entry(
        ModelCatalogueEntry(
            entry_id=sibling_id,
            provider_id=PRIMARY,
            provider_mode="openai",
            model_family="gpt-5.4-mini",
            model_revision=sibling_revision,
            deployment=None,
            sku=None,
            lifecycle_state=ModelLifecycleState.APPROVED,
            revision_pinned=True,
            modalities=["text"],
            seed_source=ModelCatalogueSeedSource.SETTINGS_LIVE_TEXT,
            created_at="2026-09-01T00:00:00Z",
            last_updated_at="2026-09-01T00:00:00Z",
        )
    )
    settings.provider_connections_json = json.dumps(
        [
            {
                "provider_id": PRIMARY,
                "model_id": "gpt-5.4-mini",
                "model_version": sibling_revision,
                "api_base": "https://sibling.example/v1",
            }
        ]
    )
    _governed_add(sibling_id)
    adapter = _ModelKeyedAdapter(
        failing={
            (PRIMARY, "gpt-5.4"): ProviderFailureCategory.PROVIDER_TIMEOUT,
            (ALTERNATE, "claude-sonnet-5"): ProviderFailureCategory.PROVIDER_TIMEOUT,
        }
    )
    monkeypatch.setattr(
        "app.services.provider_gateway.resolve_text_generation_adapter",
        lambda mode: adapter,
    )

    from app.services.provider_gateway import execute_text_generation

    # Execution 1: model-A and the alternate fail (opening their breakers);
    # the healthy same-provider sibling serves.
    first = execute_text_generation(_request())
    assert first.provider_id == PRIMARY
    assert first.model_catalogue_entry_id == sibling_id

    # Execution 2: model-A and the alternate are refused at preflight by
    # their OWN open breakers - and the sibling still serves, because
    # model-A's failures never opened the sibling's breaker.
    second = execute_text_generation(_request())
    assert second.provider_id == PRIMARY
    assert second.model_catalogue_entry_id == sibling_id
    assert adapter.executed == [
        (PRIMARY, "gpt-5.4"),
        (ALTERNATE, "claude-sonnet-5"),
        (PRIMARY, "gpt-5.4-mini"),
        (PRIMARY, "gpt-5.4-mini"),
    ]
    decision = second.routing_decision
    assert decision is not None
    assert decision.candidates[0].rejection_reason is ProviderFailureCategory.CIRCUIT_OPEN
    assert decision.candidates[1].rejection_reason is ProviderFailureCategory.CIRCUIT_OPEN
    assert decision.candidates[2].rejection_reason is None


def test_a_deployment_scoped_identity_serves_under_its_own_catalogue_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Issue #303: a deployment-scoped candidate is a complete governed
    identity - catalogued with its deployment, connected through declared
    material carrying that deployment, policy-ordered, and when it serves
    the response and decision bind the deployment-scoped entry id, never
    the direct-API entry of the same provider and revision."""

    _ordered_fallback_settings()
    deployment = "eu-frankfurt-1"
    scoped_id = derive_model_catalogue_entry_id(
        provider_id=THIRD_PROVIDER, model_revision=THIRD_REVISION, deployment=deployment
    )
    upsert_model_catalogue_entry(
        ModelCatalogueEntry(
            entry_id=scoped_id,
            provider_id=THIRD_PROVIDER,
            provider_mode="openai",
            model_family=THIRD_MODEL,
            model_revision=THIRD_REVISION,
            deployment=deployment,
            sku=None,
            lifecycle_state=ModelLifecycleState.APPROVED,
            revision_pinned=True,
            modalities=["text"],
            seed_source=ModelCatalogueSeedSource.SETTINGS_LIVE_TEXT,
            created_at="2026-09-01T00:00:00Z",
            last_updated_at="2026-09-01T00:00:00Z",
        )
    )
    settings.provider_connections_json = json.dumps(
        [
            {
                "provider_id": THIRD_PROVIDER,
                "model_id": THIRD_MODEL,
                "model_version": THIRD_REVISION,
                "api_base": "https://eu.example/v1",
                "deployment": deployment,
                "region": "eu-central",
            }
        ]
    )
    _governed_add(scoped_id)
    adapter = _install_adapter(
        monkeypatch,
        failing={
            PRIMARY: ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR,
            ALTERNATE: ProviderFailureCategory.PROVIDER_TIMEOUT,
        },
    )

    from app.services.provider_gateway import execute_text_generation

    response = execute_text_generation(_request())

    assert response.provider_id == THIRD_PROVIDER
    assert adapter.executed_provider_ids == [PRIMARY, ALTERNATE, THIRD_PROVIDER]
    # The deployment-scoped identity is what served - bound, recorded and
    # answerable from the response alone.
    assert response.model_catalogue_entry_id == scoped_id
    decision = response.routing_decision
    assert decision is not None
    assert decision.selected_provider_id == THIRD_PROVIDER
    assert scoped_id in {candidate.model_catalogue_entry_id for candidate in decision.candidates}


def test_status_surface_reports_history_newest_first() -> None:
    _ordered_fallback_settings()
    entry_id = _catalogue_third_identity()
    _governed_add(entry_id)
    remove_serving_policy_identity(
        ServingPolicyIdentityRemovalRequest(entry_id=entry_id, reason="contain"),
        GOVERNED_REQUESTER,
    )

    status = build_serving_policy_status()
    assert status.current is not None
    assert status.current.version == 2
    assert [record.version for record in status.versions] == [2, 1]


def test_a_delimiter_ambiguous_identity_cannot_join_the_serving_policy() -> None:
    """Issue #314 (P0 block): a revision containing the v1 delimiter renders
    an ambiguous entry id - two distinct tuples can share it - so policy
    admission refuses it until candidate identity v2 keys the policy."""

    _ordered_fallback_settings()
    ambiguous_id = derive_model_catalogue_entry_id(
        provider_id="text.local", model_revision="qwen3:8b", deployment=None
    )
    upsert_model_catalogue_entry(
        ModelCatalogueEntry(
            entry_id=ambiguous_id,
            provider_id="text.local",
            provider_mode="local_openai_compatible",
            model_family="qwen3:8b",
            model_revision="qwen3:8b",
            deployment=None,
            sku=None,
            lifecycle_state=ModelLifecycleState.APPROVED,
            revision_pinned=True,
            modalities=["text"],
            seed_source=ModelCatalogueSeedSource.SETTINGS_LIVE_TEXT,
            created_at="2026-09-01T00:00:00Z",
            last_updated_at="2026-09-01T00:00:00Z",
        )
    )

    with pytest.raises(HTTPException) as refused:
        request_serving_policy_identity_add(
            ServingPolicyIdentityAddRequest(entry_id=ambiguous_id, reason="widen"),
            GOVERNED_REQUESTER,
        )
    assert refused.value.status_code == 409
    assert "delimiter-ambiguous" in refused.value.detail
