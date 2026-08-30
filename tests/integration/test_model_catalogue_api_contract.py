"""API contract and SQL restart proof for the governed model catalogue (issue #175, slice 1)."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services.model_catalogue_store import reset_model_catalogue_store_cache
from tests.support.migration_runner import upgrade_database_to_head
from tests.support.runtime_settings import override_runtime_settings

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


def test_model_catalogue_returns_seeded_identities_with_pinning_posture(
    client: TestClient,
) -> None:
    with override_runtime_settings(
        provider_mode="local_openai_compatible",
        live_text_provider_id="text.local",
        live_text_model_id="qwen3:8b",
        live_text_model_version=None,
        workflow_run_model_risk_inventory_json=APPROVED_INVENTORY_JSON,
    ):
        response = client.get("/platform/models/catalogue")

        assert response.status_code == 200
        body = response.json()
        assert body["service"] == "lotus-ai"
        assert body["store_mode"] == "memory"
        assert body["entry_count"] == 2
        assert body["unpinned_revision_count"] == 1

        by_id = {entry["entry_id"]: entry for entry in body["entries"]}
        settings_entry = by_id["text.local:qwen3:8b"]
        assert settings_entry["lifecycle_state"] == "CATALOGUED"
        assert settings_entry["revision_pinned"] is False
        assert settings_entry["seed_source"] == "settings_live_text"
        assert settings_entry["approval_evidence_refs"] == []

        approved_entry = by_id["text.openai:gpt-5.2-2026-05-01"]
        assert approved_entry["lifecycle_state"] == "APPROVED"
        assert approved_entry["revision_pinned"] is True
        assert approved_entry["model_family"] == "gpt-5.2"
        assert approved_entry["approved_workflow_pack_ids"] == ["advisor_brief.pack"]
        assert approved_entry["approval_evidence_refs"] == ["mrm-approval-2026-014"]
        assert approved_entry["seed_source"] == "approved_workflow_run_model_inventory"


def test_model_catalogue_reads_are_stable_across_repeated_requests(
    client: TestClient,
) -> None:
    with override_runtime_settings(
        provider_mode="openai",
        live_text_provider_id="text.openai",
        live_text_model_id="gpt-5.2",
        live_text_model_version="gpt-5.2-2026-05-01",
        workflow_run_model_risk_inventory_json="[]",
    ):
        first = client.get("/platform/models/catalogue")
        second = client.get("/platform/models/catalogue")

        assert first.status_code == second.status_code == 200
        assert first.json() == second.json()


def test_model_catalogue_survives_a_store_restart_in_sqlalchemy_mode(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'model-catalogue-restart.db'}"
    upgrade_database_to_head(database_url)

    with override_runtime_settings(
        model_catalogue_store_mode="sqlalchemy",
        database_url=database_url,
        provider_mode="openai",
        live_text_provider_id="text.openai",
        live_text_model_id="gpt-5.2",
        live_text_model_version="gpt-5.2-2026-05-01",
        workflow_run_model_risk_inventory_json=APPROVED_INVENTORY_JSON,
    ):
        with TestClient(app) as first_process:
            first_body = first_process.get("/platform/models/catalogue").json()
        assert first_body["store_mode"] == "sqlalchemy"
        assert first_body["entry_count"] == 1

        # Restart: drop every in-process handle; truth must come back from SQL.
        reset_model_catalogue_store_cache()

        with TestClient(app) as second_process:
            second_body = second_process.get("/platform/models/catalogue").json()

        assert second_body == first_body
        assert second_body["entries"][0]["created_at"] == first_body["entries"][0]["created_at"], (
            "a restart must re-read the catalogued row, not re-create it"
        )
