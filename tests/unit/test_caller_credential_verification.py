"""Verified service-caller credentials (issue #149, S1).

In verified_service_jwt mode the caller identity comes from a
platform-issued EdDSA credential: every malformation, signature failure,
issuer/audience mismatch, and expiry is a 401 CALLER_CREDENTIAL_INVALID
that never falls back to header trust; rotation accepts a second key id;
header mode in the promoted profile is a blocking startup finding.
"""

from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.config import settings
from app.http.authenticated_caller import _resolve_authenticated_caller
from app.http.caller_credential import (
    parse_caller_credential_public_keys,
    verify_caller_credential,
)
from app.main import app
from app.services.startup_policy import evaluate_startup_readiness
from tests.support.caller_credentials import (
    TEST_AUDIENCE,
    TEST_ISSUER,
    generate_caller_signing_key,
    mint_caller_credential,
    public_keys_setting,
)

KEY = generate_caller_signing_key()
ROTATED_KEY = generate_caller_signing_key()
INTRUDER_KEY = generate_caller_signing_key()


def _verified_mode_settings() -> None:
    settings.caller_trust_mode = "verified_service_jwt"
    settings.caller_jwt_issuer = TEST_ISSUER
    settings.caller_jwt_audience = TEST_AUDIENCE
    settings.caller_jwt_public_keys = public_keys_setting(
        platform_2026_08=KEY, platform_2026_09=ROTATED_KEY
    )


def _bearer(**overrides: object) -> str:
    kwargs: dict[str, object] = {
        "signing_key": KEY,
        "key_id": "platform_2026_08",
        "subject": "lotus-advise",
    }
    kwargs.update(overrides)
    return "Bearer " + mint_caller_credential(**kwargs)  # type: ignore[arg-type]


def _assert_credential_invalid(exc_info: pytest.ExceptionInfo[HTTPException]) -> None:
    assert exc_info.value.status_code == 401
    detail = exc_info.value.detail
    assert isinstance(detail, dict)
    assert detail["error_code"] == "CALLER_CREDENTIAL_INVALID"


def test_valid_credential_yields_the_verified_subject() -> None:
    _verified_mode_settings()
    verified = verify_caller_credential(_bearer())
    assert verified.subject == "lotus-advise"
    assert verified.key_id == "platform_2026_08"


def test_rotation_accepts_the_second_active_key_id() -> None:
    _verified_mode_settings()
    verified = verify_caller_credential(_bearer(signing_key=ROTATED_KEY, key_id="platform_2026_09"))
    assert verified.subject == "lotus-advise"
    assert verified.key_id == "platform_2026_09"


@pytest.mark.parametrize(
    "overrides",
    [
        {"expires_in_seconds": -30},
        {"issuer": "https://intruder.example/issuer"},
        {"audience": "lotus-core"},
        {"key_id": "unknown_kid"},
        {"signing_key": INTRUDER_KEY},
        {"algorithm": "HS256"},
        {"subject": "  "},
        {"extra_claims": {"nbf": 4102444800}},
    ],
    ids=[
        "expired",
        "wrong-issuer",
        "wrong-audience",
        "unknown-kid",
        "wrong-signature",
        "non-eddsa-alg",
        "blank-subject",
        "not-yet-valid",
    ],
)
def test_invalid_credentials_are_rejected(overrides: dict[str, object]) -> None:
    _verified_mode_settings()
    with pytest.raises(HTTPException) as exc_info:
        verify_caller_credential(_bearer(**overrides))
    _assert_credential_invalid(exc_info)


@pytest.mark.parametrize(
    "authorization",
    [None, "", "Bearer ", "Basic dXNlcjpwYXNz", "Bearer not.a", "Bearer a.b.c"],
    ids=["missing", "empty", "bare-bearer", "wrong-scheme", "two-segments", "garbage"],
)
def test_malformed_authorization_is_rejected(authorization: str | None) -> None:
    _verified_mode_settings()
    with pytest.raises(HTTPException) as exc_info:
        verify_caller_credential(authorization)
    _assert_credential_invalid(exc_info)


