from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.contracts.workflow_run_model_risk import ApprovedWorkflowRunModel


@dataclass(frozen=True)
class WorkflowRunModelRiskDecision:
    status: str
    approval_ref: str | None


class WorkflowRunModelRiskInventory(Protocol):
    def approved_models(self) -> list[ApprovedWorkflowRunModel]: ...


def evaluate_workflow_run_model_risk(
    *,
    inventory: WorkflowRunModelRiskInventory,
    provider_id: str,
    provider_mode: str,
    model_id: str,
    model_version: str,
    workflow_pack_id: str,
    evaluated_at_utc: str,
    stubbed: bool,
) -> WorkflowRunModelRiskDecision:
    if stubbed:
        return WorkflowRunModelRiskDecision(status="test_only", approval_ref=None)
    evaluated_at = _timestamp(evaluated_at_utc, "model-risk evaluation time")
    matches = [
        model
        for model in inventory.approved_models()
        if model.provider_id == provider_id
        and model.provider_mode == provider_mode
        and model.model_id == model_id
        and model.model_version == model_version
        and workflow_pack_id in model.workflow_pack_ids
        and _is_effective(model=model, evaluated_at=evaluated_at)
    ]
    if len(matches) != 1:
        return WorkflowRunModelRiskDecision(status="approval_unverified", approval_ref=None)
    return WorkflowRunModelRiskDecision(status="approved", approval_ref=matches[0].approval_ref)


def _is_effective(*, model: ApprovedWorkflowRunModel, evaluated_at: datetime) -> bool:
    approved_from = _timestamp(model.approved_from_utc, "model approval start")
    approved_until = (
        _timestamp(model.approved_until_utc, "model approval end")
        if model.approved_until_utc is not None
        else None
    )
    return approved_from <= evaluated_at and (
        approved_until is None or evaluated_at < approved_until
    )


def _timestamp(value: str, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{label} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")
    return parsed
