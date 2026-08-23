from __future__ import annotations

from collections.abc import AsyncGenerator, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.config import settings

AUTHENTICATED_CALLER_HEADER = "X-Caller-App"
AUTHENTICATED_CALLER_TRUST_SOURCE = "trusted_http_header"
VERIFIED_AUTHENTICATED_CALLER_TRUST_SOURCES = frozenset({"verified_service_jwt", "mtls_san"})
LOCAL_HEADER_CALLER_STARTUP_FINDING = (
    "caller identity: trusted HTTP header mode is local-only; privileged all-tenant audit "
    "reads fail closed outside the local warn/observe posture until verified service identity "
    "is delivered by issue #149"
)


class AuthenticatedCaller(BaseModel):
    caller_app: str = Field(description="Authenticated caller application identity.")
    trust_source: str = Field(description="Trusted source used to resolve the caller identity.")


def is_local_header_caller_posture() -> bool:
    """Return whether the documented local-only header identity posture is active."""

    return (
        settings.startup_readiness_policy == "warn" and settings.readiness_probe_policy == "observe"
    )


def is_privileged_caller_identity_accepted(caller: AuthenticatedCaller) -> bool:
    """Accept privileged identity only when verified or explicitly local-only."""

    if caller.trust_source in VERIFIED_AUTHENTICATED_CALLER_TRUST_SOURCES:
        return True
    return (
        caller.trust_source == AUTHENTICATED_CALLER_TRUST_SOURCE
        and is_local_header_caller_posture()
    )


_authenticated_caller: ContextVar[AuthenticatedCaller | None] = ContextVar(
    "authenticated_lotus_ai_caller",
    default=None,
)


async def require_authenticated_caller(
    x_caller_app: Annotated[str | None, Header(alias=AUTHENTICATED_CALLER_HEADER)] = None,
) -> AsyncGenerator[AuthenticatedCaller, None]:
    caller_app = (x_caller_app or "").strip()
    if not caller_app:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=("Authenticated caller identity is required for this protected lotus-ai route."),
        )
    authenticated_caller = AuthenticatedCaller(
        caller_app=caller_app,
        trust_source=AUTHENTICATED_CALLER_TRUST_SOURCE,
    )
    token = _authenticated_caller.set(authenticated_caller)
    try:
        yield authenticated_caller
    finally:
        _authenticated_caller.reset(token)


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
