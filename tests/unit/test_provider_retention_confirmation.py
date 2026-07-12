from __future__ import annotations

import base64
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.contracts.workflow_run_attestation import (
    WorkflowRunAttestationKeyDiscoveryResponse,
    WorkflowRunAttestationPublicKey,
)
from app.provider_retention_confirmations.contracts import (
    ProviderRetentionConfirmationEnvelope,
    ProviderRetentionConfirmationRequest,
)
from app.provider_retention_confirmations.memory_repository import (
    InMemoryProviderRetentionConfirmationRepository,
)
from app.provider_retention_confirmations.repository import (
    ProviderRetentionConfirmationConflictError,
)
from app.provider_retention_confirmations.service import (
    ProviderRetentionConfirmationNotFoundError,
    ProviderRetentionConfirmationNotIssuableError,
    issue_provider_retention_confirmation,
)
from app.provider_retention_confirmations.verification import (
    verify_provider_retention_confirmation,
)
from app.providers.ed25519_workflow_run_signer import Ed25519WorkflowRunAttestationSigner
from app.repositories.memory_workflow_pack_run_repository import InMemoryWorkflowPackRunRepository
from app.repositories.workflow_pack_run_repository import WorkflowPackRunRecord
from tests.unit.test_workflow_run_attestation_issuance import _record as workflow_run_record

NOW = datetime(2026, 7, 12, 2, 0, tzinfo=UTC)
PRIVATE_KEY = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
BASE_RUN = workflow_run_record()


def test_issues_and_verifies_source_safe_deletion_confirmation() -> None:
    envelope = _issue(BASE_RUN, _request(outcome="DELETION_CONFIRMED"))

    assert envelope.claims.provider_id == "text.openai"
    assert envelope.claims.model_id == "gpt-5.4"
    assert envelope.claims.tenant_id == "tenant-sg-001"
    assert envelope.claims.deletion_confirmed is True
    assert envelope.claims.supportability_status == "READY"
    assert envelope.claims.raw_prompt_included is False
    assert envelope.claims.raw_output_included is False
    assert envelope.claims.client_identifier_included is False
    verify_provider_retention_confirmation(
        envelope,
        key_discovery=_discovery(),
        expected_tenant_id="tenant-sg-001",
        at_utc=NOW + timedelta(minutes=1),
    )


def test_provider_failure_is_signed_as_blocked_not_deletion_proof() -> None:
    envelope = _issue(
        BASE_RUN,
        _request(outcome="PROVIDER_FAILURE", provider_failure_code="PROVIDER_TIMEOUT"),
    )

    assert envelope.claims.outcome == "PROVIDER_FAILURE"
    assert envelope.claims.provider_failure_code == "PROVIDER_TIMEOUT"
    assert envelope.claims.supportability_status == "BLOCKED"
    assert envelope.claims.deletion_confirmed is False


def test_request_rejects_inconsistent_provider_failure_details() -> None:
    with pytest.raises(ValueError, match="requires provider_failure_code"):
        _request(outcome="PROVIDER_FAILURE")
    with pytest.raises(ValueError, match="allowed only for provider failure"):
        _request(provider_failure_code="UNEXPECTED_CODE")


def test_same_input_replays_and_changed_input_conflicts() -> None:
    runs = _runs(BASE_RUN)
    confirmations = InMemoryProviderRetentionConfirmationRepository()
    first = _issue_with_stores(_request(), runs, confirmations)
    replay = _issue_with_stores(_request(), runs, confirmations)

    assert replay == first
    with pytest.raises(ProviderRetentionConfirmationConflictError):
        _issue_with_stores(
            _request(provider_confirmation_ref="provider-confirmation-changed"),
            runs,
            confirmations,
        )
    with pytest.raises(ProviderRetentionConfirmationConflictError):
        _issue_with_stores(
            _request(),
            runs,
            confirmations,
            idempotency_key="provider-retention-key-new",
        )


