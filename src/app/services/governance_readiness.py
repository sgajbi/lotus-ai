from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol


_READY_STATUSES = frozenset({"READY", "ACTIVATED"})


class ActivationScopedItem(Protocol):
    @property
    def required_for_activation(self) -> bool: ...

    @property
    def status(self) -> str: ...


def summarize_activation_items(items: Iterable[ActivationScopedItem]) -> tuple[int, int]:
    materialized_items = list(items)
    required_item_count = sum(1 for item in materialized_items if item.required_for_activation)
    completed_required_item_count = sum(
        1
        for item in materialized_items
        if item.required_for_activation and item.status in _READY_STATUSES
    )
    return required_item_count, completed_required_item_count


def summarize_governance_flags(*flags: bool) -> tuple[bool, int]:
    governance_ready = all(flags)
    blocking_area_count = sum(1 for flag in flags if not flag)
    return governance_ready, blocking_area_count
