from app.contracts.tasks import (
    CallerMetadata,
    TaskContextEnvelope,
    TaskExecutionRequest,
    TaskInputMode,
)
from app.services.capability_pack_activation_readiness import (
    build_capability_pack_activation_readiness,
)
from app.services.capability_pack_governance import (
    build_capability_pack_catalog_governance_status,
    build_capability_pack_governance_status,
)
from app.services.capability_pack_observability import (
    build_capability_pack_observability_summary,
)
from app.services.capability_pack_quality_gates import build_capability_pack_approval_gate
from app.services.capability_pack_runbook_readiness import (
    build_capability_pack_runbook_readiness,
)
from app.services.eval_async_execution import run_next_evaluation_execution_job
from app.services.eval_run_submission_service import submit_evaluation_run
from app.services.task_executor import execute_task
from app.contracts.evals import EvaluationRunSubmissionRequest


def test_analytics_commentary_pack_governance_reports_blocked_before_runtime_quality_pass() -> None:
    activation = build_capability_pack_activation_readiness(pack_id="analytics_commentary.pack.v1")
    runbook = build_capability_pack_runbook_readiness(pack_id="analytics_commentary.pack.v1")
    governance = build_capability_pack_governance_status(pack_id="analytics_commentary.pack.v1")

    assert activation.activation_ready is False
    assert activation.items[0].item_id == "runtime_quality_gate"
    assert runbook.runbook_ready is False
    assert governance.governance_ready is False
    assert governance.blocking_area_count == 2


def test_decision_explanation_pack_governance_reports_missing_anchor_and_runbook() -> None:
    observability = build_capability_pack_observability_summary(
        pack_id="decision_explanation.pack.v1"
    )
    governance = build_capability_pack_governance_status(pack_id="decision_explanation.pack.v1")

    assert observability.observability_ready is True
    assert observability.sampled_audit_record_count == 0
    assert governance.governance_ready is False
    assert governance.blocking_area_count >= 2


def test_analytics_commentary_pack_observability_summarizes_bounded_usage() -> None:
    execute_task(
        TaskExecutionRequest(
            task_id="explain.v1",
            input_mode=TaskInputMode.STRUCTURED_CONTEXT,
            caller=CallerMetadata(
                caller_app="lotus-performance",
                correlation_id="corr-pack-obs-001",
                tenant_id="tenant-sg-001",
            ),
            context=TaskContextEnvelope(
                summary="Analytics commentary pack observability coverage.",
                payload={
                    "analysis_scope": "monthly_contribution_change",
                    "metric_deltas": [{"metric_id": "active_return_bps", "delta_bps": 33}],
                    "material_findings": ["Allocation shifts drove the change."],
                },
                source_refs=[],
            ),
        )
    )

    summary = build_capability_pack_observability_summary(pack_id="analytics_commentary.pack.v1")

    assert summary.observability_ready is True
    assert summary.sampled_audit_record_count >= 1
    assert "lotus-performance" in summary.observed_caller_apps


def test_analytics_commentary_pack_governance_can_become_ready_after_runtime_quality_pass() -> None:
    submit_evaluation_run(
        EvaluationRunSubmissionRequest(
            fixture_id="capability_pack_analytics_commentary_examples",
            caller_app="lotus-platform",
            correlation_id="corr-pack-governance-001",
            triggered_by="operator-a",
        )
    )
    run_next_evaluation_execution_job(worker_id="worker-a")

    governance = build_capability_pack_governance_status(pack_id="analytics_commentary.pack.v1")
    catalog_governance = build_capability_pack_catalog_governance_status()

    assert governance.activation_readiness.activation_ready is True
    assert governance.observability.observability_ready is True
    # The runtime quality gate passed, but governance now tells the honest
    # runbook truth (issue #154): the operational runbook items are
    # DOCUMENTED_ONLY, not enforced controls, so the pack does not become
    # governance-ready until the catalog records them as ENFORCED with
    # evidence.
    assert governance.runbook_readiness.runbook_ready is False
    assert governance.governance_ready is False
    assert catalog_governance.ready_pack_count == 0
    assert catalog_governance.blocking_pack_count == 2


def test_decision_explanation_pack_activation_and_runbook_surfaces_remain_blocked() -> None:
    activation = build_capability_pack_activation_readiness(pack_id="decision_explanation.pack.v1")
    runbook = build_capability_pack_runbook_readiness(pack_id="decision_explanation.pack.v1")

    assert activation.activation_ready is False
    assert activation.completed_required_item_count == 1
    assert any(
        item.item_id == "downstream_anchor" and item.status == "BLOCKED"
        for item in activation.items
    )
    assert runbook.runbook_ready is False
    assert any(
        item.item_id == "downstream_owner_documented" and item.status == "BLOCKED"
        for item in runbook.items
    )


def test_capability_pack_services_reject_unknown_pack_ids() -> None:
    builders = (
        lambda: build_capability_pack_observability_summary(pack_id="unknown.pack.v1"),
        lambda: build_capability_pack_activation_readiness(pack_id="unknown.pack.v1"),
        lambda: build_capability_pack_runbook_readiness(pack_id="unknown.pack.v1"),
        lambda: build_capability_pack_approval_gate(pack_id="unknown.pack.v1"),
        lambda: build_capability_pack_governance_status(pack_id="unknown.pack.v1"),
    )

    for builder in builders:
        try:
            builder()
        except ValueError as exc:
            assert "Unknown capability pack" in str(exc)
        else:
            raise AssertionError("Expected unknown capability pack lookup to fail")