@pytest.mark.parametrize(
    ("run", "caller_app", "tenant_id", "reason_code"),
    [
        (
            replace(BASE_RUN, pack_id="advisor_brief.pack"),
            "lotus-ai-provider-operations",
            "tenant-sg-001",
            "run_not_idea_owned",
        ),
        (BASE_RUN, "lotus-idea", "tenant-sg-001", "caller_not_authorized"),
        (BASE_RUN, "lotus-ai-provider-operations", "tenant-other", "tenant_mismatch"),
        (
            replace(BASE_RUN, runtime_state="FAILED"),
            "lotus-ai-provider-operations",
            "tenant-sg-001",
            "run_not_completed",
        ),
        (
            replace(BASE_RUN, stubbed=True),
            "lotus-ai-provider-operations",
            "tenant-sg-001",
            "provider_execution_not_live",
        ),
        (
            replace(BASE_RUN, provider_id="unverifiable"),
            "lotus-ai-provider-operations",
            "tenant-sg-001",
            "provider_identity_unverifiable",
        ),
    ],
)
def test_confirmation_fails_closed_for_untrusted_run_or_caller_posture(
    run: WorkflowPackRunRecord,
    caller_app: str,
    tenant_id: str,
    reason_code: str,
) -> None:
    with pytest.raises(ProviderRetentionConfirmationNotIssuableError) as caught:
        _issue(run, _request(), caller_app=caller_app, tenant_id=tenant_id)

    assert caught.value.reason_code == reason_code


def test_confirmation_rejects_missing_run_invalid_time_and_ttl() -> None:
    empty_runs = InMemoryWorkflowPackRunRepository()
    confirmations = InMemoryProviderRetentionConfirmationRepository()
    with pytest.raises(ProviderRetentionConfirmationNotFoundError):
        _issue_with_stores(_request(), empty_runs, confirmations)
    with pytest.raises(ValueError, match="ISO-8601"):
        _issue(BASE_RUN, _request(provider_decision_at_utc="not-a-time"))
    with pytest.raises(ValueError, match="timezone-aware"):
        _issue(BASE_RUN, _request(provider_decision_at_utc="2026-07-12T01:59:00"))
    with pytest.raises(ProviderRetentionConfirmationNotIssuableError) as caught:
        _issue(BASE_RUN, _request(provider_decision_at_utc="2026-07-12T02:01:00Z"))
    assert caught.value.reason_code == "provider_decision_in_future"
    with pytest.raises(ValueError, match="TTL"):
        issue_provider_retention_confirmation(
            run_id=BASE_RUN.run_id,
            request=_request(),
            idempotency_key="invalid-ttl",
            caller_app="lotus-ai-provider-operations",
            tenant_id="tenant-sg-001",
            run_repository=_runs(BASE_RUN),
            confirmation_repository=confirmations,
            signer=Ed25519WorkflowRunAttestationSigner(
                private_key=PRIVATE_KEY,
                key_id="workflow-attestation-2026-07",
                rotation_epoch=2,
            ),
            issued_at_utc=NOW,
            ttl_seconds=0,
        )


def test_confirmation_rejects_naive_issue_time_and_invalid_signer_result() -> None:
    class InvalidSigner:
        def sign(self, payload: bytes) -> object:
            del payload
            return type(
                "InvalidSignatureResult",
                (),
                {"algorithm": "RS256", "signature": b"", "key_id": "bad", "rotation_epoch": 1},
            )()

    with pytest.raises(ValueError, match="timezone-aware"):
        issue_provider_retention_confirmation(
            run_id=BASE_RUN.run_id,
            request=_request(),
            idempotency_key="naive-issue-time",
            caller_app="lotus-ai-provider-operations",
            tenant_id="tenant-sg-001",
            run_repository=_runs(BASE_RUN),
            confirmation_repository=InMemoryProviderRetentionConfirmationRepository(),
            signer=Ed25519WorkflowRunAttestationSigner(
                private_key=PRIVATE_KEY,
                key_id="workflow-attestation-2026-07",
                rotation_epoch=2,
            ),
            issued_at_utc=NOW.replace(tzinfo=None),
        )
    with pytest.raises(ValueError, match="invalid signature"):
        issue_provider_retention_confirmation(
            run_id=BASE_RUN.run_id,
            request=_request(),
            idempotency_key="invalid-signer",
            caller_app="lotus-ai-provider-operations",
            tenant_id="tenant-sg-001",
            run_repository=_runs(BASE_RUN),
            confirmation_repository=InMemoryProviderRetentionConfirmationRepository(),
            signer=InvalidSigner(),  # type: ignore[arg-type]
            issued_at_utc=NOW,
        )


