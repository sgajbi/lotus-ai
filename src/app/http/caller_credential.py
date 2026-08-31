"""Verified service-caller credentials (issue #149, S1).

The caller identity boundary accepts a platform-issued service credential -
a compact EdDSA JWS whose ``sub`` claim names the calling application -
verified against configured issuer, audience, and Ed25519 public keys
(two active key ids supported for rotation). The bare ``X-Caller-App``
header remains only for the local header trust mode; verification failures
are 401 ``CALLER_CREDENTIAL_INVALID`` and never downgrade to header trust.
"""

from __future__ import annotations

import base64
import binascii
import json
from datetime import UTC, datetime
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from fastapi import HTTPException, status

from app.config import settings

CALLER_CREDENTIAL_ERROR_CODE = "CALLER_CREDENTIAL_INVALID"
CALLER_TRUST_MODE_HEADER = "header"
CALLER_TRUST_MODE_VERIFIED_JWT = "verified_service_jwt"
SUPPORTED_CALLER_TRUST_MODES = frozenset({CALLER_TRUST_MODE_HEADER, CALLER_TRUST_MODE_VERIFIED_JWT})


def parse_caller_credential_public_keys(raw: str) -> dict[str, Ed25519PublicKey]:
    """Parse the configured kid -> base64 raw Ed25519 public key map.

    Raises ``ValueError`` with a bounded message on any malformation, so the
    startup findings and the verifier report configuration problems
    identically.
    """

    if not raw.strip():
        raise ValueError("no caller credential public keys are configured")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("caller credential public keys are not valid JSON") from exc
    if not isinstance(parsed, dict) or not parsed:
        raise ValueError("caller credential public keys must be a non-empty JSON object")
    keys: dict[str, Ed25519PublicKey] = {}
    for key_id, encoded in parsed.items():
        if not isinstance(key_id, str) or not key_id.strip():
            raise ValueError("caller credential key ids must be non-empty strings")
        if not isinstance(encoded, str):
            raise ValueError(f"caller credential public key for kid '{key_id}' must be a string")
        try:
            raw_bytes = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError(
                f"caller credential public key for kid '{key_id}' is not valid base64"
            ) from exc
        try:
            keys[key_id] = Ed25519PublicKey.from_public_bytes(raw_bytes)
        except (ValueError, TypeError) as exc:
            raise ValueError(
                f"caller credential public key for kid '{key_id}' is not a raw Ed25519 public key"
            ) from exc
    return keys


def verify_caller_credential(authorization: str | None) -> str:
    """Verify the Authorization bearer credential and return the caller subject.

    Every failure - missing credential, malformed token, unknown key id, bad
    signature, wrong issuer or audience, expiry - is a 401 with the bounded
    ``CALLER_CREDENTIAL_INVALID`` code. Nothing ever falls back to header
    trust.
    """

    token = _extract_bearer_token(authorization)
    header, payload, signing_input, signature = _decode_compact_jws(token)

    algorithm = header.get("alg")
    if algorithm != "EdDSA":
        raise _credential_invalid(f"credential algorithm '{algorithm}' is not EdDSA")
    key_id = header.get("kid")
    if not isinstance(key_id, str) or not key_id:
        raise _credential_invalid("credential does not name a key id")

    try:
        keys = parse_caller_credential_public_keys(settings.caller_jwt_public_keys)
    except ValueError as exc:
        raise _credential_invalid(str(exc)) from exc
    public_key = keys.get(key_id)
    if public_key is None:
        raise _credential_invalid(f"credential key id '{key_id}' is not an accepted key")
    try:
        public_key.verify(signature, signing_input)
    except InvalidSignature as exc:
        raise _credential_invalid("credential signature verification failed") from exc

    issuer = payload.get("iss")
    if not settings.caller_jwt_issuer or issuer != settings.caller_jwt_issuer:
        raise _credential_invalid("credential issuer is not the configured platform issuer")
    audience = payload.get("aud")
    if not settings.caller_jwt_audience or audience != settings.caller_jwt_audience:
        raise _credential_invalid("credential audience is not this service")

    now = datetime.now(UTC).timestamp()
    expiry = payload.get("exp")
    if not isinstance(expiry, (int, float)):
        raise _credential_invalid("credential does not carry a numeric expiry")
    if now >= float(expiry):
        raise _credential_invalid("credential has expired")
    not_before = payload.get("nbf")
    if not_before is not None:
        if not isinstance(not_before, (int, float)):
            raise _credential_invalid("credential not-before claim is not numeric")
        if now < float(not_before):
            raise _credential_invalid("credential is not valid yet")

    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject.strip():
        raise _credential_invalid("credential does not carry a caller subject")
    return subject.strip()


def _extract_bearer_token(authorization: str | None) -> str:
    value = (authorization or "").strip()
    if not value:
        raise _credential_invalid(
            "a platform-issued service credential is required in the Authorization header"
        )
    scheme, _, token = value.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise _credential_invalid("the Authorization header must carry a Bearer credential")
    return token.strip()


def _decode_compact_jws(token: str) -> tuple[dict[str, Any], dict[str, Any], bytes, bytes]:
    segments = token.split(".")
    if len(segments) != 3:
        raise _credential_invalid("credential is not a compact JWS")
    header_segment, payload_segment, signature_segment = segments
    header = _decode_json_segment(header_segment, "header")
    payload = _decode_json_segment(payload_segment, "payload")
    signature = _decode_base64url(signature_segment, "signature")
    signing_input = f"{header_segment}.{payload_segment}".encode("ascii")
    return header, payload, signing_input, signature


def _decode_json_segment(segment: str, name: str) -> dict[str, Any]:
    raw = _decode_base64url(segment, name)
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise _credential_invalid(f"credential {name} is not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise _credential_invalid(f"credential {name} is not a JSON object")
    return parsed


def _decode_base64url(segment: str, name: str) -> bytes:
    padded = segment + "=" * (-len(segment) % 4)
    try:
        return base64.urlsafe_b64decode(padded.encode("ascii"))
    except (binascii.Error, ValueError, UnicodeEncodeError) as exc:
        raise _credential_invalid(f"credential {name} is not valid base64url") from exc


def _credential_invalid(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"detail": detail, "error_code": CALLER_CREDENTIAL_ERROR_CODE},
    )
