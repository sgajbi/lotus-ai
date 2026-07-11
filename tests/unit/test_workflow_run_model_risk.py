import json

import pytest

from app.config import Settings
from app.providers.configured_workflow_run_model_risk_inventory import (
    ConfiguredWorkflowRunModelRiskInventory,
)
from app.services.workflow_run_model_risk import (
    WorkflowRunModelRiskDecision,
    evaluate_workflow_run_model_risk,
)


APPROVED_MODEL: dict[str, object] = {
    "provider_id": "text.openai",
    "provider_mode": "openai",
    "model_id": "gpt-5.4",
    "model_version": "2026-06-01",
    "workflow_pack_ids": ["idea_explanation.pack"],
    "approval_ref": "model-risk://lotus-ai/gpt-5.4/2026-06-01",
    "approved_from_utc": "2026-06-01T00:00:00Z",
    "approved_until_utc": "2026-09-01T00:00:00Z",
}


def _inventory(models: list[dict[str, object]]) -> ConfiguredWorkflowRunModelRiskInventory:
    return ConfiguredWorkflowRunModelRiskInventory(
        settings=Settings(workflow_run_model_risk_inventory_json=json.dumps(models))
    )


def _evaluate(
    *,
    inventory: ConfiguredWorkflowRunModelRiskInventory | None = None,
    workflow_pack_id: str = "idea_explanation.pack",
    model_version: str = "2026-06-01",
    evaluated_at_utc: str = "2026-07-11T10:00:00Z",
    stubbed: bool = False,
) -> WorkflowRunModelRiskDecision:
    return evaluate_workflow_run_model_risk(
        inventory=inventory or _inventory([APPROVED_MODEL]),
        provider_id="text.openai",
        provider_mode="openai",
        model_id="gpt-5.4",
        model_version=model_version,
        workflow_pack_id=workflow_pack_id,
        evaluated_at_utc=evaluated_at_utc,
        stubbed=stubbed,
    )


def test_exact_effective_model_inventory_match_is_approved() -> None:
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
def test_non_matching_or_expired_model_is_not_approved(
    workflow_pack_id: str, model_version: str, evaluated_at_utc: str
) -> None:
    decision = _evaluate(
        workflow_pack_id=workflow_pack_id,
        model_version=model_version,
        evaluated_at_utc=evaluated_at_utc,
    )

    assert decision.status == "approval_unverified"
    assert decision.approval_ref is None


def test_stub_execution_remains_test_only_even_when_inventory_matches() -> None:
    decision = _evaluate(stubbed=True)

    assert decision.status == "test_only"
    assert decision.approval_ref is None


@pytest.mark.parametrize(
    ("configured", "message"),
    [
        ("{", "valid governed JSON"),
        (json.dumps([APPROVED_MODEL, APPROVED_MODEL]), "identities must be unique"),
    ],
)
def test_invalid_model_inventory_fails_closed(configured: str, message: str) -> None:
    inventory = ConfiguredWorkflowRunModelRiskInventory(
        settings=Settings(workflow_run_model_risk_inventory_json=configured)
    )

    with pytest.raises(ValueError, match=message):
        inventory.approved_models()
