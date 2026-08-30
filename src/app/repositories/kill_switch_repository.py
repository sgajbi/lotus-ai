from __future__ import annotations

from typing import Protocol

from app.contracts.kill_switches import KillSwitchActivationRecord


class KillSwitchRepository(Protocol):
    def list_activations(self) -> list[KillSwitchActivationRecord]: ...

    def get_activation(self, switch_id: str) -> KillSwitchActivationRecord | None: ...

    def upsert_activation(self, activation: KillSwitchActivationRecord) -> None: ...
