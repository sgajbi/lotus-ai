from __future__ import annotations

from fastapi import HTTPException, status

from app.config import settings
from app.contracts.evals import (
    EvaluationRunArtifactDescriptor,
    EvaluationCaseOutcome,
    EvaluationCaseResultDescriptor,
    EvaluationRunRecordSource,
    EvaluationRunCatalogResponse,
    EvaluationRunDetailResponse,
    EvaluationRunAttemptDescriptor,
    EvaluationRunVerdict,
    EvaluationSeamCoverageDescriptor,
    EvaluationRunStatus,
)
from app.evals.fixture_manifest import load_evaluation_fixture_manifest
from app.evals.run_registry import load_evaluation_run_artifacts
from app.repositories.evaluation_runtime_repository import (
    EvaluationCaseResultRecord,
    EvaluationRunAttemptRecord,
    EvaluationRunRecord,
)
from app.services.artifact_payloads import load_artifact_descriptors
from app.services.eval_seam_summary import SEAM_FIXTURE_MAP
from app.services.evaluation_runtime_store import get_evaluation_runtime_store

_FIXTURE_SEAM_LOOKUP = {
    fixture_id: seam_id
    for seam_id, fixture_ids in SEAM_FIXTURE_MAP.items()
    for fixture_id in fixture_ids
}


def build_evaluation_run_catalog() -> EvaluationRunCatalogResponse:
    runs = _list_evaluation_runs()
    latest_run_id = runs[0].run_id if runs else None
    status_counts = {
        status: sum(1 for run in runs if run.status == status) for status in EvaluationRunStatus
    }
    return EvaluationRunCatalogResponse(
        service=settings.service_name,
        version=settings.service_version,
        delivery_phase=settings.delivery_phase,
        run_count=len(runs),
        latest_run_id=latest_run_id,
        runtime_backed_run_count=sum(
            1 for run in runs if run.record_source == EvaluationRunRecordSource.RUNTIME_STATE
        ),
        historical_run_count=sum(
            1 for run in runs if run.record_source == EvaluationRunRecordSource.STAGED_ARTIFACT
        ),
        status_counts=status_counts,
        runs=runs,
    )


def build_evaluation_run_detail(*, run_id: str) -> EvaluationRunDetailResponse:
    run = next((item for item in _list_evaluation_runs() if item.run_id == run_id), None)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evaluation run '{run_id}' was not found.",
        )
    return EvaluationRunDetailResponse(
        service=settings.service_name,
        version=settings.service_version,
        delivery_phase=settings.delivery_phase,
        run=run,
        attempts=(
            []
            if run.record_source != EvaluationRunRecordSource.RUNTIME_STATE
            else [
                _map_runtime_attempt(item)
                for item in get_evaluation_runtime_store().list_attempts(run_id=run_id)
            ]
        ),
        case_results=(
            []
            if run.record_source != EvaluationRunRecordSource.RUNTIME_STATE
            else [
                _map_runtime_case_result(item)
                for item in get_evaluation_runtime_store().list_case_results(run_id=run_id)
            ]
        ),
    )


def _list_evaluation_runs() -> list[EvaluationRunArtifactDescriptor]:
    runtime_runs = [
        _map_runtime_evaluation_run(record) for record in get_evaluation_runtime_store().list_runs()
    ]
    historical_runs = load_evaluation_run_artifacts()
    return sorted(runtime_runs + historical_runs, key=lambda run: run.recorded_at, reverse=True)


def _map_runtime_evaluation_run(record: EvaluationRunRecord) -> EvaluationRunArtifactDescriptor:
    fixture_manifest = load_evaluation_fixture_manifest()
    fixture_descriptor = next(
        fixture
        for fixture in fixture_manifest.fixture_families
        if fixture.fixture_id == record.fixture_id
    )
    seam_id = _FIXTURE_SEAM_LOOKUP.get(record.fixture_id, "task_execution")
    return EvaluationRunArtifactDescriptor(
        run_id=record.run_id,
        recorded_at=record.submitted_at,
        status=EvaluationRunStatus(record.lifecycle_status),
        record_source=EvaluationRunRecordSource.RUNTIME_STATE,
        manifest_version=record.manifest_version,
        fixture_id=record.fixture_id,
        async_job_id=record.async_job_id,
        triggered_by=record.triggered_by,
        staged_fixture_count=1,
        staged_case_count=record.case_count,
        seam_coverage=[
            EvaluationSeamCoverageDescriptor(
                seam_id=seam_id,
                fixture_ids=[record.fixture_id],
                staged_fixture_count=1,
                staged_case_count=fixture_descriptor.case_count,
            )
        ],
        notes=record.latest_message,
    )


def _map_runtime_attempt(record: EvaluationRunAttemptRecord) -> EvaluationRunAttemptDescriptor:
    return EvaluationRunAttemptDescriptor(
        attempt_id=record.attempt_id,
        attempt_number=record.attempt_number,
        status=EvaluationRunStatus(record.lifecycle_status),
        started_at=record.started_at,
        completed_at=record.completed_at,
        worker_id=record.worker_id,
        message=record.latest_message,
        verdict=None if record.verdict is None else EvaluationRunVerdict(record.verdict),
        failure_reason=record.failure_reason,
    )


def _map_runtime_case_result(record: EvaluationCaseResultRecord) -> EvaluationCaseResultDescriptor:
    return EvaluationCaseResultDescriptor(
        case_result_id=record.case_result_id,
        attempt_id=record.attempt_id,
        case_id=record.case_id,
        fixture_id=record.fixture_id,
        outcome=EvaluationCaseOutcome(record.outcome),
        summary=record.summary,
        evidence_refs=record.evidence_refs,
        artifact_refs=load_artifact_descriptors(artifact_ids=record.artifact_ids),
        provider_config_sha256=record.provider_config_sha256,
        recorded_at=record.recorded_at,
    )
