from pathlib import Path

import pytest
from fastapi import HTTPException
from unittest.mock import patch

from app.config import settings
from app.contracts.async_runtime import AsyncJobSubmissionRequest
from app.contracts.evals import EvaluationRunSubmissionRequest
from app.repositories.evaluation_runtime_repository import EvaluationRunRecord
from app.services.async_job_service import build_async_job_catalog
from app.services.eval_run_service import build_evaluation_run_catalog
from app.services.eval_run_submission_service import (
    submit_evaluation_execution_async_job,
    submit_evaluation_run,
)
from app.services.async_runtime_store import reset_async_runtime_store_cache
from app.services.evaluation_runtime_store import (
    get_evaluation_runtime_store,
    reset_evaluation_runtime_store_cache,
)
from tests.support.migration_runner import upgrade_database_to_head


def test_submit_evaluation_run_accepts_allowlisted_fixture_family() -> None:
    response = submit_evaluation_run(
        EvaluationRunSubmissionRequest(
            fixture_id="retrieval_citation_examples",
            caller_app="lotus-platform",
            correlation_id="corr-eval-001",
            triggered_by="operator-a",
        )
    )

    assert response.accepted is True
    assert response.submission_status == "ACCEPTED"
    assert response.run_id is not None
    assert response.async_job_id is not None

    catalog = build_evaluation_run_catalog()
    runtime_run = next(run for run in catalog.runs if run.run_id == response.run_id)
    detail = get_evaluation_runtime_store().list_attempts(run_id=response.run_id or "")

    assert runtime_run.record_source == "RUNTIME_STATE"
    assert runtime_run.fixture_id == "retrieval_citation_examples"
    assert detail[0].lifecycle_status == "QUEUED"
    assert get_evaluation_runtime_store().list_case_results(run_id=response.run_id or "") == []


def test_submit_evaluation_run_persists_sql_backed_runtime_submission(tmp_path: Path) -> None:
    settings.async_runtime_store_mode = "sqlalchemy"
    settings.evaluation_runtime_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'lotus-ai-eval-runtime-submission.db'}"
    upgrade_database_to_head(settings.database_url)

    response = submit_evaluation_run(
        EvaluationRunSubmissionRequest(
            fixture_id="provider_runtime_examples",
            caller_app="lotus-platform",
            correlation_id="corr-eval-sql-001",
            triggered_by="operator-a",
        )
    )
    reset_async_runtime_store_cache()
    reset_evaluation_runtime_store_cache()

    detail = get_evaluation_runtime_store().get_run(run_id=response.run_id or "")

    assert response.accepted is True
    assert detail is not None
    assert detail.fixture_id == "provider_runtime_examples"


def test_submit_evaluation_run_rejects_duplicate_active_fixture_family() -> None:
    first = submit_evaluation_run(
        EvaluationRunSubmissionRequest(
            fixture_id="provider_policy_examples",
            caller_app="lotus-platform",
            correlation_id="corr-eval-duplicate-001",
            triggered_by="operator-a",
        )
    )

    duplicate = submit_evaluation_run(
        EvaluationRunSubmissionRequest(
            fixture_id="provider_policy_examples",
            caller_app="lotus-platform",
            correlation_id="corr-eval-duplicate-002",
            triggered_by="operator-a",
        )
    )

    assert first.accepted is True
    assert duplicate.accepted is False
    assert duplicate.submission_status == "DUPLICATE_REJECTED"
    assert duplicate.existing_run_id == first.run_id
    assert duplicate.existing_async_job_id == first.async_job_id


def test_submit_evaluation_run_rejects_staged_only_fixture_family() -> None:
    with pytest.raises(HTTPException, match="staged-only"):
        submit_evaluation_run(
            EvaluationRunSubmissionRequest(
                fixture_id="explanation_task_examples",
                caller_app="lotus-platform",
                correlation_id="corr-eval-staged-only-001",
                triggered_by="operator-a",
            )
        )


def test_submit_evaluation_execution_async_job_accepts_allowlisted_fixture_family() -> None:
    response = submit_evaluation_execution_async_job(
        AsyncJobSubmissionRequest(
            job_type="evaluation_execution",
            target_id="provider_operations_examples",
            caller_app="lotus-platform",
            correlation_id="corr-async-eval-001",
            payload_summary="Run provider operations evaluation family.",
        )
    )

    assert response.accepted is True
    assert response.job_id is not None

    async_catalog = build_async_job_catalog()
    runtime_job = next(job for job in async_catalog.jobs if job.job_id == response.job_id)

    assert runtime_job.job_type == "evaluation_execution"
    assert runtime_job.related_evaluation_run_id is not None
    assert runtime_job.target_id == "provider_operations_examples"


