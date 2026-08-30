"""Model-risk evaluation for workflow runs, sourced from the governed catalogue.

Issue #191: the catalogue (#175) is the single source of model identity and
approval truth. Evaluation matches the executing identity against APPROVED
catalogue rows - the rows the seed mirrors from the model-risk inventory and
the rows operators promote through governed lifecycle transitions. The env
inventory remains a seed-time input only; it is never read at evaluation time.

Semantics preserved from the inventory era: exactly one effective match is
`approved` (carrying its approval reference); anything else on a live path is
`approval_unverified`; stub executions are `test_only`. Validity windows bound
an approval when present; an APPROVED entry without a window (an operator
promotion) is effective by virtue of its lifecycle state - the state machine
is authoritative, windows are additional bounds.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.contracts.model_catalogue import ModelCatalogueEntry, ModelLifecycleState
from app.services.model_catalogue_store import get_model_catalogue_repository


@dataclass(frozen=True)
class WorkflowRunModelRiskDecision:
    status: str
    approval_ref: str | None


def evaluate_workflow_run_model_risk(
    *,
    entries: list[ModelCatalogueEntry],
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
        entry
        for entry in entries
        if entry.lifecycle_state is ModelLifecycleState.APPROVED
        and entry.provider_id == provider_id
        and entry.provider_mode == provider_mode
        and entry.model_family == model_id
        and entry.model_revision == model_version
        and workflow_pack_id in entry.approved_workflow_pack_ids
        and entry.approval_evidence_refs
        and _is_effective(entry=entry, evaluated_at=evaluated_at)
    ]
    if len(matches) != 1:
        return WorkflowRunModelRiskDecision(status="approval_unverified", approval_ref=None)
    return WorkflowRunModelRiskDecision(
        status="approved",
        approval_ref=matches[0].approval_evidence_refs[-1],
    )


def evaluate_workflow_run_model_risk_from_catalogue(
    *,
    provider_id: str,
    provider_mode: str,
    model_id: str,
    model_version: str,
    workflow_pack_id: str,
    evaluated_at_utc: str,
    stubbed: bool,
) -> WorkflowRunModelRiskDecision:
    # Imported lazily to keep this module import-light for pure evaluation use.
    from app.services.model_catalogue import ensure_model_catalogue_seeded

    ensure_model_catalogue_seeded()
    return evaluate_workflow_run_model_risk(
        entries=get_model_catalogue_repository().list_entries(),
        provider_id=provider_id,
        provider_mode=provider_mode,
        model_id=model_id,
        model_version=model_version,
        workflow_pack_id=workflow_pack_id,
        evaluated_at_utc=evaluated_at_utc,
        stubbed=stubbed,
    )


def _is_effective(*, entry: ModelCatalogueEntry, evaluated_at: datetime) -> bool:
    if entry.approved_from_utc is not None:
        approved_from = _timestamp(entry.approved_from_utc, "model approval start")
        if approved_from > evaluated_at:
            return False
    if entry.approved_until_utc is not None:
        approved_until = _timestamp(entry.approved_until_utc, "model approval end")
        if evaluated_at >= approved_until:
            return False
    return True


def _timestamp(value: str, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{label} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")
    return parsed
