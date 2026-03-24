from __future__ import annotations

from dataclasses import dataclass

from app.contracts.evals import (
    EvaluationApprovalEvidenceState,
    EvaluationApprovalFixtureSummaryDescriptor,
    EvaluationApprovalGateSummaryDescriptor,
    EvaluationRunRecordSource,
    EvaluationRunStatus,
    EvaluationRunVerdict,
)
from app.evals.fixture_manifest import load_evaluation_fixture_manifest
from app.evals.run_registry import load_evaluation_run_artifacts
from app.repositories.evaluation_runtime_repository import EvaluationRunRecord
from app.services.evaluation_runtime_store import get_evaluation_runtime_store

_PROVIDER_APPROVAL_FIXTURE_IDS = (
    "provider_policy_examples",
    "provider_runtime_examples",
    "provider_failure_mode_examples",
    "provider_operations_examples",
    "provider_degradation_examples",
    "provider_embedding_examples",
)

_RETRIEVAL_APPROVAL_FIXTURE_IDS = (
    "retrieval_citation_examples",
    "retrieval_embedding_examples",
)
_SAFETY_APPROVAL_FIXTURE_IDS = (
    "safety_policy_examples",
    "safety_runtime_examples",
)
_PROMPT_APPROVAL_FIXTURE_IDS = (
    "prompt_promotion_examples",
    "prompt_rollback_examples",
)
_FIRST_USE_CASE_APPROVAL_FIXTURE_IDS = ("lotus_performance_first_use_case_examples",)
_ANALYTICS_COMMENTARY_PACK_APPROVAL_FIXTURE_IDS = ("capability_pack_analytics_commentary_examples",)
_DECISION_EXPLANATION_PACK_APPROVAL_FIXTURE_IDS = ("capability_pack_decision_explanation_examples",)


@dataclass(frozen=True)
class _FixtureApprovalSummary:
    fixture_id: str
    state: EvaluationApprovalEvidenceState
    runtime_run: EvaluationRunRecord | None
    notes: str


def build_provider_approval_gate_summary() -> EvaluationApprovalGateSummaryDescriptor:
    return _build_approval_gate_summary(
        domain_id="provider_execution",
        domain_label="Provider Execution",
        required_fixture_ids=_PROVIDER_APPROVAL_FIXTURE_IDS,
    )


def build_retrieval_approval_gate_summary() -> EvaluationApprovalGateSummaryDescriptor:
    return _build_approval_gate_summary(
        domain_id="retrieval_execution",
        domain_label="Retrieval Execution",
        required_fixture_ids=_RETRIEVAL_APPROVAL_FIXTURE_IDS,
    )


def build_safety_approval_gate_summary() -> EvaluationApprovalGateSummaryDescriptor:
    return _build_approval_gate_summary(
        domain_id="safety_enforcement",
        domain_label="Safety Enforcement",
        required_fixture_ids=_SAFETY_APPROVAL_FIXTURE_IDS,
    )


def build_prompt_approval_gate_summary() -> EvaluationApprovalGateSummaryDescriptor:
    return _build_approval_gate_summary(
        domain_id="prompt_rollout",
        domain_label="Prompt Rollout",
        required_fixture_ids=_PROMPT_APPROVAL_FIXTURE_IDS,
    )


def build_first_use_case_approval_gate_summary() -> EvaluationApprovalGateSummaryDescriptor:
    return _build_approval_gate_summary(
        domain_id="first_use_case_onboarding",
        domain_label="First Use-Case Onboarding",
        required_fixture_ids=_FIRST_USE_CASE_APPROVAL_FIXTURE_IDS,
    )


def build_analytics_commentary_pack_approval_gate_summary() -> (
    EvaluationApprovalGateSummaryDescriptor
):
    return _build_approval_gate_summary(
        domain_id="analytics_commentary_pack",
        domain_label="Analytics Commentary Pack",
        required_fixture_ids=_ANALYTICS_COMMENTARY_PACK_APPROVAL_FIXTURE_IDS,
    )


def build_decision_explanation_pack_approval_gate_summary() -> (
    EvaluationApprovalGateSummaryDescriptor
):
    return _build_approval_gate_summary(
        domain_id="decision_explanation_pack",
        domain_label="Decision Explanation Pack",
        required_fixture_ids=_DECISION_EXPLANATION_PACK_APPROVAL_FIXTURE_IDS,
    )


def build_named_approval_gate_summary(
    *,
    domain_id: str,
    domain_label: str,
    required_fixture_ids: tuple[str, ...],
) -> EvaluationApprovalGateSummaryDescriptor:
    return _build_approval_gate_summary(
        domain_id=domain_id,
        domain_label=domain_label,
        required_fixture_ids=required_fixture_ids,
    )


