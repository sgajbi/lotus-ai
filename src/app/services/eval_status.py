from __future__ import annotations

from app.contracts.evals import EvaluationRuntimeStatusResponse
from app.services.deployment_split_routing import (
    resolve_evaluation_async_route,
    resolve_evaluation_submission_route,
)
from app.services.deployment_split_shared import resolve_effective_deployment_split_stage
from app.services.eval_approval_gate_summary import (
    build_first_use_case_approval_gate_summary,
    build_prompt_approval_gate_summary,
    build_provider_approval_gate_summary,
    build_retrieval_approval_gate_summary,
    build_safety_approval_gate_summary,
)
from app.services.eval_catalog import build_evaluation_catalog
from app.services.eval_inventory_summary import summarize_evaluation_inventory
from app.services.eval_run_service import build_evaluation_run_catalog
from app.services.eval_seam_summary import build_evaluation_seam_coverage


def build_evaluation_runtime_status() -> EvaluationRuntimeStatusResponse:
    effective_stage, _ = resolve_effective_deployment_split_stage()
    submission_route = resolve_evaluation_submission_route(effective_stage=effective_stage)
    async_route = resolve_evaluation_async_route(effective_stage=effective_stage)
    catalog = build_evaluation_catalog()
    inventory_summary = summarize_evaluation_inventory(catalog)
    seam_coverage = build_evaluation_seam_coverage()
    run_catalog = build_evaluation_run_catalog()
    latest_run = run_catalog.runs[0] if run_catalog.runs else None
    approval_gates = [
        build_first_use_case_approval_gate_summary(),
        build_prompt_approval_gate_summary(),
        build_retrieval_approval_gate_summary(),
        build_provider_approval_gate_summary(),
        build_safety_approval_gate_summary(),
    ]
    return EvaluationRuntimeStatusResponse(
        service=catalog.service,
        version=catalog.version,
        delivery_phase=catalog.delivery_phase,
        manifest_version=catalog.manifest_version,
        evidence_category_count=inventory_summary.evidence_category_count,
        staged_fixture_count=inventory_summary.staged_fixture_count,
        documented_fixture_count=inventory_summary.documented_fixture_count,
        staged_case_count=inventory_summary.staged_case_count,
        seam_coverage=seam_coverage,
        approval_gates=approval_gates,
        recorded_run_count=run_catalog.run_count,
        runtime_backed_run_count=run_catalog.runtime_backed_run_count,
        historical_run_count=run_catalog.historical_run_count,
        latest_recorded_run_id=run_catalog.latest_run_id,
        latest_recorded_run_status=latest_run.status if latest_run is not None else None,
        evaluation_runner_active=True,
        owning_plane=async_route.owning_plane,
        submission_route_mode=submission_route.route_mode,
        async_execution_route_mode=async_route.route_mode,
        rollback_target_stage=async_route.rollback_target_stage,
        message=(
            "Allowlisted evaluation families now run through the durable async backbone with "
            "persisted attempts, replay-safe case-result history, and runtime-backed approval-gate "
            f"summaries. {submission_route.detail} {async_route.detail}"
        ),
    )
