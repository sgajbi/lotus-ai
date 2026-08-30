from __future__ import annotations

from app.contracts.kill_switches import KillSwitchActivationRecord


class InMemoryKillSwitchRepository:
    def __init__(self) -> None:
        self._activations: dict[str, KillSwitchActivationRecord] = {}

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
