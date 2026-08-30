"""Model-risk evaluation sourced from the governed catalogue (issue #191).

The evaluation matrix from the inventory era is preserved case for case; the
source of truth is now APPROVED catalogue rows, so lifecycle transitions
(#175 S3) change outcomes immediately. The env inventory's own validation
remains tested as the seed-time guard it still is.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from app.config import Settings, settings
from app.contracts.model_catalogue import (
    ModelCatalogueEntry,
    ModelCatalogueSeedSource,
    ModelLifecycleState,
    derive_model_catalogue_entry_id,
)
from app.providers.configured_workflow_run_model_risk_inventory import (
    ConfiguredWorkflowRunModelRiskInventory,
)
from app.services.model_catalogue_store import (
    get_model_catalogue_repository,
    reset_model_catalogue_store_cache,
)
from app.services.workflow_run_model_risk import (
    WorkflowRunModelRiskDecision,
    evaluate_workflow_run_model_risk,
    evaluate_workflow_run_model_risk_from_catalogue,
)

APPROVED_INVENTORY_ROW: dict[str, object] = {
    "provider_id": "text.openai",
    "provider_mode": "openai",
    "model_id": "gpt-5.4",
    "model_version": "2026-06-01",
    "workflow_pack_ids": ["idea_explanation.pack"],
    "approval_ref": "model-risk://lotus-ai/gpt-5.4/2026-06-01",
    "approved_from_utc": "2026-06-01T00:00:00Z",
    "approved_until_utc": "2026-09-01T00:00:00Z",
}


def _entry(**overrides: object) -> ModelCatalogueEntry:
    payload: dict[str, object] = {
        "provider_id": "text.openai",
        "provider_mode": "openai",
        "model_family": "gpt-5.4",
        "model_revision": "2026-06-01",
        "deployment": None,
        "sku": None,
        "lifecycle_state": ModelLifecycleState.APPROVED,
        "revision_pinned": True,
        "modalities": ["text"],
        "approved_workflow_pack_ids": ["idea_explanation.pack"],
        "approval_evidence_refs": ["model-risk://lotus-ai/gpt-5.4/2026-06-01"],
        "approved_from_utc": "2026-06-01T00:00:00Z",
        "approved_until_utc": "2026-09-01T00:00:00Z",
        "seed_source": ModelCatalogueSeedSource.APPROVED_WORKFLOW_RUN_MODEL_INVENTORY,
        "created_at": "2026-06-01T00:00:00Z",
        "last_updated_at": "2026-06-01T00:00:00Z",
    }
    payload.update(overrides)
    payload["entry_id"] = derive_model_catalogue_entry_id(
        provider_id=str(payload["provider_id"]),
        model_revision=str(payload["model_revision"]),
        deployment=None,
    )
    return ModelCatalogueEntry.model_validate(payload)


def _evaluate(
    *,
    entries: list[ModelCatalogueEntry] | None = None,
    workflow_pack_id: str = "idea_explanation.pack",
    model_version: str = "2026-06-01",
    evaluated_at_utc: str = "2026-07-11T10:00:00Z",
    stubbed: bool = False,
) -> WorkflowRunModelRiskDecision:
    return evaluate_workflow_run_model_risk(
        entries=entries if entries is not None else [_entry()],
        provider_id="text.openai",
        provider_mode="openai",
        model_id="gpt-5.4",
        model_version=model_version,
        workflow_pack_id=workflow_pack_id,
        evaluated_at_utc=evaluated_at_utc,
        stubbed=stubbed,
    )


def test_exact_effective_approved_entry_is_approved() -> None:
    decision = _evaluate()

    assert decision.status == "approved"
    assert decision.approval_ref == "model-risk://lotus-ai/gpt-5.4/2026-06-01"


@pytest.mark.parametrize(
    ("workflow_pack_id", "model_version", "evaluated_at_utc"),
    [
        ("advisor_brief.pack", "2026-06-01", "2026-07-11T10:00:00Z"),
        ("idea_explanation.pack", "2026-06-02", "2026-07-11T10:00:00Z"),
        ("idea_explanation.pack", "2026-06-01", "2026-09-01T00:00:00Z"),
    ],
)
def test_non_matching_or_expired_entry_is_not_approved(
    workflow_pack_id: str, model_version: str, evaluated_at_utc: str
) -> None:
    decision = _evaluate(
        workflow_pack_id=workflow_pack_id,
        model_version=model_version,
        evaluated_at_utc=evaluated_at_utc,
    )

    assert decision.status == "approval_unverified"
    assert decision.approval_ref is None


def test_stub_execution_remains_test_only_even_when_an_entry_matches() -> None:
    decision = _evaluate(stubbed=True)

    assert decision.status == "test_only"
    assert decision.approval_ref is None


def test_lifecycle_state_is_authoritative() -> None:
    """A demoted entry stops approving immediately - the point of #191."""

    for state in (
        ModelLifecycleState.DEPRECATED,
        ModelLifecycleState.RETIRED,
        ModelLifecycleState.DEGRADED,
        ModelLifecycleState.CATALOGUED,
    ):
        decision = _evaluate(entries=[_entry(lifecycle_state=state)])
        assert decision.status == "approval_unverified", state


