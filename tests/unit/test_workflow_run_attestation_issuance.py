from dataclasses import replace
from datetime import UTC, datetime

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.contracts.artifacts import (
    ArtifactDescriptor,
    ArtifactLifecycleStatus,
    ArtifactStorageBackend,
)
from app.contracts.evidence import ExecutionEvidenceDescriptor
from app.contracts.workflow_run_attestation import WorkflowRunAttestationEnvelope
from app.providers.ed25519_workflow_run_signer import Ed25519WorkflowRunAttestationSigner
from app.repositories.memory_workflow_pack_run_repository import InMemoryWorkflowPackRunRepository
from app.repositories.workflow_pack_run_repository import WorkflowPackRunRecord
from app.services.workflow_run_attestation_issuance import (
    WorkflowRunAttestationNotIssuableError,
    WorkflowRunAttestationRunNotFoundError,
    issue_workflow_run_attestation,
)


ISSUED_AT = datetime(2026, 7, 11, 10, 5, tzinfo=UTC)


def _record() -> WorkflowPackRunRecord:
    return WorkflowPackRunRecord(
        run_id="packrun_idea_explanation_request-001",
        pack_id="idea_explanation.pack",
        pack_family="idea_explanation",
        pack_version="v1",
        registration_ref="idea_explanation.pack@v1",
        task_id="explain.v1",
        request_id="request-001",
        caller_app="lotus-idea",
        correlation_id="corr-001",
        tenant_id="tenant-sg-001",
        workflow_surface="idea-explanation-evidence",
        workflow_authority_owner="lotus-idea",
        runtime_state="COMPLETED",
        review_state="ACCEPTED",
        review_required=True,
        provider_mode="openai",
        stubbed=False,
        output_preview="Source-grounded explanation.",
        structured_output_keys=["advisor_review_summary"],
        evidence_descriptors=[
            ExecutionEvidenceDescriptor(
                evidence_type="task_contract",
                summary="Bounded explanation task contract.",
                attributes={"task_id": "explain.v1"},
            )
        ],
        artifact_refs=[
            ArtifactDescriptor(
                artifact_id="artifact-001",
                domain="workflow_pack",
                artifact_type="run_output_summary",
                source_object_kind="workflow_pack_run",
                source_object_id="packrun_idea_explanation_request-001",
                lifecycle_status=ArtifactLifecycleStatus.RUNTIME_GENERATED,
                retention_posture="retained_for_review",
                media_type="application/json",
                byte_size=128,
                checksum_sha256="a" * 64,
                storage_backend=ArtifactStorageBackend.MEMORY,
                storage_reference="memory://artifact-001",
                created_at="2026-07-11T10:00:02Z",
                created_by="lotus-ai",
            )
        ],
        supersedes_run_id=None,
        superseded_by_run_id=None,
        created_at="2026-07-11T10:00:02Z",
        completed_at="2026-07-11T10:00:02Z",
        last_updated_at="2026-07-11T10:01:00Z",
        evaluator_id="idea-explanation-guardrails",
        evaluator_policy_version="idea-explanation-policy.v1",
        provider_id="text.openai",
        model_id="gpt-5.4",
        model_version="2026-06-01",
        model_risk_status="approved",
        model_risk_approval_ref="model-risk://lotus-ai/gpt-5.4/2026-06-01",
        input_evidence_sha256="b" * 64,
        output_content_sha256="c" * 64,
        replay_nonce="d" * 64,
        execution_started_at="2026-07-11T10:00:00Z",
    )


def _issue(record: WorkflowPackRunRecord) -> WorkflowRunAttestationEnvelope:
    repository = InMemoryWorkflowPackRunRepository()
    repository.save_run(record)
    return issue_workflow_run_attestation(
        run_id=record.run_id,
        run_repository=repository,
        signer=Ed25519WorkflowRunAttestationSigner(
            private_key=Ed25519PrivateKey.generate(), key_id="attestation-key-1", rotation_epoch=1
        ),
        issued_at_utc=ISSUED_AT,
        ttl_seconds=300,
    )


def test_issuance_binds_durable_run_governance_and_consumer_identity() -> None:
    envelope = _issue(_record())

    claims = envelope.claims
    assert claims.issuer == "lotus-ai"
    assert claims.audience == "lotus-idea"
    assert claims.run_id == "packrun_idea_explanation_request-001"
    assert claims.consumer_request_id == "request-001"
    assert claims.workflow_pack_id == "idea_explanation.pack"
    assert claims.evaluator_policy_version == "idea-explanation-policy.v1"
    assert claims.model_risk_status == "approved"
    assert claims.model_risk_approval_ref.endswith("/2026-06-01")
    assert claims.execution_started_at_utc == "2026-07-11T10:00:00Z"
    assert claims.execution_completed_at_utc == "2026-07-11T10:00:02Z"
    assert claims.issued_at_utc == "2026-07-11T10:05:00Z"
    assert claims.expires_at_utc == "2026-07-11T10:10:00Z"
    assert envelope.signature.key_id == "attestation-key-1"


@pytest.mark.parametrize(
    ("record", "reason_code"),
    [
        (replace(_record(), review_state="AWAITING_REVIEW"), "supportability_not_ready"),
        (replace(_record(), runtime_state="FAILED"), "execution_not_completed"),
        (
            replace(
                _record(),
                model_risk_status="approval_unverified",
                model_risk_approval_ref="unverifiable",
            ),
            "model_risk_not_approved",
        ),
        (replace(_record(), stubbed=True), "stub_execution"),
    ],
)
def test_issuance_rejects_non_certifying_run_posture(
    record: WorkflowPackRunRecord, reason_code: str
) -> None:
    with pytest.raises(WorkflowRunAttestationNotIssuableError) as captured:
        _issue(record)

    assert captured.value.reason_code == reason_code


def test_issuance_rejects_unknown_run() -> None:
    with pytest.raises(WorkflowRunAttestationRunNotFoundError):
        issue_workflow_run_attestation(
            run_id="missing",
            run_repository=InMemoryWorkflowPackRunRepository(),
            signer=Ed25519WorkflowRunAttestationSigner(
                private_key=Ed25519PrivateKey.generate(), key_id="key-1", rotation_epoch=1
            ),
            issued_at_utc=ISSUED_AT,
        )
