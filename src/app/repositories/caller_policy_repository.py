from __future__ import annotations

from typing import Protocol

from app.contracts.access_control import CallerPolicyDescriptor


class CallerPolicyRepository(Protocol):
    def list_policies(self) -> list[CallerPolicyDescriptor]: ...

    def get_policy(self, caller_app: str) -> CallerPolicyDescriptor | None: ...
