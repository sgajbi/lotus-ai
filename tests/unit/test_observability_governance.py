from types import SimpleNamespace

from _pytest.monkeypatch import MonkeyPatch

from app.services.observability_governance import build_observability_governance_status


def test_observability_governance_mentions_split_degradation_when_present(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.observability_governance.build_deployment_split_runtime_status",
        lambda: SimpleNamespace(degraded=True),
    )

    governance = build_observability_governance_status()

    assert any("split-plane degradation" in line for line in governance.governance_summary)
