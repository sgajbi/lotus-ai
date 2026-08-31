"""Registered-caller gate for every protected route (issue #149, S2).

Caller identity alone is not authorization: this dependency runs after
``require_authenticated_caller`` and requires the identified caller to be a
registered, ACTIVE caller-policy entry before any protected route executes.
Route- and service-level capability rules (task execution, provider control,
audit scopes, ...) still apply on top; this gate closes the gap where
diagnostic read surfaces answered to any identity string.
"""

from __future__ import annotations

from fastapi import HTTPException, status

from app.contracts.access_control import AuthorizationCapabilityType
from app.http.authenticated_caller import get_authenticated_caller
from app.services.access_control_authorization import authorize_request, require_authorized


async def require_registered_caller() -> None:
    authenticated_caller = get_authenticated_caller()
    if authenticated_caller is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=("Authenticated caller identity is required for this protected lotus-ai route."),
        )
    require_authorized(
        authorize_request(
            caller_app=authenticated_caller.caller_app,
            capability_type=AuthorizationCapabilityType.PLATFORM_READ,
        )
    )