def test_operator_promotion_without_windows_is_effective() -> None:
    """An APPROVED entry without validity windows (a governed operator
    promotion) is effective by state; windows are bounds, not prerequisites."""

    decision = _evaluate(
        entries=[
            _entry(
                approved_from_utc=None,
                approved_until_utc=None,
                approval_evidence_refs=["mrm-operator-2026-041"],
                seed_source=ModelCatalogueSeedSource.SETTINGS_LIVE_TEXT,
            )
        ]
    )

    assert decision.status == "approved"
    assert decision.approval_ref == "mrm-operator-2026-041"


def test_entries_without_evidence_or_pack_bindings_never_approve() -> None:
    assert _evaluate(entries=[_entry(approval_evidence_refs=[])]).status == ("approval_unverified")
    assert _evaluate(entries=[_entry(approved_workflow_pack_ids=[])]).status == (
        "approval_unverified"
    )


def test_more_than_one_effective_match_refuses_approval() -> None:
    duplicate = _entry(deployment=None)
    shadow = duplicate.model_copy(update={"entry_id": duplicate.entry_id + ":shadow"})
    decision = _evaluate(entries=[duplicate, shadow])

    assert decision.status == "approval_unverified"
    assert decision.approval_ref is None


@pytest.fixture
def _seeded_catalogue(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    reset_model_catalogue_store_cache()
    monkeypatch.setattr(settings, "provider_mode", "disabled")
    monkeypatch.setattr(
        settings,
        "workflow_run_model_risk_inventory_json",
        json.dumps([APPROVED_INVENTORY_ROW]),
    )
    yield
    reset_model_catalogue_store_cache()


def test_from_catalogue_wrapper_reflects_lifecycle_transitions(
    _seeded_catalogue: None,
) -> None:
    """End to end: the seed mirrors the inventory to an APPROVED row, the
    wrapper approves against it, and a lifecycle demotion flips the outcome -
    impossible under the env-inventory read this issue removed."""

    def _wrapped() -> WorkflowRunModelRiskDecision:
        return evaluate_workflow_run_model_risk_from_catalogue(
            provider_id="text.openai",
            provider_mode="openai",
            model_id="gpt-5.4",
            model_version="2026-06-01",
            workflow_pack_id="idea_explanation.pack",
            evaluated_at_utc="2026-07-11T10:00:00Z",
            stubbed=False,
        )

    assert _wrapped().status == "approved"

    repository = get_model_catalogue_repository()
    entry = repository.get_entry("text.openai:2026-06-01")
    assert entry is not None
    repository.upsert_entry(
        entry.model_copy(update={"lifecycle_state": ModelLifecycleState.DEPRECATED})
    )

    demoted = _wrapped()
    assert demoted.status == "approval_unverified"
    assert demoted.approval_ref is None


@pytest.mark.parametrize(
    ("configured", "message"),
    [
        ("{", "valid governed JSON"),
        (
            json.dumps([APPROVED_INVENTORY_ROW, APPROVED_INVENTORY_ROW]),
            "identities must be unique",
        ),
    ],
)
def test_invalid_inventory_fails_closed_at_seed_time(configured: str, message: str) -> None:
    """The loader's validation is now the SEED-TIME guard: the seed calls
    approved_models(), so a malformed or duplicated inventory fails loud
    before any catalogue row exists."""

    inventory = ConfiguredWorkflowRunModelRiskInventory(
        settings=Settings(workflow_run_model_risk_inventory_json=configured)
    )

    with pytest.raises(ValueError, match=message):
        inventory.approved_models()


def test_inventory_loader_is_referenced_only_by_the_seed() -> None:
    """#191's single-source guard: the env inventory is a seed input, never a
    runtime evaluation source. A new runtime consumer must show up here."""

    src_root = Path(__file__).resolve().parents[2] / "src" / "app"
    referencing = {
        path.relative_to(src_root).as_posix()
        for path in src_root.rglob("*.py")
        if "ConfiguredWorkflowRunModelRiskInventory" in path.read_text(encoding="utf-8")
    }
    assert referencing == {
        "providers/configured_workflow_run_model_risk_inventory.py",
        "services/model_catalogue.py",
    }
