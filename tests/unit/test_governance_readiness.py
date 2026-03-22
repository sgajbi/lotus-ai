from dataclasses import dataclass

from app.services.governance_readiness import (
    summarize_activation_items,
    summarize_governance_flags,
)


@dataclass(frozen=True)
class _ActivationItem:
    required_for_activation: bool
    status: str


def test_summarize_activation_items_counts_required_and_completed_items() -> None:
    items = [
        _ActivationItem(required_for_activation=True, status="FOUNDATION_DOCUMENTED"),
        _ActivationItem(required_for_activation=True, status="READY"),
        _ActivationItem(required_for_activation=True, status="ACTIVATED"),
        _ActivationItem(required_for_activation=False, status="READY"),
    ]

    required_item_count, completed_required_item_count = summarize_activation_items(items)

    assert required_item_count == 3
    assert completed_required_item_count == 2


def test_summarize_governance_flags_derives_readiness_and_blocking_count() -> None:
    governance_ready, blocking_area_count = summarize_governance_flags(True, False, True, False)

    assert governance_ready is False
    assert blocking_area_count == 2
