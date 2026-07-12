from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.contracts.workflow_run_attestation import WorkflowRunAttestationSignature


class ProviderRetentionOutcome(StrEnum):
    NO_PROVIDER_STORAGE = "NO_PROVIDER_STORAGE"
    RETENTION_CONFIRMED = "RETENTION_CONFIRMED"
    DELETION_CONFIRMED = "DELETION_CONFIRMED"
    PROVIDER_FAILURE = "PROVIDER_FAILURE"


class ProviderRetentionConfirmationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    provider_confirmation_ref: str = Field(min_length=3, max_length=256)
    retention_policy_id: str = Field(min_length=3, max_length=128)
    outcome: ProviderRetentionOutcome
    provider_decision_at_utc: str
    evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider_failure_code: str | None = Field(default=None, min_length=3, max_length=128)

    @model_validator(mode="after")
    def validate_failure_posture(self) -> ProviderRetentionConfirmationRequest:
        if self.outcome is ProviderRetentionOutcome.PROVIDER_FAILURE:
            if self.provider_failure_code is None:
                raise ValueError("provider failure outcome requires provider_failure_code")
        elif self.provider_failure_code is not None:
            raise ValueError("provider_failure_code is allowed only for provider failure")
        return self


class ProviderRetentionConfirmationClaims(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(pattern=r"^lotus-ai\.provider-retention-confirmation\.v1$")
    issuer: str = Field(pattern=r"^lotus-ai$")
    audience: str = Field(pattern=r"^lotus-idea$")
    recorded_by: str = Field(pattern=r"^lotus-ai-provider-operations$")
    confirmation_id: str = Field(min_length=1, max_length=128)
    workflow_run_id: str = Field(min_length=1, max_length=128)
    workflow_pack_id: str = Field(pattern=r"^idea_explanation\.pack$")
    tenant_id: str = Field(min_length=1, max_length=128)
    provider_id: str = Field(min_length=1, max_length=128)
    provider_mode: str = Field(min_length=1, max_length=64)
    model_id: str = Field(min_length=1, max_length=128)
    model_version: str = Field(min_length=1, max_length=64)
    provider_confirmation_ref: str = Field(min_length=3, max_length=256)
    retention_policy_id: str = Field(min_length=3, max_length=128)
    outcome: ProviderRetentionOutcome
    provider_decision_at_utc: str
    evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider_failure_code: str | None = Field(default=None, min_length=3, max_length=128)
    deletion_confirmed: bool
    raw_prompt_included: bool = Field(default=False)
    raw_output_included: bool = Field(default=False)
    client_identifier_included: bool = Field(default=False)
    supportability_status: str = Field(pattern=r"^(READY|BLOCKED)$")
    issued_at_utc: str
    expires_at_utc: str
    replay_nonce: str = Field(pattern=r"^[0-9a-f]{64}$")


class ProviderRetentionConfirmationEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claims: ProviderRetentionConfirmationClaims
    signature: WorkflowRunAttestationSignature
    key_discovery_path: str = Field(pattern=r"^/\.well-known/lotus-ai-workflow-attestation-keys$")
