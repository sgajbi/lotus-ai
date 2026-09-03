"""Test-side minting of platform service-caller credentials (issue #149)."""

from __future__ import annotations

import base64
import json
import time
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

TEST_ISSUER = "https://platform.lotus/issuer"
TEST_AUDIENCE = "lotus-ai"


def generate_caller_signing_key() -> Ed25519PrivateKey:
    return Ed25519PrivateKey.generate()


def public_keys_setting(**keys_by_kid: Ed25519PrivateKey) -> str:
    """The LOTUS_AI_CALLER_JWT_PUBLIC_KEYS value for the given signing keys."""

    return json.dumps(
        {
            kid: base64.b64encode(
                key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
            ).decode("ascii")
            for kid, key in keys_by_kid.items()
        }
    )


def mint_caller_credential(
    *,
    signing_key: Ed25519PrivateKey,
    key_id: str,
    subject: str,
    issuer: str = TEST_ISSUER,
    audience: str = TEST_AUDIENCE,
    expires_in_seconds: int = 300,
    extra_claims: dict[str, Any] | None = None,
    omit_claims: tuple[str, ...] = (),
    algorithm: str = "EdDSA",
    token_type: str | None = "JWT",
) -> str:
    now = time.time()
    payload: dict[str, Any] = {
        "iss": issuer,
        "aud": audience,
        "sub": subject,
        "iat": int(now),
        "exp": int(now + expires_in_seconds),
    }
    if extra_claims:
        payload.update(extra_claims)
    for claim in omit_claims:
        payload.pop(claim, None)
    header: dict[str, Any] = {"alg": algorithm, "kid": key_id}
    if token_type is not None:
        header["typ"] = token_type
    signing_input = f"{_b64url(header)}.{_b64url(payload)}"
    signature = signing_key.sign(signing_input.encode("ascii"))
    return f"{signing_input}.{_b64url_bytes(signature)}"


def _b64url(value: dict[str, Any]) -> str:
    return _b64url_bytes(json.dumps(value, separators=(",", ":")).encode("utf-8"))


def _b64url_bytes(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")
