from __future__ import annotations

from collections.abc import AsyncGenerator, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.config import settings
from app.http.caller_credential import (
    CALLER_TRUST_MODE_HEADER,
    CALLER_TRUST_MODE_VERIFIED_JWT,
    verify_caller_credential,
)

AUTHENTICATED_CALLER_HEADER = "X-Caller-App"
AUTHENTICATED_CALLER_TRUST_SOURCE = "trusted_http_header"
VERIFIED_AUTHENTICATED_CALLER_TRUST_SOURCES = frozenset({"verified_service_jwt", "mtls_san"})


class AuthenticatedCaller(BaseModel):
    caller_app: str = Field(description="Authenticated caller application identity.")
    trust_source: str = Field(description="Trusted source used to resolve the caller identity.")
    credential_key_id: str | None = Field(
        default=None,
        description=(
            "Key id of the platform-issued credential that verified this caller; "
            "null under header trust."
        ),
    )


def is_privileged_caller_identity_accepted(caller: AuthenticatedCaller) -> bool:
    """Accept privileged identity only when verified or explicitly enabled for local use."""

    if caller.trust_source in VERIFIED_AUTHENTICATED_CALLER_TRUST_SOURCES:
        return True
    return (
        caller.trust_source == AUTHENTICATED_CALLER_TRUST_SOURCE
        and settings.local_header_caller_identity_enabled
    )


_authenticated_caller: ContextVar[AuthenticatedCaller | None] = ContextVar(
    "authenticated_lotus_ai_caller",
    default=None,
)


async def require_authenticated_caller(
    x_caller_app: Annotated[str | None, Header(alias=AUTHENTICATED_CALLER_HEADER)] = None,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> AsyncGenerator[AuthenticatedCaller, None]:
    authenticated_caller = _resolve_authenticated_caller(
        x_caller_app=x_caller_app,
        authorization=authorization,
    )
    token = _authenticated_caller.set(authenticated_caller)
    try:
        yield authenticated_caller
    finally:
        _authenticated_caller.reset(token)


def _resolve_authenticated_caller(
    *,
    x_caller_app: str | None,
    authorization: str | None,
) -> AuthenticatedCaller:
    caller_app = (x_caller_app or "").strip()
    if settings.caller_trust_mode != CALLER_TRUST_MODE_HEADER:
        # Any non-header mode verifies the credential; an unknown mode never
        # falls open to header trust (it is also a startup finding).
        credential = verify_caller_credential(authorization)
        if caller_app and caller_app != credential.subject:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=("X-Caller-App does not match the verified caller credential subject."),
            )
        return AuthenticatedCaller(
            caller_app=credential.subject,
            trust_source=CALLER_TRUST_MODE_VERIFIED_JWT,
            credential_key_id=credential.key_id,
        )
    if not caller_app:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=("Authenticated caller identity is required for this protected lotus-ai route."),
        )
    return AuthenticatedCaller(
        caller_app=caller_app,
        trust_source=AUTHENTICATED_CALLER_TRUST_SOURCE,
    )


def get_authenticated_caller() -> AuthenticatedCaller | None:
    return _authenticated_caller.get()


@contextmanager
def bind_internal_authenticated_caller(
    *,
    caller_app: str,
    trust_source: str,
) -> Iterator[AuthenticatedCaller]:
    authenticated_caller = AuthenticatedCaller(
        caller_app=caller_app,
        trust_source=trust_source,
    )
    token = _authenticated_caller.set(authenticated_caller)
    try:
        yield authenticated_caller
    finally:
        _authenticated_caller.reset(token)


def require_authenticated_caller_matches(declared_caller_app: str) -> AuthenticatedCaller:
    authenticated_caller = get_authenticated_caller()
    if authenticated_caller is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=("Authenticated caller identity is required for this protected lotus-ai route."),
        )
    if authenticated_caller.caller_app != declared_caller_app:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Request caller_app does not match the authenticated HTTP caller identity.",
        )
    return authenticated_caller


AuthenticatedCallerDependency = Annotated[
    AuthenticatedCaller,
    Depends(require_authenticated_caller),
]
