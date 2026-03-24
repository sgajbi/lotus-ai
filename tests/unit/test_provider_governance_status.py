from _pytest.monkeypatch import MonkeyPatch

from app.contracts.providers import ProviderExpansionPolicyDescriptor
from app.services.provider_governance_status import build_provider_governance_status


def test_provider_governance_status_reports_blocked_foundation_posture() -> None:
    status = build_provider_governance_status()

    assert status.service == "lotus-ai"
    assert status.governance_ready is False
    assert status.blocking_area_count == 3
    assert status.activation_readiness.activation_ready is False
    assert status.runbook_readiness.runbook_ready is False
    assert status.evidence_readiness.evidence_ready is False
    assert status.expansion_policy.bounded_expansion_enabled is True
    assert status.expansion_policy.expansion_blocked is False
    assert len(status.governance_summary) == 3
    assert "runtime-backed approval gate summary" in status.governance_summary[2]


def test_provider_governance_status_blocks_when_expansion_policy_is_exhausted(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.provider_governance_status.build_provider_expansion_policy",
        lambda: ProviderExpansionPolicyDescriptor(
            bounded_expansion_enabled=True,
            expansion_blocked=True,
            findings=["Provider breadth exceeded the slot model."],
            capability_rules=[],
        ),
    )

    status = build_provider_governance_status()

    assert status.governance_ready is False
    assert status.blocking_area_count == 4
    assert status.expansion_policy.expansion_blocked is True
    assert "bounded slot model" in status.governance_summary[-1]