def test_submit_evaluation_execution_async_job_rejects_missing_target() -> None:
    with pytest.raises(HTTPException, match="requires a concrete evaluation fixture target_id"):
        submit_evaluation_execution_async_job(
            AsyncJobSubmissionRequest(
                job_type="evaluation_execution",
                target_id=None,
                caller_app="lotus-platform",
                correlation_id="corr-async-eval-missing-target-001",
                payload_summary="Run evaluation family without target.",
            )
        )


def test_submit_evaluation_execution_async_job_rejects_unknown_target() -> None:
    with pytest.raises(HTTPException, match="Unknown evaluation fixture family"):
        submit_evaluation_execution_async_job(
            AsyncJobSubmissionRequest(
                job_type="evaluation_execution",
                target_id="unknown_fixture_family",
                caller_app="lotus-platform",
                correlation_id="corr-async-eval-unknown-target-001",
                payload_summary="Run unknown evaluation family.",
            )
        )


def test_submit_evaluation_run_rejects_when_runtime_job_type_is_disabled() -> None:
    with patch(
        "app.services.eval_run_submission_service.get_async_job_type_descriptor",
        return_value=None,
    ):
        response = submit_evaluation_run(
            EvaluationRunSubmissionRequest(
                fixture_id="provider_runtime_examples",
                caller_app="lotus-platform",
                correlation_id="corr-eval-disabled-job-type-001",
                triggered_by="operator-a",
            )
        )

    assert response.accepted is False
    assert response.submission_status == "REJECTED"
    assert "not allowlisted for runtime-backed submission" in response.message


def test_submit_evaluation_execution_async_job_rejects_duplicate_active_run() -> None:
    first = submit_evaluation_execution_async_job(
        AsyncJobSubmissionRequest(
            job_type="evaluation_execution",
            target_id="provider_runtime_examples",
            caller_app="lotus-platform",
            correlation_id="corr-async-eval-duplicate-001",
            payload_summary="Run provider runtime family.",
        )
    )

    duplicate = submit_evaluation_execution_async_job(
        AsyncJobSubmissionRequest(
            job_type="evaluation_execution",
            target_id="provider_runtime_examples",
            caller_app="lotus-platform",
            correlation_id="corr-async-eval-duplicate-002",
            payload_summary="Run provider runtime family again.",
        )
    )

    assert first.accepted is True
    assert duplicate.accepted is False
    assert duplicate.submission_status == "DUPLICATE_REJECTED"
    assert duplicate.existing_job_id == first.job_id


def test_submit_evaluation_execution_async_job_rejects_when_runtime_job_type_disabled() -> None:
    with patch(
        "app.services.eval_run_submission_service.get_async_job_type_descriptor",
        return_value=None,
    ):
        response = submit_evaluation_execution_async_job(
            AsyncJobSubmissionRequest(
                job_type="evaluation_execution",
                target_id="provider_runtime_examples",
                caller_app="lotus-platform",
                correlation_id="corr-async-eval-disabled-001",
                payload_summary="Run disabled evaluation family.",
            )
        )

    assert response.accepted is False
    assert response.submission_status == "REJECTED"
    assert "not allowlisted for runtime-backed submission" in response.message


def test_submit_evaluation_run_ignores_terminal_prior_run_when_accepting_new_submission() -> None:
    first = submit_evaluation_run(
        EvaluationRunSubmissionRequest(
            fixture_id="provider_policy_examples",
            caller_app="lotus-platform",
            correlation_id="corr-eval-terminal-prior-001",
            triggered_by="operator-a",
        )
    )
    store = get_evaluation_runtime_store()
    store.save_run(
        EvaluationRunRecord(
            run_id=first.run_id or "",
            fixture_id="provider_policy_examples",
            manifest_version="foundation.v1",
            lifecycle_status="FAILED",
            triggered_by="operator-a",
            submitted_at="2026-03-23T00:00:00Z",
            async_job_id=first.async_job_id,
            latest_message="Terminal prior run.",
            verdict="FAIL",
            case_count=2,
        )
    )
    second = submit_evaluation_run(
        EvaluationRunSubmissionRequest(
            fixture_id="provider_policy_examples",
            caller_app="lotus-platform",
            correlation_id="corr-eval-terminal-prior-002",
            triggered_by="operator-a",
        )
    )

    assert second.accepted is True
    assert second.run_id is not None
    assert second.run_id != first.run_id
