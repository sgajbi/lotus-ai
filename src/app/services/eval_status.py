from __future__ import annotations

from app.contracts.evals import EvaluationRuntimeStatusResponse
from app.services.eval_catalog import build_evaluation_catalog
from app.services.eval_inventory_summary import summarize_evaluation_inventory
from app.services.eval_run_service import build_evaluation_run_catalog
from app.services.eval_seam_summary import build_evaluation_seam_coverage


def build_evaluation_runtime_status() -> EvaluationRuntimeStatusResponse:
    catalog = build_evaluation_catalog()
    inventory_summary = summarize_evaluation_inventory(catalog)
    seam_coverage = build_evaluation_seam_coverage()
    run_catalog = build_evaluation_run_catalog()
    latest_run = run_catalog.runs[0] if run_catalog.runs else None
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
        recorded_run_count=run_catalog.run_count,
        latest_recorded_run_id=run_catalog.latest_run_id,
        latest_recorded_run_status=latest_run.status if latest_run is not None else None,
        evaluation_runner_active=False,
        message=(
            "Evaluation assets are cataloged and partially staged, but no live evaluation runner "
            "is active in the foundation phase."
        ),
    )
