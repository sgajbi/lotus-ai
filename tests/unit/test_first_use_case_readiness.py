from pathlib import Path

from _pytest.monkeypatch import MonkeyPatch

from app.contracts.evals import EvaluationRunSubmissionRequest
from app.contracts.evals import EvaluationApprovalEvidenceState
from app.services.eval_async_execution import run_next_evaluation_execution_job
from app.services.eval_run_submission_service import submit_evaluation_run
from app.services.first_use_case_readiness import (
    _approval_gate_status,
    build_first_use_case_readiness,
)
from app.services.first_use_case_status import build_first_use_case_runtime_status
from app.services.observability_governance import build_observability_governance_status
from app.services.observability_runtime import build_observability_runtime_status
from tests.support.migration_runner import upgrade_database_to_head
from tests.support.observability import build_healthy_ai_surface_supportability_summary
from tests.support.runtime_settings import override_runtime_settings


def test_first_use_case_readiness_reports_staged_only_without_runtime_eval_evidence() -> None:
    readiness = build_first_use_case_readiness()

    assert readiness.use_case_id == "lotus_performance.analytics_commentary.v1"
    assert readiness.downstream_app == "lotus-performance"
    assert readiness.readiness_ready is False
    assert readiness.approval_gate.domain_id == "first_use_case_onboarding"
    assert readiness.approval_gate.evidence_state.value == "STAGED_ONLY"
    assert readiness.required_item_count == 9
    assert readiness.completed_required_item_count == 4
    assert readiness.items[0].status == "READY"
    assert readiness.items[1].status == "READY"
    assert readiness.items[2].status == "FOUNDATION_STAGED"
    assert readiness.items[3].status == "READY"
    assert readiness.items[4].status == "NOT_READY"
    assert readiness.items[5].status == "NOT_READY"
    assert readiness.items[6].status == "NOT_READY"
    assert readiness.items[7].status == "NOT_READY"
    assert readiness.items[8].status == "READY"


def test_first_use_case_readiness_keeps_limited_rollout_blocked_without_durable_review_surfaces() -> (
    None
):
    submit_evaluation_run(
        EvaluationRunSubmissionRequest(
            fixture_id="lotus_performance_first_use_case_examples",
            caller_app="lotus-platform",
            correlation_id="corr-first-use-case-001",
            triggered_by="operator-a",
        )
    )
    run_next_evaluation_execution_job(worker_id="worker-a")

    readiness = build_first_use_case_readiness()

    assert readiness.readiness_ready is False
    assert readiness.approval_gate.evidence_state.value == "RUNTIME_PASS"
    assert readiness.items[2].status == "READY"
    assert readiness.items[4].status == "NOT_READY"
    assert readiness.items[5].status == "NOT_READY"
    assert readiness.items[6].status == "NOT_READY"
    assert readiness.items[7].status == "NOT_READY"
    assert readiness.items[8].status == "READY"


def test_first_use_case_readiness_uses_sql_seeded_lotus_performance_policy(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'first-use-case-readiness.db'}"
    upgrade_database_to_head(database_url)

    with override_runtime_settings(
        access_control_store_mode="sqlalchemy",
        audit_store_mode="sqlalchemy",
        artifact_store_mode="sqlalchemy",
        artifact_object_store_mode="memory",
        database_url=database_url,
    ):
        submit_evaluation_run(
            EvaluationRunSubmissionRequest(
                fixture_id="lotus_performance_first_use_case_examples",
                caller_app="lotus-platform",
                correlation_id="corr-first-use-case-002",
                triggered_by="operator-a",
            )
        )
        run_next_evaluation_execution_job(worker_id="worker-a")
        observability_runtime = build_observability_runtime_status().model_copy(
            update={"ai_surface_supportability": build_healthy_ai_surface_supportability_summary()}
        )
        readiness = build_first_use_case_readiness(
            observability_governance=build_observability_governance_status(
                runtime_status=observability_runtime
            )
        )

    assert readiness.items[0].status == "READY"
    assert readiness.items[4].status == "READY"
    assert readiness.items[5].status == "READY"
    assert readiness.items[6].status == "READY"
    assert readiness.items[7].status == "NOT_READY"
    assert readiness.items[8].status == "READY"
    assert readiness.readiness_ready is False


def test_first_use_case_readiness_maps_all_runtime_gate_states() -> None:
    assert _approval_gate_status(EvaluationApprovalEvidenceState.RUNTIME_PARTIAL) == "PARTIAL"
    assert _approval_gate_status(EvaluationApprovalEvidenceState.RUNTIME_FAIL) == "FAILED"
    assert _approval_gate_status(EvaluationApprovalEvidenceState.RUNTIME_STALE) == "STALE"
    assert _approval_gate_status(EvaluationApprovalEvidenceState.NO_EVIDENCE) == "NOT_READY"


def test_first_use_case_runtime_status_requires_registered_capability_pack(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.first_use_case_status.get_capability_pack_by_id",
        lambda pack_id: None,
    )

    try:
        build_first_use_case_runtime_status()
    except RuntimeError as exc:
        assert "analytics_commentary.pack.v1 capability pack is not registered" in str(exc)
    else:
        raise AssertionError("Expected missing capability pack to raise RuntimeError")
