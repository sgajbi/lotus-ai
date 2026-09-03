from __future__ import annotations

from collections.abc import Sequence

from typing import Protocol

from app.contracts.kill_switches import KillSwitchActivationRecord


class KillSwitchRepository(Protocol):
    def list_activations(self) -> list[KillSwitchActivationRecord]: ...

    def delete_activations(self, switch_ids: Sequence[str]) -> int:
        """Delete non-enforcing activation evidence by id (issue #158, S2b)."""
        ...

    def get_activation(self, switch_id: str) -> KillSwitchActivationRecord | None: ...

    def upsert_activation(self, activation: KillSwitchActivationRecord) -> None: ...
