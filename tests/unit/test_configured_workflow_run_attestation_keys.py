import base64
from datetime import UTC, datetime, timedelta
import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.config import Settings
from app.providers.configured_workflow_run_attestation_keys import (
    ConfiguredWorkflowRunAttestationKeys,
)
from app.services.workflow_run_attestation_key_discovery import (
    build_workflow_run_attestation_key_discovery,
)


NOW = datetime(2026, 7, 11, 10, tzinfo=UTC)


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _settings(**overrides: object) -> Settings:
    private_key = Ed25519PrivateKey.generate()
    values: dict[str, object] = {
        "workflow_run_attestation_key_id": "workflow-attestation-2026-07",
        "workflow_run_attestation_rotation_epoch": 2,
        "workflow_run_attestation_private_key_base64url": _encode(private_key.private_bytes_raw()),
        "workflow_run_attestation_key_not_before_utc": NOW.isoformat(),
        "workflow_run_attestation_key_not_after_utc": (NOW + timedelta(days=90)).isoformat(),
        "workflow_run_attestation_rotated_public_keys_json": json.dumps(
            [
                {
                    "key_id": "workflow-attestation-2026-04",
                    "algorithm": "EdDSA",
                    "curve": "Ed25519",
                    "public_key_base64url": _encode(
                        Ed25519PrivateKey.generate().public_key().public_bytes_raw()
                    ),
                    "rotation_epoch": 1,
                    "status": "rotated",
                    "not_before_utc": (NOW - timedelta(days=90)).isoformat(),
                    "not_after_utc": (NOW + timedelta(days=7)).isoformat(),
                }
            ]
        ),
    }
    values.update(overrides)
    return Settings.model_validate(values)


def test_discovery_publishes_active_and_rotated_public_keys_without_private_material() -> None:
    configured_keys = ConfiguredWorkflowRunAttestationKeys(settings=_settings())

    discovery = build_workflow_run_attestation_key_discovery(key_source=configured_keys)

    assert [key.rotation_epoch for key in discovery.keys] == [2, 1]
    assert [key.status for key in discovery.keys] == ["active", "rotated"]
    encoded_discovery = discovery.model_dump_json()
    assert "private" not in encoded_discovery.lower()
    assert "workflow_run_attestation_private_key" not in encoded_discovery


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"workflow_run_attestation_key_id": None}, "identifier is not configured"),
        ({"workflow_run_attestation_rotation_epoch": 0}, "epoch must be positive"),
        ({"workflow_run_attestation_private_key_base64url": "not-a-key"}, "raw Ed25519"),
        ({"workflow_run_attestation_key_not_before_utc": "2026-07-11"}, "timezone-aware"),
        ({"workflow_run_attestation_rotated_public_keys_json": "{"}, "governed JSON"),
    ],
)
def test_invalid_signing_key_configuration_fails_closed(
    overrides: dict[str, object], message: str
) -> None:
    configured_keys = ConfiguredWorkflowRunAttestationKeys(settings=_settings(**overrides))

    with pytest.raises(ValueError, match=message):
        build_workflow_run_attestation_key_discovery(key_source=configured_keys)