def _raw_token(header: object, payload: object, *, sign_with: object = None) -> str:
    import base64
    import json as jsonlib

    def encode(value: object) -> str:
        if isinstance(value, bytes):
            raw = value
        else:
            raw = jsonlib.dumps(value, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    signing_input = f"{encode(header)}.{encode(payload)}"
    key = sign_with if sign_with is not None else KEY
    signature = key.sign(signing_input.encode("ascii"))  # type: ignore[attr-defined]
    return signing_input + "." + base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")


@pytest.mark.parametrize(
    ("header", "payload"),
    [
        ({"alg": "EdDSA", "typ": "JWT"}, {"sub": "lotus-advise"}),
        ({"alg": "EdDSA", "typ": "JWT", "kid": ""}, {"sub": "lotus-advise"}),
        (b"not json at all", {"sub": "lotus-advise"}),
        (["not", "an", "object"], {"sub": "lotus-advise"}),
    ],
    ids=["missing-kid", "empty-kid", "header-not-json", "header-not-an-object"],
)
def test_malformed_token_structures_are_rejected(header: object, payload: object) -> None:
    _verified_mode_settings()
    with pytest.raises(HTTPException) as exc_info:
        verify_caller_credential("Bearer " + _raw_token(header, payload))
    _assert_credential_invalid(exc_info)


def test_missing_expiry_and_non_numeric_not_before_are_rejected() -> None:
    _verified_mode_settings()
    header = {"alg": "EdDSA", "typ": "JWT", "kid": "platform_2026_08"}
    with pytest.raises(HTTPException) as exc_info:
        verify_caller_credential(
            "Bearer "
            + _raw_token(header, {"iss": TEST_ISSUER, "aud": TEST_AUDIENCE, "sub": "lotus-advise"})
        )
    _assert_credential_invalid(exc_info)

    with pytest.raises(HTTPException) as exc_info:
        verify_caller_credential(
            "Bearer "
            + _raw_token(
                header,
                {
                    "iss": TEST_ISSUER,
                    "aud": TEST_AUDIENCE,
                    "sub": "lotus-advise",
                    "exp": 4102444800,
                    "nbf": "later",
                },
            )
        )
    _assert_credential_invalid(exc_info)


def test_unconfigured_keys_reject_a_well_formed_credential() -> None:
    _verified_mode_settings()
    settings.caller_jwt_public_keys = ""
    with pytest.raises(HTTPException) as exc_info:
        verify_caller_credential(_bearer())
    _assert_credential_invalid(exc_info)


def test_verification_never_downgrades_to_the_header_identity() -> None:
    _verified_mode_settings()
    with pytest.raises(HTTPException) as exc_info:
        _resolve_authenticated_caller(x_caller_app="lotus-advise", authorization=None)
    _assert_credential_invalid(exc_info)


def test_header_claiming_a_different_caller_than_the_credential_is_rejected() -> None:
    _verified_mode_settings()
    with pytest.raises(HTTPException) as exc_info:
        _resolve_authenticated_caller(x_caller_app="lotus-gateway", authorization=_bearer())
    assert exc_info.value.status_code == 403

    caller = _resolve_authenticated_caller(x_caller_app="lotus-advise", authorization=_bearer())
    assert caller.caller_app == "lotus-advise"
    assert caller.trust_source == "verified_service_jwt"


def test_header_mode_keeps_header_trust_even_when_keys_are_configured() -> None:
    _verified_mode_settings()
    settings.caller_trust_mode = "header"
    caller = _resolve_authenticated_caller(x_caller_app="lotus-advise", authorization=None)
    assert caller.trust_source == "trusted_http_header"


def test_bound_route_accepts_a_credential_and_refuses_a_bare_header() -> None:
    _verified_mode_settings()
    payload = {
        "pack_id": "advisor_brief.pack",
        "version": "v1",
        "caller_app": "lotus-gateway",
        "environment": "QA",
        "caller_identity_class": "INTERNAL_SERVICE",
        "workflow_surface": "advisor-brief-panel",
    }
    with TestClient(app) as client:
        refused = client.post(
            "/platform/workflow-packs/eligibility/evaluate",
            json=payload,
            headers={"X-Caller-App": "lotus-gateway"},
        )
        assert refused.status_code == 401
        assert refused.json()["error_code"] == "CALLER_CREDENTIAL_INVALID"

        accepted = client.post(
            "/platform/workflow-packs/eligibility/evaluate",
            json=payload,
            headers={"Authorization": _bearer(subject="lotus-gateway")},
        )
        assert accepted.status_code == 200
        assert accepted.json()["allowed"] is True


def test_evaluation_condition_promoted_profile_end_to_end(tmp_path: Path) -> None:
    """Issue #149 evaluation condition: with promoted-profile settings, a
    request carrying only X-Caller-App is rejected 401; the same request with
    a valid platform-issued credential succeeds and the audit record's caller
    equals the credential subject, with the trust facts recorded."""

    from app.services.audit_store import get_audit_store
    from app.contracts.audit_access import INTERNAL_AGGREGATE_AUDIT_SCOPE
    from tests.support.migration_runner import upgrade_database_to_head

    settings.runtime_profile = "promoted"
    settings.workflow_pack_admission_store_mode = "sqlalchemy"
    database_url = f"sqlite:///{tmp_path / 'eval-condition-149.db'}"
    settings.database_url = database_url
    upgrade_database_to_head(database_url)
    _verified_mode_settings()

    payload = {
        "task_id": "explain.v1",
        "input_mode": "STRUCTURED_CONTEXT",
        "caller": {
            "caller_app": "lotus-manage",
            "correlation_id": "corr-149-s3",
            "requested_by": "ops.user@lotus",
            "tenant_id": "tenant-sg-001",
        },
        "context": {
            "summary": "Explain rebalance outcome",
            "payload": {"status": "BLOCKED", "violations": 2},
            "source_refs": ["lotus-manage:run:reb_149"],
        },
        "expected_output_label": "EXPLANATION_ONLY",
    }
    with TestClient(app) as client:
        refused = client.post(
            "/ai/tasks/execute", json=payload, headers={"X-Caller-App": "lotus-manage"}
        )
        assert refused.status_code == 401
        assert refused.json()["error_code"] == "CALLER_CREDENTIAL_INVALID"

        accepted = client.post(
            "/ai/tasks/execute",
            json=payload,
            headers={
                "Authorization": _bearer(
                    subject="lotus-manage", extra_claims={"jti": "tok-149-e2e"}
                )
            },
        )
        assert accepted.status_code == 200
        assert accepted.json()["status"] == "COMPLETED"

    records = get_audit_store().list(scope=INTERNAL_AGGREGATE_AUDIT_SCOPE, limit=5)
    record = next(r for r in records if r.correlation_id == "corr-149-s3")
    assert record.caller_app == "lotus-manage"
    assert record.authorization.authenticated_caller_app == "lotus-manage"
    assert record.authorization.caller_identity_source == "verified_service_jwt"
    assert record.authorization.caller_identity_bound is True
    assert record.authorization.caller_credential_key_id == "platform_2026_08"
    # The issuer-assigned token id rides the decision so a future revocation
    # list can name exactly this token (issue #233).
    assert record.authorization.caller_credential_token_id == "tok-149-e2e"


def test_public_key_parsing_rejects_each_malformation() -> None:
    with pytest.raises(ValueError, match="no caller credential public keys"):
        parse_caller_credential_public_keys("   ")
    with pytest.raises(ValueError, match="not valid JSON"):
        parse_caller_credential_public_keys("{nope")
    with pytest.raises(ValueError, match="non-empty JSON object"):
        parse_caller_credential_public_keys("[]")
    with pytest.raises(ValueError, match="non-empty JSON object"):
        parse_caller_credential_public_keys("{}")
    with pytest.raises(ValueError, match="must be a string"):
        parse_caller_credential_public_keys('{"kid": 5}')
    with pytest.raises(ValueError, match="not valid base64"):
        parse_caller_credential_public_keys('{"kid": "@@@"}')
    with pytest.raises(ValueError, match="not a raw Ed25519 public key"):
        parse_caller_credential_public_keys('{"kid": "AAAA"}')
    with pytest.raises(ValueError, match="key ids must be non-empty"):
        parse_caller_credential_public_keys('{" ": "AAAA"}')


def test_startup_findings_cover_the_caller_trust_posture() -> None:
    # Header trust in the promoted profile is a finding.
    settings.runtime_profile = "promoted"
    settings.workflow_pack_admission_store_mode = "sqlalchemy"
    findings = evaluate_startup_readiness().findings
    assert any("header caller trust cannot be the identity boundary" in f for f in findings)

    # Verified mode without issuer, audience, or keys names each gap.
    settings.runtime_profile = "local"
    settings.caller_trust_mode = "verified_service_jwt"
    findings = evaluate_startup_readiness().findings
    assert any("requires a configured credential issuer" in f for f in findings)
    assert any("requires a configured credential audience" in f for f in findings)
    assert any("no caller credential public keys" in f for f in findings)

    # An unknown mode is a finding and nothing else about it is evaluated.
    settings.caller_trust_mode = "certificate"
    findings = evaluate_startup_readiness().findings
    assert any("unknown caller trust mode 'certificate'" in f for f in findings)

    # Fully configured verified mode carries no caller-identity findings.
    _verified_mode_settings()
    assert not [f for f in evaluate_startup_readiness().findings if "caller identity" in f]

    # Header mode outside promoted carries none either.
    settings.caller_trust_mode = "header"
    assert not [f for f in evaluate_startup_readiness().findings if "caller identity" in f]


def test_credential_lifetime_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    """Issue #233: a leaked token must not replay for an issuer-chosen
    unbounded lifetime. The accepted window (exp - iat) is bounded by
    configuration; with iat required and never in the future, that also
    bounds the remaining lifetime."""

    _verified_mode_settings()

    # The exact boundary is accepted; one second past it is not.
    at_limit = _resolve_authenticated_caller(
        x_caller_app=None, authorization=_bearer(expires_in_seconds=3600)
    )
    assert at_limit.caller_app == "lotus-advise"

    with pytest.raises(HTTPException) as exc_info:
        verify_caller_credential(_bearer(expires_in_seconds=3601))
    _assert_credential_invalid(exc_info)
    detail = exc_info.value.detail
    assert isinstance(detail, dict)
    assert "lifetime exceeds" in detail["detail"]


def test_missing_future_and_non_numeric_issued_at_are_rejected() -> None:
    _verified_mode_settings()
    import time as _time

    for overrides in (
        {"omit_claims": ("iat",)},
        {"extra_claims": {"iat": "yesterday"}},
        {"extra_claims": {"iat": int(_time.time()) + 600}},
    ):
        with pytest.raises(HTTPException) as exc_info:
            verify_caller_credential(_bearer(**overrides))
        _assert_credential_invalid(exc_info)


def test_credential_header_must_declare_typ_jwt() -> None:
    _verified_mode_settings()
    for token_type in (None, "JOSE"):
        with pytest.raises(HTTPException) as exc_info:
            verify_caller_credential(_bearer(token_type=token_type))
        _assert_credential_invalid(exc_info)
        detail = exc_info.value.detail
        assert isinstance(detail, dict)
        assert "typ JWT" in detail["detail"]


def test_token_id_is_carried_when_present_and_validated() -> None:
    """An optional jti is verified in shape, carried on the identity, and
    absent stays honestly None - the future revocation surface (issue #233)."""

    _verified_mode_settings()

    with_jti = verify_caller_credential(_bearer(extra_claims={"jti": "tok-42"}))
    assert with_jti.token_id == "tok-42"

    without_jti = verify_caller_credential(_bearer())
    assert without_jti.token_id is None

    for bad_jti in ("", "   ", 123, "x" * 129):
        with pytest.raises(HTTPException) as exc_info:
            verify_caller_credential(_bearer(extra_claims={"jti": bad_jti}))
        _assert_credential_invalid(exc_info)

    caller = _resolve_authenticated_caller(
        x_caller_app=None, authorization=_bearer(extra_claims={"jti": "tok-77"})
    )
    assert caller.credential_token_id == "tok-77"
