from app.services.retrieval_evidence_readiness import build_retrieval_evidence_readiness
from app.contracts.evals import EvaluationRunSubmissionRequest
from app.services.eval_async_execution import run_next_evaluation_execution_job
from app.services.eval_run_submission_service import submit_evaluation_run
from app.contracts.runtime_readiness import RuntimeReadinessStatus


def test_retrieval_evidence_readiness_reports_foundation_evidence_gaps() -> None:
    readiness = build_retrieval_evidence_readiness()

    assert readiness.service == "lotus-ai"
    assert readiness.evidence_ready is False
    assert readiness.required_item_count == 6
    assert readiness.completed_required_item_count == 0
    assert readiness.items[0].evidence_id == "retrieval_fixture_coverage_pack"
    assert readiness.items[1].status == "NOT_READY"
    assert readiness.approval_gate.domain_id == "retrieval_execution"
    assert readiness.approval_gate.evidence_state.value == "STAGED_ONLY"


def test_retrieval_evidence_readiness_prefers_runtime_backed_live_evidence() -> None:
    for fixture_id in ("retrieval_citation_examples", "retrieval_embedding_examples"):
        submit_evaluation_run(
            EvaluationRunSubmissionRequest(
                fixture_id=fixture_id,
                caller_app="lotus-platform",
                correlation_id=f"corr-{fixture_id}",
                triggered_by="operator-a",
            )
        )
        run_next_evaluation_execution_job(worker_id="worker-a")

    readiness = build_retrieval_evidence_readiness()

    assert readiness.approval_gate.evidence_state.value == "RUNTIME_PASS"
    assert readiness.items[0].status == "READY"
    assert readiness.items[1].status == "READY"
    assert readiness.items[2].status == "READY"
    assert readiness.items[3].status == "READY"
    assert readiness.items[5].status == "NOT_READY"


def test_retrieval_evidence_readiness_reports_corpus_change_artifact_pack_when_available() -> None:
    from app.services.retrieval_ingestion_async_execution import (
        run_next_retrieval_ingestion_job,
        submit_retrieval_ingestion_job_async,
    )

    submit_retrieval_ingestion_job_async(
        job_id="ingjob_lotus_platform_rfcs_refresh_0069",
        caller_app="lotus-platform",
        correlation_id="corr-ret-evidence-artifact-001",
    )
    run_next_retrieval_ingestion_job(worker_id="worker-a")

    readiness = build_retrieval_evidence_readiness()

    assert readiness.items[5].status == "READY"


def test_retrieval_evidence_readiness_blocks_corpus_change_pack_when_artifact_review_path_is_not_ready(
    monkeypatch,
) -> None:
    from app.services.retrieval_ingestion_async_execution import (
        run_next_retrieval_ingestion_job,
        submit_retrieval_ingestion_job_async,
    )

    submit_retrieval_ingestion_job_async(
        job_id="ingjob_lotus_platform_rfcs_refresh_0069",
        caller_app="lotus-platform",
        correlation_id="corr-ret-evidence-artifact-blocked-001",
    )
    run_next_retrieval_ingestion_job(worker_id="worker-a")
    monkeypatch.setattr(
        "app.services.retrieval_evidence_readiness.build_artifact_runtime_status",
        lambda: type(
            "ArtifactRuntime",
            (),
            {
                "metadata_store": type(
                    "MetadataStore",
                    (),
                    {"status": RuntimeReadinessStatus.READY},
                )(),
                "object_store": type(
                    "ObjectStore",
                    (),
                    {"status": RuntimeReadinessStatus.CONFIGURATION_REQUIRED},
                )(),
            },
        )(),
    )

    readiness = build_retrieval_evidence_readiness()

    assert readiness.items[5].status == "NOT_READY"
    assert "artifact backbone is operational" in readiness.items[5].notes
