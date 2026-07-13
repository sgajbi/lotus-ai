from pathlib import Path
from types import SimpleNamespace

from _pytest.monkeypatch import MonkeyPatch

from app.config import settings
from app.services.observability_governance import build_observability_governance_status
from tests.support.migration_runner import upgrade_database_to_head


def test_observability_governance_mentions_split_degradation_when_present(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.observability_governance.build_deployment_split_runtime_status",
        lambda: SimpleNamespace(degraded=True, status_summary=["split runtime degraded"]),
    )

    governance = build_observability_governance_status()

    assert any("split-plane degradation" in line for line in governance.governance_summary)


def test_observability_governance_blocks_on_ai_no_sensitive_telemetry(
    tmp_path: Path,
) -> None:
    settings.audit_store_mode = "sqlalchemy"
    settings.access_control_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'observability-governance.db'}"
    upgrade_database_to_head(settings.database_url)

    governance = build_observability_governance_status()

    assert governance.governance_ready is False
    assert governance.activation_readiness.activation_ready is False
    assert any(
        "no-sensitive-content telemetry" in item
        for item in governance.activation_readiness.blocking_findings
    )
    assert any(
        "AI no-sensitive telemetry posture" in item for item in governance.governance_summary
    )
