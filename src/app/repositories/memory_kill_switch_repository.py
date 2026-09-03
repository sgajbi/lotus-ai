from __future__ import annotations

from collections.abc import Sequence

from app.contracts.kill_switches import KillSwitchActivationRecord


class InMemoryKillSwitchRepository:
    def __init__(self) -> None:
        self._activations: dict[str, KillSwitchActivationRecord] = {}

    def delete_activations(self, switch_ids: Sequence[str]) -> int:
        deleted = 0
        for switch_id in switch_ids:
            if self._activations.pop(switch_id, None) is not None:
                deleted += 1
        return deleted

    def list_activations(self) -> list[KillSwitchActivationRecord]:
        return sorted(
            (activation.model_copy(deep=True) for activation in self._activations.values()),
            key=lambda activation: activation.activated_at,
            reverse=True,
        )

    def get_activation(self, switch_id: str) -> KillSwitchActivationRecord | None:
        activation = self._activations.get(switch_id)
        return activation.model_copy(deep=True) if activation is not None else None

    def upsert_activation(self, activation: KillSwitchActivationRecord) -> None:
        self._activations[activation.switch_id] = activation.model_copy(deep=True)
