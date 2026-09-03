"""Data-lifecycle evidence and legal-hold contracts (issue #158, S2a)."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.contracts.governed_actions import GovernedActionRecord
from app.contracts.workflow_run_attestation import WorkflowRunAttestationSignature


class DataLifecycleAction(str, Enum):
    EXPIRY = "EXPIRY"
    ERASURE = "ERASURE"


class DataLifecycleEventRecord(BaseModel):
    """One append-only deletion-evidence row: deletion never removes the
    evidence of deletion, and content is referenced only by digest."""

    event_id: str = Field(min_length=1, max_length=64)
    family_id: str = Field(min_length=1, max_length=128)
    action: DataLifecycleAction
    key_scope: str | None = Field(
        default=None,
        max_length=256,
        description="Key scope the action applied to, when narrower than the family.",
    )
    row_count: int = Field(ge=1)
    policy_version: str = Field(min_length=1, max_length=16)
    actor: str = Field(min_length=1, max_length=256)
    deleted_ids_digest: str = Field(
        min_length=64,
        max_length=64,
        description="sha256 over the sorted deleted primary keys - evidence without content.",
    )
    recorded_at: str = Field(min_length=1, max_length=64)


class DataLegalHoldRecord(BaseModel):
    """An active hold while released_at is null: legal hold overrides expiry,
    and (from S3) erasure - both recorded."""

    hold_id: str = Field(min_length=1, max_length=64)
    family_id: str = Field(min_length=1, max_length=128)
    key_type: str = Field(min_length=1, max_length=32)
    key_value: str = Field(min_length=1, max_length=256)
    reason: str = Field(min_length=1)
    placed_by: str = Field(min_length=1, max_length=256)
    placed_at: str = Field(min_length=1, max_length=64)
    released_at: str | None = Field(default=None, max_length=64)


class DataErasureIntentRequest(BaseModel):
    """Step one of governed tenant erasure (issue #158, S3).

    Erasure permanently destroys client-derived rows across every
    tenant-erasable family - a risk-appropriate governed action: a verified
    requester states the intent, a distinct verified credential approves the
    exact hash. Caller identity comes from the credential, never the body.
    """

    tenant_id: str = Field(min_length=1, max_length=128)
    reason: str = Field(min_length=1, description="The obligation driving the erasure.")
    requested_by: str | None = Field(
        default=None,
        max_length=256,
        description="Claimed operator name; recorded as unverified attribution.",
    )


class DataErasureApprovalRequest(BaseModel):
    """Step two: a distinct verified credential approves the exact pending action."""

    action_id: str = Field(min_length=1, max_length=64)
    action_hash: str = Field(min_length=64, max_length=64)
    approved_by: str | None = Field(default=None, max_length=256)


class DataErasureFamilyResult(BaseModel):
    """One family's outcome inside an erasure receipt."""

    family_id: str = Field(min_length=1)
    erased_count: int = Field(ge=0)
    held: bool = Field(
        description="True when an active legal hold for this tenant kept the family untouched."
    )


class DataErasureReceiptClaims(BaseModel):
    """The verifiable facts of one executed tenant erasure.

    Legal hold overrides erasure: a held family is listed with held=true and
    zero erasures rather than silently skipped. The receipt is what #115
    consumers present as deletion proof.
    """

    schema_version: str = Field(pattern=r"^lotus-ai\.data-erasure-receipt\.v1$")
    issuer: str = Field(pattern=r"^lotus-ai$")
    receipt_id: str = Field(min_length=1, max_length=64)
    tenant_id: str = Field(min_length=1, max_length=128)
    reason: str = Field(min_length=1)
    policy_version: str = Field(min_length=1, max_length=16)
    governed_action_id: str = Field(min_length=1, max_length=64)
    families: list[DataErasureFamilyResult] = Field(min_length=1)
    executed_at: str = Field(min_length=1, max_length=64)


class DataErasureReceiptEnvelope(BaseModel):
    """A signed erasure receipt, verifiable against the published keys."""

    claims: DataErasureReceiptClaims
    signature: WorkflowRunAttestationSignature
    key_discovery_path: str = Field(
        description="Path serving the Ed25519 public keys that verify this receipt."
    )


class DataErasureApprovalResponse(BaseModel):
    service: str
    version: str
    receipt: DataErasureReceiptEnvelope
    governed_action: GovernedActionRecord
    summary: list[str]
