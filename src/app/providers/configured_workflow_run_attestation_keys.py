from __future__ import annotations

import base64
from datetime import datetime
import json

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import TypeAdapter, ValidationError

from app.config import Settings
from app.contracts.workflow_run_attestation import WorkflowRunAttestationPublicKey
from app.providers.ed25519_workflow_run_signer import Ed25519WorkflowRunAttestationSigner
from app.services.workflow_run_attestation_signing import WorkflowRunSignature


_PUBLIC_KEYS = TypeAdapter(list[WorkflowRunAttestationPublicKey])


class ConfiguredWorkflowRunAttestationKeys:
    def __init__(self, *, settings: Settings) -> None:
        self._settings = settings

    def signer(self) -> Ed25519WorkflowRunAttestationSigner:
        key_id, rotation_epoch, private_key = self._active_key_configuration()
        return Ed25519WorkflowRunAttestationSigner(
            private_key=private_key,
            key_id=key_id,
            rotation_epoch=rotation_epoch,
        )

    def sign(self, payload: bytes) -> WorkflowRunSignature:
        return self.signer().sign(payload)

    def public_keys(self) -> list[WorkflowRunAttestationPublicKey]:
        key_id, rotation_epoch, private_key = self._active_key_configuration()
        not_before = self._required_text(
            self._settings.workflow_run_attestation_key_not_before_utc,
            "workflow-run attestation key not-before timestamp",
        )
        self._parse_timestamp(not_before, "workflow-run attestation key not-before timestamp")
        not_after = self._settings.workflow_run_attestation_key_not_after_utc
        if not_after is not None:
            self._parse_timestamp(not_after, "workflow-run attestation key not-after timestamp")
        active_key = WorkflowRunAttestationPublicKey(
            key_id=key_id,
            algorithm="EdDSA",
            curve="Ed25519",
            public_key_base64url=self._encode(
                private_key.public_key().public_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PublicFormat.Raw,
                )
            ),
            rotation_epoch=rotation_epoch,
            status="active",
            not_before_utc=not_before,
            not_after_utc=not_after,
        )
        try:
            rotated = _PUBLIC_KEYS.validate_python(
                json.loads(self._settings.workflow_run_attestation_rotated_public_keys_json)
            )
        except (json.JSONDecodeError, ValidationError) as exc:
            raise ValueError(
                "rotated workflow-run attestation keys must be valid governed JSON"
            ) from exc
        if any(key.status == "active" for key in rotated):
            raise ValueError(
                "rotated workflow-run attestation key configuration cannot declare active keys"
            )
        keys = [active_key, *rotated]
        if len({key.key_id for key in keys}) != len(keys):
            raise ValueError("workflow-run attestation key identifiers must be unique")
        return keys

    def _active_key_configuration(self) -> tuple[str, int, Ed25519PrivateKey]:
        key_id = self._required_text(
            self._settings.workflow_run_attestation_key_id,
            "workflow-run attestation key identifier",
        )
        rotation_epoch = self._settings.workflow_run_attestation_rotation_epoch
        if rotation_epoch is None or rotation_epoch < 1:
            raise ValueError("workflow-run attestation rotation epoch must be positive")
        encoded = self._required_text(
            self._settings.workflow_run_attestation_private_key_base64url,
            "workflow-run attestation private key",
        )
        try:
            private_key = Ed25519PrivateKey.from_private_bytes(self._decode(encoded))
        except (ValueError, TypeError) as exc:
            raise ValueError(
                "workflow-run attestation private key must be a raw Ed25519 key"
            ) from exc
        return key_id, rotation_epoch, private_key

    @staticmethod
    def _required_text(value: str | None, label: str) -> str:
        if value is None or not value.strip():
            raise ValueError(f"{label} is not configured")
        return value.strip()

    @staticmethod
    def _parse_timestamp(value: str, label: str) -> datetime:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"{label} must be an ISO-8601 timestamp") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError(f"{label} must be timezone-aware")
        return parsed

    @staticmethod
    def _decode(value: str) -> bytes:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))

    @staticmethod
    def _encode(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")
