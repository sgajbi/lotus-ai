"""Model-catalogue seeding, identity guard and store selection (issue #175, slice 1).

These pin the seed semantics that make the catalogue honest: configuration is
catalogued but never approved, approval evidence comes only from the model-risk
inventory, an unpinned revision is visibly unpinned, and re-seeding never
duplicates rows or rewrites provenance.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from app.config import settings
from app.contracts.model_catalogue import (
    ModelCatalogueSeedSource,
    ModelLifecycleState,
    derive_model_catalogue_entry_id,
)
from app.services.model_catalogue import (
    build_model_catalogue_response,
    build_seed_model_catalogue_entries,
    ensure_model_catalogue_seeded,
    upsert_model_catalogue_entry,
)
from app.repositories.sqlalchemy_model_catalogue_repository import (
    SqlAlchemyModelCatalogueRepository,
)
from app.services.model_catalogue_store import (
    get_model_catalogue_repository,
    reset_model_catalogue_store_cache,
)

APPROVED_INVENTORY_JSON = json.dumps(
    [
        {
            "provider_id": "text.openai",
            "provider_mode": "openai",
            "model_id": "gpt-5.2",
            "model_version": "gpt-5.2-2026-05-01",
            "workflow_pack_ids": ["advisor_brief.pack"],
            "approval_ref": "mrm-approval-2026-014",
            "approved_from_utc": "2026-05-01T00:00:00Z",
            "approved_until_utc": "2027-05-01T00:00:00Z",
        }
    ]
)


@pytest.fixture(autouse=True)
def _fresh_catalogue_store() -> Iterator[None]:
    reset_model_catalogue_store_cache()
    yield
    reset_model_catalogue_store_cache()


@pytest.fixture
def _local_unpinned_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "provider_mode", "local_openai_compatible")
    monkeypatch.setattr(settings, "live_text_provider_id", "text.local")
    monkeypatch.setattr(settings, "live_text_model_id", "qwen3:8b")
    monkeypatch.setattr(settings, "live_text_model_version", None)
    monkeypatch.setattr(settings, "workflow_run_model_risk_inventory_json", "[]")


def test_entry_id_derivation_is_deterministic_and_deployment_aware() -> None:
    bare = derive_model_catalogue_entry_id(
        provider_id="text.openai", model_revision="gpt-5.2-2026-05-01", deployment=None
    )
    deployed = derive_model_catalogue_entry_id(
        provider_id="text.openai", model_revision="gpt-5.2-2026-05-01", deployment="azure-sea"
    )
    assert bare == "text.openai:gpt-5.2-2026-05-01"
    assert deployed == "text.openai:gpt-5.2-2026-05-01:azure-sea"


def test_upsert_rejects_an_entry_id_that_contradicts_the_identity(
    _local_unpinned_settings: None,
) -> None:
    entry = build_seed_model_catalogue_entries()[0]
    tampered = entry.model_copy(update={"entry_id": "text.local:some-other-revision"})
    with pytest.raises(ValueError, match="must equal the identity derived"):
        upsert_model_catalogue_entry(tampered)
    assert get_model_catalogue_repository().list_entries() == []


def test_seed_skips_settings_identity_outside_live_text_modes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "provider_mode", "stub")
    monkeypatch.setattr(settings, "live_text_provider_id", "text.local")
    monkeypatch.setattr(settings, "live_text_model_id", "qwen3:8b")
    monkeypatch.setattr(settings, "workflow_run_model_risk_inventory_json", "[]")
    assert build_seed_model_catalogue_entries() == []


def test_seed_marks_a_versionless_settings_model_as_unpinned(
    _local_unpinned_settings: None,
) -> None:
    entries = build_seed_model_catalogue_entries()
    assert len(entries) == 1
    entry = entries[0]
    assert entry.entry_id == "text.local:qwen3:8b"
    assert entry.model_family == "qwen3:8b"
    assert entry.model_revision == "qwen3:8b"
    assert entry.revision_pinned is False
    assert entry.lifecycle_state is ModelLifecycleState.CATALOGUED
    assert entry.seed_source is ModelCatalogueSeedSource.SETTINGS_LIVE_TEXT
    assert entry.approval_evidence_refs == []


def test_seed_pins_an_explicitly_versioned_settings_model(
    monkeypatch: pytest.MonkeyPatch, _local_unpinned_settings: None
) -> None:
    monkeypatch.setattr(settings, "live_text_model_version", "qwen3:8b-q4-2026-03")
    entry = build_seed_model_catalogue_entries()[0]
    assert entry.model_revision == "qwen3:8b-q4-2026-03"
    assert entry.model_family == "qwen3:8b"
    assert entry.revision_pinned is True


def test_seed_maps_approved_inventory_rows_with_their_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "provider_mode", "disabled")
    monkeypatch.setattr(settings, "workflow_run_model_risk_inventory_json", APPROVED_INVENTORY_JSON)
    entries = build_seed_model_catalogue_entries()
    assert len(entries) == 1
    entry = entries[0]
    assert entry.lifecycle_state is ModelLifecycleState.APPROVED
    assert entry.revision_pinned is True
    assert entry.model_family == "gpt-5.2"
    assert entry.model_revision == "gpt-5.2-2026-05-01"
    assert entry.approved_workflow_pack_ids == ["advisor_brief.pack"]
    assert entry.approval_evidence_refs == ["mrm-approval-2026-014"]
    assert entry.approved_from_utc == "2026-05-01T00:00:00Z"
    assert entry.approved_until_utc == "2027-05-01T00:00:00Z"
    assert entry.seed_source is ModelCatalogueSeedSource.APPROVED_WORKFLOW_RUN_MODEL_INVENTORY


def test_approved_inventory_supersedes_the_settings_row_for_the_same_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "provider_mode", "openai")
    monkeypatch.setattr(settings, "live_text_provider_id", "text.openai")
    monkeypatch.setattr(settings, "live_text_model_id", "gpt-5.2")
    monkeypatch.setattr(settings, "live_text_model_version", "gpt-5.2-2026-05-01")
    monkeypatch.setattr(settings, "workflow_run_model_risk_inventory_json", APPROVED_INVENTORY_JSON)
    entries = build_seed_model_catalogue_entries()
    assert len(entries) == 1
    assert entries[0].lifecycle_state is ModelLifecycleState.APPROVED
    assert entries[0].seed_source is ModelCatalogueSeedSource.APPROVED_WORKFLOW_RUN_MODEL_INVENTORY


def test_reseeding_is_idempotent_and_preserves_created_at(
    monkeypatch: pytest.MonkeyPatch, _local_unpinned_settings: None
) -> None:
    first_report = ensure_model_catalogue_seeded()
    assert (first_report.created_count, first_report.updated_count) == (1, 0)
    first_created_at = get_model_catalogue_repository().list_entries()[0].created_at

    second_report = ensure_model_catalogue_seeded()
    assert (second_report.created_count, second_report.updated_count) == (0, 0)
    assert second_report.unchanged_count == 1

    # Same derived identity (text.local:qwen3:8b), different seeded content:
    # the revision is now explicit and the family differs, so this must be an
    # in-place update that keeps the original created_at.
    monkeypatch.setattr(settings, "live_text_model_version", "qwen3:8b")
    monkeypatch.setattr(settings, "live_text_model_id", "qwen3")
    third_report = ensure_model_catalogue_seeded()
    assert (third_report.created_count, third_report.updated_count) == (0, 1)
    updated_entry = get_model_catalogue_repository().get_entry("text.local:qwen3:8b")
    assert updated_entry is not None
    assert updated_entry.model_family == "qwen3"
    assert updated_entry.revision_pinned is True
    assert updated_entry.created_at == first_created_at


def test_store_accessor_defaults_to_memory_and_reset_clears_state(
    _local_unpinned_settings: None,
) -> None:
    repository = get_model_catalogue_repository()
    assert repository is get_model_catalogue_repository()
    ensure_model_catalogue_seeded()
    assert len(repository.list_entries()) == 1
    reset_model_catalogue_store_cache()
    assert get_model_catalogue_repository().list_entries() == []


def test_store_accessor_fails_closed_on_bad_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "model_catalogue_store_mode", "sqlalchemy")
    monkeypatch.setattr(settings, "database_url", None)
    with pytest.raises(RuntimeError, match="LOTUS_AI_DATABASE_URL is required"):
        get_model_catalogue_repository()
    monkeypatch.setattr(settings, "model_catalogue_store_mode", "carrier-pigeon")
    with pytest.raises(RuntimeError, match="Unsupported LOTUS_AI_MODEL_CATALOGUE_STORE_MODE"):
        get_model_catalogue_repository()


def test_response_builder_reports_counts_store_mode_and_unpinned_exposure(
    _local_unpinned_settings: None,
) -> None:
    response = build_model_catalogue_response()
    assert response.service == settings.service_name
    assert response.version == settings.service_version
    assert response.store_mode == "memory"
    assert response.entry_count == 1
    assert response.unpinned_revision_count == 1
    assert response.entries[0].entry_id == "text.local:qwen3:8b"


def test_sqlalchemy_repository_prepares_each_sqlite_location_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # In-memory sqlite needs no directory preparation.
    SqlAlchemyModelCatalogueRepository("sqlite:///:memory:").close()
    # A relative sqlite path gets its parent directory created under cwd.
    monkeypatch.chdir(tmp_path)
    SqlAlchemyModelCatalogueRepository("sqlite:///data/nested/catalogue.db").close()
    assert (tmp_path / "data" / "nested").is_dir()
    # Non-sqlite URLs are left untouched: no directory side effects at all.
    SqlAlchemyModelCatalogueRepository("postgresql+psycopg://user:secret@localhost:5432/db").close()
    assert list(tmp_path.iterdir()) == [tmp_path / "data"]
