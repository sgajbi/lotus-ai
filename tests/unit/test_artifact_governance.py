from pathlib import Path

from pytest import MonkeyPatch

from app.config import settings
from app.services import artifact_activation_readiness as artifact_activation_module
from app.services.artifact_activation_readiness import build_artifact_activation_readiness
from app.services.artifact_governance import build_artifact_governance_status
from app.services.artifact_runbook_readiness import build_artifact_runbook_readiness
from tests.support.migration_runner import upgrade_database_to_head


def test_artifact_activation_readiness_blocks_memory_posture() -> None:
    settings.artifact_store_mode = "memory"
    settings.artifact_object_store_mode = "memory"
    settings.artifact_object_store_root = None

    readiness = build_artifact_activation_readiness()

    assert readiness.activation_ready is False
    assert readiness.lifecycle_controls_ready is True
    assert readiness.cutover_domain_count == 3
    assert any("not restart-safe" in finding for finding in readiness.blocking_findings)


def test_artifact_activation_readiness_blocks_filesystem_fallback_posture(
    tmp_path: Path,
) -> None:
    settings.artifact_store_mode = "sqlalchemy"
    settings.artifact_object_store_mode = "filesystem"
    settings.artifact_object_store_root = str(tmp_path / "artifact-objects")
    settings.database_url = f"sqlite:///{tmp_path / 'artifact-governance.db'}"
    upgrade_database_to_head(settings.database_url)

    readiness = build_artifact_activation_readiness()

    assert readiness.activation_ready is False
    assert any("development fallback" in finding for finding in readiness.blocking_findings)


def test_artifact_runbook_readiness_is_complete() -> None:
    readiness = build_artifact_runbook_readiness()

    assert readiness.runbook_ready is True
    assert readiness.required_item_count == 3
    assert readiness.completed_required_item_count == 3


def test_artifact_governance_status_combines_activation_and_runbook() -> None:
    settings.artifact_store_mode = "memory"
    settings.artifact_object_store_mode = "memory"
    settings.artifact_object_store_root = None

    governance = build_artifact_governance_status()

    assert governance.governance_ready is False
    assert governance.activation_readiness.activation_ready is False
    assert governance.runbook_readiness.runbook_ready is True
    assert governance.blocking_area_count == 1


def test_artifact_activation_readiness_blocks_missing_cutover_breadth(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.artifact_store_mode = "memory"
    settings.artifact_object_store_mode = "memory"
    settings.artifact_object_store_root = None
    monkeypatch.setattr(artifact_activation_module, "ACTIVE_CUTOVER_DOMAINS", ["evaluation"])

    readiness = build_artifact_activation_readiness()

    assert readiness.activation_ready is False
    assert any("too narrow" in finding for finding in readiness.blocking_findings)


def test_artifact_activation_readiness_blocks_unready_metadata_and_object_store() -> None:
    settings.artifact_store_mode = "unsupported"
    settings.artifact_object_store_mode = "filesystem"
    settings.artifact_object_store_root = None

    readiness = build_artifact_activation_readiness()

    assert readiness.activation_ready is False
    assert any("metadata store is not ready" in finding for finding in readiness.blocking_findings)
    assert any(
        "object-store backend is not ready" in finding for finding in readiness.blocking_findings
    )
