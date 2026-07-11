from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class WorkflowRunAttestationClaims(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(pattern=r"^lotus-ai\.workflow-run-attestation\.v1$")
    issuer: str = Field(pattern=r"^lotus-ai$")
    audience: str = Field(min_length=1, max_length=64)
    run_id: str = Field(min_length=1, max_length=128)
    consumer_request_id: str = Field(min_length=1, max_length=128)
    replay_nonce: str = Field(pattern=r"^[0-9a-f]{64}$")
    workflow_pack_id: str = Field(min_length=1, max_length=128)
    workflow_pack_version: str = Field(min_length=1, max_length=64)
    registration_ref: str = Field(min_length=1, max_length=256)
    evaluator_id: str = Field(min_length=1, max_length=128)
    evaluator_policy_version: str = Field(min_length=1, max_length=64)
    provider_id: str = Field(min_length=1, max_length=128)
    provider_mode: str = Field(min_length=1, max_length=64)
    model_id: str = Field(min_length=1, max_length=128)
    model_version: str = Field(min_length=1, max_length=64)
    model_risk_status: str = Field(pattern=r"^approved$")
    model_risk_approval_ref: str = Field(min_length=1, max_length=256)
    input_evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    issued_at_utc: str
    execution_started_at_utc: str
    execution_completed_at_utc: str
    expires_at_utc: str
    stubbed: bool
    supportability_status: str = Field(pattern=r"^READY$")


class WorkflowRunAttestationSignature(BaseModel):
    model_config = ConfigDict(extra="forbid")

    algorithm: str = Field(pattern=r"^EdDSA$")
    key_id: str = Field(min_length=1, max_length=128)
    rotation_epoch: int = Field(ge=1)
    signature_base64url: str = Field(pattern=r"^[A-Za-z0-9_-]+$")


class WorkflowRunAttestationEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claims: WorkflowRunAttestationClaims
    signature: WorkflowRunAttestationSignature
    key_discovery_path: str = Field(pattern=r"^/\.well-known/lotus-ai-workflow-attestation-keys$")


class WorkflowRunAttestationPublicKey(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key_id: str = Field(min_length=1, max_length=128)
    algorithm: str = Field(pattern=r"^EdDSA$")
    curve: str = Field(pattern=r"^Ed25519$")
    public_key_base64url: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    rotation_epoch: int = Field(ge=1)
    status: str = Field(pattern=r"^(active|rotated|revoked)$")
    not_before_utc: str
    not_after_utc: str | None = None


class WorkflowRunAttestationKeyDiscoveryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(pattern=r"^lotus-ai\.workflow-run-attestation-keys\.v1$")
    issuer: str = Field(pattern=r"^lotus-ai$")
    keys: list[WorkflowRunAttestationPublicKey]