def _build_approval_gate_summary(
    *,
    domain_id: str,
    domain_label: str,
    required_fixture_ids: tuple[str, ...],
) -> EvaluationApprovalGateSummaryDescriptor:
    manifest_version = load_evaluation_fixture_manifest().manifest_version
    fixture_summaries = [
        _summarize_fixture_approval(fixture_id=fixture_id, manifest_version=manifest_version)
        for fixture_id in required_fixture_ids
    ]
    historical_runs = [
        run
        for run in load_evaluation_run_artifacts()
        if run.record_source == EvaluationRunRecordSource.STAGED_ARTIFACT
        and any(
            fixture_id in seam.fixture_ids
            for seam in run.seam_coverage
            for fixture_id in required_fixture_ids
        )
    ]
    historical_runs.sort(key=lambda item: item.recorded_at, reverse=True)
    latest_historical_baseline_run_id = historical_runs[0].run_id if historical_runs else None

    evidence_state = _derive_domain_state(fixture_summaries=fixture_summaries)
    latest_runtime_run = max(
        (summary.runtime_run for summary in fixture_summaries if summary.runtime_run is not None),
        key=lambda item: item.submitted_at,
        default=None,
    )
    runtime_backed_fixture_count = sum(
        1
        for summary in fixture_summaries
        if summary.state
        in {
            EvaluationApprovalEvidenceState.RUNTIME_PASS,
            EvaluationApprovalEvidenceState.RUNTIME_FAIL,
            EvaluationApprovalEvidenceState.RUNTIME_IN_PROGRESS,
            EvaluationApprovalEvidenceState.RUNTIME_STALE,
        }
    )
    notes = _build_domain_notes(
        domain_label=domain_label,
        evidence_state=evidence_state,
        fixture_summaries=fixture_summaries,
        latest_historical_baseline_run_id=latest_historical_baseline_run_id,
    )
    return EvaluationApprovalGateSummaryDescriptor(
        domain_id=domain_id,
        domain_label=domain_label,
        approval_ready=evidence_state == EvaluationApprovalEvidenceState.RUNTIME_PASS,
        evidence_state=evidence_state,
        required_fixture_count=len(required_fixture_ids),
        runtime_backed_fixture_count=runtime_backed_fixture_count,
        latest_runtime_run_id=None if latest_runtime_run is None else latest_runtime_run.run_id,
        latest_runtime_recorded_at=(
            None if latest_runtime_run is None else latest_runtime_run.submitted_at
        ),
        latest_historical_baseline_run_id=latest_historical_baseline_run_id,
        fixture_summaries=[
            EvaluationApprovalFixtureSummaryDescriptor(
                fixture_id=summary.fixture_id,
                latest_runtime_run_id=(
                    None if summary.runtime_run is None else summary.runtime_run.run_id
                ),
                latest_runtime_recorded_at=(
                    None if summary.runtime_run is None else summary.runtime_run.submitted_at
                ),
                latest_runtime_status=(
                    None
                    if summary.runtime_run is None
                    else EvaluationRunStatus(summary.runtime_run.lifecycle_status)
                ),
                latest_runtime_verdict=(
                    None
                    if summary.runtime_run is None or summary.runtime_run.verdict is None
                    else EvaluationRunVerdict(summary.runtime_run.verdict)
                ),
                evidence_state=summary.state,
                notes=summary.notes,
            )
            for summary in fixture_summaries
        ],
        notes=notes,
    )


def _summarize_fixture_approval(
    *,
    fixture_id: str,
    manifest_version: str,
) -> _FixtureApprovalSummary:
    runs = [
        run for run in get_evaluation_runtime_store().list_runs() if run.fixture_id == fixture_id
    ]
    runs.sort(key=lambda item: item.submitted_at, reverse=True)
    latest_runtime_run = runs[0] if runs else None
    if latest_runtime_run is None:
        return _FixtureApprovalSummary(
            fixture_id=fixture_id,
            state=EvaluationApprovalEvidenceState.STAGED_ONLY,
            runtime_run=None,
            notes="No runtime-backed evaluation run has been recorded for this fixture family yet.",
        )
    if latest_runtime_run.manifest_version != manifest_version:
        return _FixtureApprovalSummary(
            fixture_id=fixture_id,
            state=EvaluationApprovalEvidenceState.RUNTIME_STALE,
            runtime_run=latest_runtime_run,
            notes=(
                f"Latest runtime-backed evaluation run '{latest_runtime_run.run_id}' uses "
                f"manifest version '{latest_runtime_run.manifest_version}' instead of the current "
                f"'{manifest_version}'."
            ),
        )
    if latest_runtime_run.lifecycle_status in {"QUEUED", "CLAIMED", "RUNNING"}:
        return _FixtureApprovalSummary(
            fixture_id=fixture_id,
            state=EvaluationApprovalEvidenceState.RUNTIME_IN_PROGRESS,
            runtime_run=latest_runtime_run,
            notes=(
                f"Latest runtime-backed evaluation run '{latest_runtime_run.run_id}' is still "
                f"{latest_runtime_run.lifecycle_status.lower()}."
            ),
        )
    if latest_runtime_run.lifecycle_status == "COMPLETED" and latest_runtime_run.verdict == "PASS":
        return _FixtureApprovalSummary(
            fixture_id=fixture_id,
            state=EvaluationApprovalEvidenceState.RUNTIME_PASS,
            runtime_run=latest_runtime_run,
            notes=(
                f"Latest runtime-backed evaluation run '{latest_runtime_run.run_id}' passed under "
                "the current fixture manifest."
            ),
        )
    return _FixtureApprovalSummary(
        fixture_id=fixture_id,
        state=EvaluationApprovalEvidenceState.RUNTIME_FAIL,
        runtime_run=latest_runtime_run,
        notes=(
            f"Latest runtime-backed evaluation run '{latest_runtime_run.run_id}' did not produce "
            "an approval-satisfying passing verdict."
        ),
    )


