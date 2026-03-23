from app.contracts.evals import EvaluationRunSubmissionRequest
from app.repositories.evaluation_runtime_repository import EvaluationRunRecord
from app.services.eval_approval_gate_summary import (
    build_provider_approval_gate_summary,
    build_retrieval_approval_gate_summary,
)
from app.services.eval_async_execution import run_next_evaluation_execution_job
from app.services.eval_run_submission_service import submit_evaluation_run
from app.services.evaluation_runtime_store import get_evaluation_runtime_store


def test_provider_approval_gate_reports_staged_only_without_runtime_runs() -> None:
    summary = build_provider_approval_gate_summary()

    assert summary.domain_id == "provider_execution"
    assert summary.evidence_state.value == "STAGED_ONLY"
    assert summary.approval_ready is False
    assert summary.required_fixture_count == 5
    assert summary.runtime_backed_fixture_count == 0
    assert summary.latest_historical_baseline_run_id == "foundation_eval_2026_03_22_001"


def test_provider_approval_gate_reports_partial_runtime_coverage() -> None:
    submit_evaluation_run(
        EvaluationRunSubmissionRequest(
            fixture_id="provider_policy_examples",
            caller_app="lotus-platform",
            correlation_id="corr-provider-approval-partial-001",
            triggered_by="operator-a",
        )
    )
    run_next_evaluation_execution_job(worker_id="worker-a")

    summary = build_provider_approval_gate_summary()

    assert summary.evidence_state.value == "RUNTIME_PARTIAL"
    assert summary.approval_ready is False
    assert summary.runtime_backed_fixture_count == 1
    assert summary.fixture_summaries[0].evidence_state.value == "RUNTIME_PASS"
    assert summary.fixture_summaries[1].evidence_state.value == "STAGED_ONLY"


def test_provider_approval_gate_reports_runtime_pass_when_all_required_fixtures_pass() -> None:
    for fixture_id in (
        "provider_policy_examples",
        "provider_runtime_examples",
        "provider_failure_mode_examples",
        "provider_operations_examples",
        "provider_degradation_examples",
    ):
        submit_evaluation_run(
            EvaluationRunSubmissionRequest(
                fixture_id=fixture_id,
                caller_app="lotus-platform",
                correlation_id=f"corr-{fixture_id}",
                triggered_by="operator-a",
            )
        )
        run_next_evaluation_execution_job(worker_id="worker-a")

    summary = build_provider_approval_gate_summary()

    assert summary.evidence_state.value == "RUNTIME_PASS"
    assert summary.approval_ready is True
    assert summary.runtime_backed_fixture_count == 5
    assert all(item.evidence_state.value == "RUNTIME_PASS" for item in summary.fixture_summaries)


def test_retrieval_approval_gate_reports_runtime_stale_for_old_manifest_version() -> None:
    get_evaluation_runtime_store().save_run(
        EvaluationRunRecord(
            run_id="runtime_eval_retrieval_stale_001",
            fixture_id="retrieval_citation_examples",
            manifest_version="foundation.v0",
            lifecycle_status="COMPLETED",
            triggered_by="operator-a",
            submitted_at="2026-03-23T10:00:00Z",
            async_job_id="async_eval_retrieval_stale_001",
            latest_message="Stale retrieval runtime run.",
            verdict="PASS",
            case_count=2,
        )
    )

    summary = build_retrieval_approval_gate_summary()

    assert summary.domain_id == "retrieval_execution"
    assert summary.evidence_state.value == "RUNTIME_STALE"
    assert summary.approval_ready is False
    assert summary.runtime_backed_fixture_count == 1
    assert summary.fixture_summaries[0].evidence_state.value == "RUNTIME_STALE"


def test_provider_approval_gate_reports_runtime_fail_for_terminal_non_passing_run() -> None:
    get_evaluation_runtime_store().save_run(
        EvaluationRunRecord(
            run_id="runtime_eval_provider_fail_001",
            fixture_id="provider_policy_examples",
            manifest_version="foundation.v1",
            lifecycle_status="FAILED",
            triggered_by="operator-a",
            submitted_at="2026-03-23T12:00:00Z",
            async_job_id="async_eval_provider_fail_001",
            latest_message="Provider policy evaluation failed.",
            verdict=None,
            case_count=2,
        )
    )

    summary = build_provider_approval_gate_summary()

    assert summary.evidence_state.value == "RUNTIME_FAIL"
    assert summary.approval_ready is False
    assert summary.fixture_summaries[0].evidence_state.value == "RUNTIME_FAIL"


def test_retrieval_approval_gate_reports_runtime_in_progress() -> None:
    get_evaluation_runtime_store().save_run(
        EvaluationRunRecord(
            run_id="runtime_eval_retrieval_in_progress_001",
            fixture_id="retrieval_citation_examples",
            manifest_version="foundation.v1",
            lifecycle_status="RUNNING",
            triggered_by="operator-a",
            submitted_at="2026-03-23T13:00:00Z",
            async_job_id="async_eval_retrieval_in_progress_001",
            latest_message="Retrieval citation evaluation running.",
            verdict=None,
            case_count=2,
        )
    )

    summary = build_retrieval_approval_gate_summary()

    assert summary.evidence_state.value == "RUNTIME_IN_PROGRESS"
    assert summary.approval_ready is False
    assert summary.fixture_summaries[0].evidence_state.value == "RUNTIME_IN_PROGRESS"
