from fastapi import HTTPException

from app.http.authenticated_caller import (
    bind_internal_authenticated_caller,
    require_authenticated_caller_matches,
)


def test_require_authenticated_caller_matches_rejects_missing_trusted_identity() -> None:
    try:
        require_authenticated_caller_matches("lotus-manage")
    except HTTPException as exc:
        assert exc.status_code == 403
        assert "Authenticated caller identity is required" in str(exc.detail)
    else:
        raise AssertionError("Expected missing trusted caller identity to be rejected.")


def test_require_authenticated_caller_matches_rejects_spoofed_declared_identity() -> None:
    with bind_internal_authenticated_caller(
        caller_app="lotus-platform",
        trust_source="unit-test",
    ):
        try:
            require_authenticated_caller_matches("lotus-manage")
        except HTTPException as exc:
            assert exc.status_code == 403
            assert "does not match" in str(exc.detail)
        else:
            raise AssertionError("Expected spoofed caller identity to be rejected.")


def test_require_authenticated_caller_matches_returns_trusted_identity() -> None:
    with bind_internal_authenticated_caller(
        caller_app="lotus-manage",
        trust_source="unit-test",
    ):
        caller = require_authenticated_caller_matches("lotus-manage")

    assert caller.caller_app == "lotus-manage"
    assert caller.trust_source == "unit-test"
