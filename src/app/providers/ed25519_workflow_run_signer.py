from __future__ import annotations

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.services.workflow_run_attestation_signing import WorkflowRunSignature


class Ed25519WorkflowRunAttestationSigner:
    def __init__(self, *, private_key: Ed25519PrivateKey, key_id: str, rotation_epoch: int) -> None:
        if not key_id.strip():
            raise ValueError("key_id must not be blank")
        if rotation_epoch < 1:
            raise ValueError("rotation_epoch must be positive")
        self._private_key = private_key
        self._key_id = key_id
        self._rotation_epoch = rotation_epoch

    def sign(self, payload: bytes) -> WorkflowRunSignature:
        if not payload:
            raise ValueError("attestation payload must not be empty")
        return WorkflowRunSignature(
            algorithm="EdDSA",
            key_id=self._key_id,
            rotation_epoch=self._rotation_epoch,
            signature=self._private_key.sign(payload),
        )
