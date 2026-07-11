from __future__ import annotations

from typing import Protocol

from app.contracts.workflow_run_attestation import (
    WorkflowRunAttestationKeyDiscoveryResponse,
    WorkflowRunAttestationPublicKey,
)


class WorkflowRunAttestationPublicKeySource(Protocol):
    def public_keys(self) -> list[WorkflowRunAttestationPublicKey]: ...


def build_workflow_run_attestation_key_discovery(
    *, key_source: WorkflowRunAttestationPublicKeySource
) -> WorkflowRunAttestationKeyDiscoveryResponse:
    keys = key_source.public_keys()
    if not keys or sum(key.status == "active" for key in keys) != 1:
        raise ValueError("workflow-run attestation discovery requires exactly one active key")
    return WorkflowRunAttestationKeyDiscoveryResponse(
        schema_version="lotus-ai.workflow-run-attestation-keys.v1",
        issuer="lotus-ai",
        keys=sorted(keys, key=lambda key: key.rotation_epoch, reverse=True),
    )