def _derive_domain_state(
    *,
    fixture_summaries: list[_FixtureApprovalSummary],
) -> EvaluationApprovalEvidenceState:
    states = {summary.state for summary in fixture_summaries}
    if states == {EvaluationApprovalEvidenceState.RUNTIME_PASS}:
        return EvaluationApprovalEvidenceState.RUNTIME_PASS
    if EvaluationApprovalEvidenceState.RUNTIME_FAIL in states:
        return EvaluationApprovalEvidenceState.RUNTIME_FAIL
    if EvaluationApprovalEvidenceState.RUNTIME_IN_PROGRESS in states:
        return EvaluationApprovalEvidenceState.RUNTIME_IN_PROGRESS
    if EvaluationApprovalEvidenceState.RUNTIME_STALE in states:
        return EvaluationApprovalEvidenceState.RUNTIME_STALE
    if EvaluationApprovalEvidenceState.RUNTIME_PASS in states:
        return EvaluationApprovalEvidenceState.RUNTIME_PARTIAL
    if states == {EvaluationApprovalEvidenceState.STAGED_ONLY}:
        return EvaluationApprovalEvidenceState.STAGED_ONLY
    return EvaluationApprovalEvidenceState.NO_EVIDENCE


def _build_domain_notes(
    *,
    domain_label: str,
    evidence_state: EvaluationApprovalEvidenceState,
    fixture_summaries: list[_FixtureApprovalSummary],
    latest_historical_baseline_run_id: str | None,
) -> list[str]:
    if evidence_state == EvaluationApprovalEvidenceState.RUNTIME_PASS:
        return [
            f"{domain_label} approval posture is currently backed by passing runtime-produced evaluation evidence.",
            "Current runtime-backed fixture coverage satisfies all governed approval fixture families.",
        ]
    if evidence_state == EvaluationApprovalEvidenceState.RUNTIME_FAIL:
        failing_fixtures = [
            summary.fixture_id
            for summary in fixture_summaries
            if summary.state == EvaluationApprovalEvidenceState.RUNTIME_FAIL
        ]
        return [
            f"{domain_label} approval posture is blocked by failing runtime-backed evaluation evidence.",
            f"Failing fixture families: {', '.join(sorted(failing_fixtures))}.",
        ]
    if evidence_state == EvaluationApprovalEvidenceState.RUNTIME_IN_PROGRESS:
        return [
            f"{domain_label} approval posture is waiting on in-flight runtime-backed evaluation execution.",
            "Staged historical baselines remain visible, but they do not satisfy current approval posture while runtime execution is in progress.",
        ]
    if evidence_state == EvaluationApprovalEvidenceState.RUNTIME_STALE:
        return [
            f"{domain_label} approval posture is blocked by stale runtime-backed evaluation evidence.",
            "A newer fixture manifest exists than the latest runtime-backed evaluation result.",
        ]
    if evidence_state == EvaluationApprovalEvidenceState.RUNTIME_PARTIAL:
        covered = [
            summary.fixture_id
            for summary in fixture_summaries
            if summary.state == EvaluationApprovalEvidenceState.RUNTIME_PASS
        ]
        return [
            f"{domain_label} approval posture has partial runtime-backed evaluation coverage but is not yet complete.",
            f"Runtime-backed passing fixtures: {', '.join(sorted(covered))}.",
        ]
    if latest_historical_baseline_run_id is not None:
        return [
            f"{domain_label} approval posture still relies on staged historical baseline '{latest_historical_baseline_run_id}'.",
            "Historical artifacts remain visible for continuity, but they do not satisfy current runtime-backed approval requirements.",
        ]
    return [
        f"{domain_label} approval posture has no historical or runtime-backed evaluation evidence yet."
    ]