def test_verification_rejects_forged_expired_revoked_and_wrong_tenant() -> None:
    envelope = _issue(BASE_RUN, _request())
    forged = envelope.model_copy(
        update={
            "claims": envelope.claims.model_copy(update={"retention_policy_id": "forged-policy"})
        }
    )

    with pytest.raises(ValueError, match="signature verification"):
        verify_provider_retention_confirmation(
            forged,
            key_discovery=_discovery(),
            expected_tenant_id="tenant-sg-001",
            at_utc=NOW + timedelta(minutes=1),
        )
    with pytest.raises(ValueError, match="not currently valid"):
        verify_provider_retention_confirmation(
            envelope,
            key_discovery=_discovery(),
            expected_tenant_id="tenant-sg-001",
            at_utc=datetime.fromisoformat(envelope.claims.expires_at_utc.replace("Z", "+00:00")),
        )
    with pytest.raises(ValueError, match="revoked"):
        verify_provider_retention_confirmation(
            envelope,
            key_discovery=_discovery(status="revoked"),
            expected_tenant_id="tenant-sg-001",
            at_utc=NOW + timedelta(minutes=1),
        )
    with pytest.raises(ValueError, match="tenant does not match"):
        verify_provider_retention_confirmation(
            envelope,
            key_discovery=_discovery(),
            expected_tenant_id="tenant-other",
            at_utc=NOW + timedelta(minutes=1),
        )
    with pytest.raises(ValueError, match="unknown or ambiguous"):
        verify_provider_retention_confirmation(
            envelope,
            key_discovery=_discovery(key_id="another-key"),
            expected_tenant_id="tenant-sg-001",
            at_utc=NOW + timedelta(minutes=1),
        )
    naive_timestamp = envelope.model_copy(
        update={
            "claims": envelope.claims.model_copy(update={"issued_at_utc": "2026-07-12T02:00:00"})
        }
    )
    with pytest.raises(ValueError, match="timestamp must be timezone-aware"):
        verify_provider_retention_confirmation(
            naive_timestamp,
            key_discovery=_discovery(),
            expected_tenant_id="tenant-sg-001",
            at_utc=NOW + timedelta(minutes=1),
        )


def _issue(
    run: WorkflowPackRunRecord,
    request: ProviderRetentionConfirmationRequest,
    *,
    caller_app: str = "lotus-ai-provider-operations",
    tenant_id: str = "tenant-sg-001",
    idempotency_key: str = "provider-retention-key-001",
) -> ProviderRetentionConfirmationEnvelope:
    return _issue_with_stores(
        request,
        _runs(run),
        InMemoryProviderRetentionConfirmationRepository(),
        caller_app=caller_app,
        tenant_id=tenant_id,
    )


def _issue_with_stores(
    request: ProviderRetentionConfirmationRequest,
    runs: InMemoryWorkflowPackRunRepository,
    confirmations: InMemoryProviderRetentionConfirmationRepository,
    *,
    caller_app: str = "lotus-ai-provider-operations",
    tenant_id: str = "tenant-sg-001",
    idempotency_key: str = "provider-retention-key-001",
) -> ProviderRetentionConfirmationEnvelope:
    return issue_provider_retention_confirmation(
        run_id="packrun_idea_explanation_request-001",
        request=request,
        idempotency_key=idempotency_key,
        caller_app=caller_app,
        tenant_id=tenant_id,
        run_repository=runs,
        confirmation_repository=confirmations,
        signer=Ed25519WorkflowRunAttestationSigner(
            private_key=PRIVATE_KEY,
            key_id="workflow-attestation-2026-07",
            rotation_epoch=2,
        ),
        issued_at_utc=NOW,
    )


def _runs(run: WorkflowPackRunRecord) -> InMemoryWorkflowPackRunRepository:
    repository = InMemoryWorkflowPackRunRepository()
    repository.save_run(run)
    return repository


def _request(**overrides: object) -> ProviderRetentionConfirmationRequest:
    values: dict[str, object] = {
        "provider_confirmation_ref": "provider-confirmation-001",
        "retention_policy_id": "idea-provider-zero-retention-v1",
        "outcome": "NO_PROVIDER_STORAGE",
        "provider_decision_at_utc": "2026-07-12T01:59:00Z",
        "evidence_sha256": "e" * 64,
    }
    values.update(overrides)
    return ProviderRetentionConfirmationRequest.model_validate(values)


def _discovery(
    status: str = "active",
    key_id: str = "workflow-attestation-2026-07",
) -> WorkflowRunAttestationKeyDiscoveryResponse:
    return WorkflowRunAttestationKeyDiscoveryResponse(
        schema_version="lotus-ai.workflow-run-attestation-keys.v1",
        issuer="lotus-ai",
        keys=[
            WorkflowRunAttestationPublicKey(
                key_id=key_id,
                algorithm="EdDSA",
                curve="Ed25519",
                public_key_base64url=base64.urlsafe_b64encode(
                    PRIVATE_KEY.public_key().public_bytes_raw()
                )
                .rstrip(b"=")
                .decode(),
                rotation_epoch=2,
                status=status,
                not_before_utc="2026-07-01T00:00:00Z",
                not_after_utc="2026-10-01T00:00:00Z",
            )
        ],
    )
