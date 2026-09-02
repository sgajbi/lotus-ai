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
    ModelCatalogueSeedReport,
    ModelCatalogueSeedSource,
    ModelLifecycleState,
    ModelLifecycleTransitionRequest,
    derive_model_catalogue_entry_id,
)
from app.contracts.providers import ProviderFailureCategory
from app.providers.base import ProviderExecutionError
from app.services import model_catalogue as model_catalogue_service
from app.services.model_catalogue import (
    bind_live_text_model_catalogue_entry,
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


def test_reseeding_never_reverts_an_operator_lifecycle_transition(
    _local_unpinned_settings: None,
) -> None:
    ensure_model_catalogue_seeded()
    repository = get_model_catalogue_repository()
    seeded = repository.get_entry("text.local:qwen3:8b")
    assert seeded is not None
    repository.upsert_entry(
        seeded.model_copy(update={"lifecycle_state": ModelLifecycleState.RETIRED})
    )

    report = ensure_model_catalogue_seeded()

    assert report.updated_count == 0
    retired = repository.get_entry("text.local:qwen3:8b")
    assert retired is not None
    assert retired.lifecycle_state is ModelLifecycleState.RETIRED


def test_binding_returns_the_seeded_entry_for_the_configured_identity(
    _local_unpinned_settings: None,
) -> None:
    entry = bind_live_text_model_catalogue_entry()
    assert entry.entry_id == "text.local:qwen3:8b"
    assert entry.revision_pinned is False
    assert entry.lifecycle_state is ModelLifecycleState.CATALOGUED


def test_binding_fails_closed_without_a_configured_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "provider_mode", "openai")
    monkeypatch.setattr(settings, "live_text_provider_id", None)
    monkeypatch.setattr(settings, "live_text_model_id", None)
    monkeypatch.setattr(settings, "workflow_run_model_risk_inventory_json", "[]")
    with pytest.raises(ProviderExecutionError) as excinfo:
        bind_live_text_model_catalogue_entry()
    assert excinfo.value.category is ProviderFailureCategory.MODEL_NOT_CATALOGUED


def test_binding_fails_closed_when_the_catalogue_row_is_absent(
    monkeypatch: pytest.MonkeyPatch, _local_unpinned_settings: None
) -> None:
    monkeypatch.setattr(
        model_catalogue_service,
        "ensure_model_catalogue_seeded",
        lambda: ModelCatalogueSeedReport(created_count=0, updated_count=0, unchanged_count=0),
    )
    with pytest.raises(ProviderExecutionError) as excinfo:
        bind_live_text_model_catalogue_entry()
    assert excinfo.value.category is ProviderFailureCategory.MODEL_NOT_CATALOGUED
    assert "text.local:qwen3:8b" in excinfo.value.message


def test_binding_refuses_an_execution_ineligible_lifecycle_state(
    _local_unpinned_settings: None,
) -> None:
    ensure_model_catalogue_seeded()
    repository = get_model_catalogue_repository()
    seeded = repository.get_entry("text.local:qwen3:8b")
    assert seeded is not None
    repository.upsert_entry(
        seeded.model_copy(update={"lifecycle_state": ModelLifecycleState.RETIRED})
    )

    with pytest.raises(ProviderExecutionError) as excinfo:
        bind_live_text_model_catalogue_entry()

    assert excinfo.value.category is ProviderFailureCategory.MODEL_LIFECYCLE_INELIGIBLE
    assert "RETIRED" in excinfo.value.message


def _transition_request(**overrides: object) -> ModelLifecycleTransitionRequest:
    payload: dict[str, object] = {
        "to_state": ModelLifecycleState.EVALUATING,
        "reason": "Begin evaluation for governed promotion.",
    }
    payload.update(overrides)
    return ModelLifecycleTransitionRequest.model_validate(payload)


def _seed_evaluation_run(
    run_id: str,
    *,
    lifecycle_status: str = "COMPLETED",
    verdict: str | None = "PASS",
) -> None:
    from app.repositories.evaluation_runtime_repository import EvaluationRunRecord
    from app.services.evaluation_runtime_store import get_evaluation_runtime_store

    get_evaluation_runtime_store().save_run(
        EvaluationRunRecord(
            run_id=run_id,
            fixture_id="model_promotion_examples",
            manifest_version="foundation.v1",
            lifecycle_status=lifecycle_status,
            triggered_by="operator-a",
            submitted_at="2026-09-03T09:00:00Z",
            async_job_id=None,
            latest_message="Promotion evidence fixture.",
            verdict=verdict,
            case_count=3,
        )
    )


def _promote_entry_for_test(
    entry_id: str, to_state: ModelLifecycleState, evaluation_run_id: str
) -> object:
    """Run the full governed two-step promotion as test setup."""

    from app.contracts.model_catalogue import (
        ModelPromotionApprovalRequest,
        ModelPromotionIntentRequest,
    )
    from app.services.model_catalogue import approve_model_promotion, request_model_promotion
    from tests.support.governed_control import GOVERNED_APPROVER, GOVERNED_REQUESTER

    pending = request_model_promotion(
        entry_id,
        ModelPromotionIntentRequest(
            to_state=to_state,
            reason="Promotion backed by passing evaluation evidence.",
            evaluation_run_id=evaluation_run_id,
        ),
        GOVERNED_REQUESTER,
    )
    return approve_model_promotion(
        entry_id,
        ModelPromotionApprovalRequest(
            action_id=pending.governed_action.action_id,
            action_hash=pending.governed_action.action_hash,
        ),
        GOVERNED_APPROVER,
    )


@pytest.fixture
def _durable_catalogue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _local_unpinned_settings: None
) -> str:
    from tests.support.migration_runner import upgrade_database_to_head

    database_url = f"sqlite:///{tmp_path / 'catalogue-lifecycle.db'}"
    upgrade_database_to_head(database_url)
    monkeypatch.setattr(settings, "model_catalogue_store_mode", "sqlalchemy")
    monkeypatch.setattr(settings, "database_url", database_url)
    ensure_model_catalogue_seeded()
    return "text.local:qwen3:8b"


def test_lifecycle_transition_requires_authorization_and_durable_store(
    monkeypatch: pytest.MonkeyPatch, _local_unpinned_settings: None
) -> None:
    from fastapi import HTTPException

    from app.http.authenticated_caller import AuthenticatedCaller
    from app.services.model_catalogue import apply_model_lifecycle_transition
    from tests.support.governed_control import GOVERNED_REQUESTER

    unauthorized = AuthenticatedCaller(
        caller_app="lotus-manage",
        trust_source="verified_service_jwt",
        credential_key_id="ops-key-alpha",
    )
    with pytest.raises(HTTPException) as excinfo:
        apply_model_lifecycle_transition("text.local:qwen3:8b", _transition_request(), unauthorized)
    assert excinfo.value.status_code == 403

    with pytest.raises(HTTPException) as excinfo:
        apply_model_lifecycle_transition(
            "text.local:qwen3:8b", _transition_request(), GOVERNED_REQUESTER
        )
    assert excinfo.value.status_code == 409
    assert "LOTUS_AI_MODEL_CATALOGUE_STORE_MODE" in str(excinfo.value.detail)


def test_lifecycle_transition_walks_the_governed_edge_table(_durable_catalogue: str) -> None:
    from fastapi import HTTPException

    from app.contracts.model_catalogue import ModelPromotionApprovalResponse
    from app.services.model_catalogue import (
        apply_model_lifecycle_transition,
        build_model_catalogue_entry_detail,
    )
    from tests.support.governed_control import GOVERNED_REQUESTER

    entry_id = _durable_catalogue

    # A serving target is refused on the single-principal route BEFORE edge
    # validation: the risk direction, not the edge table, is the first gate.
    with pytest.raises(HTTPException) as excinfo:
        apply_model_lifecycle_transition(
            entry_id,
            _transition_request(to_state=ModelLifecycleState.PRODUCTION),
            GOVERNED_REQUESTER,
        )
    assert excinfo.value.status_code == 409
    assert "promotion-requests" in str(excinfo.value.detail)

    evaluating = apply_model_lifecycle_transition(
        entry_id, _transition_request(), GOVERNED_REQUESTER
    )
    assert evaluating.transition.requested_by == "lotus-platform (credential ops-key-alpha)"
    # No approval existed, and the record says so honestly.
    assert evaluating.transition.approved_by is None
    assert evaluating.transition.approval_evidence_ref is None

    _seed_evaluation_run("run_promotion_001")
    approved = _promote_entry_for_test(entry_id, ModelLifecycleState.APPROVED, "run_promotion_001")
    assert isinstance(approved, ModelPromotionApprovalResponse)
    assert approved.entry.lifecycle_state is ModelLifecycleState.APPROVED
    assert "evaluation-run:run_promotion_001" in approved.entry.approval_evidence_refs
    assert approved.transition.requested_by == "lotus-platform (credential ops-key-alpha)"
    assert approved.transition.approved_by == "lotus-platform (credential ops-key-beta)"
    assert approved.governed_action.status.value == "EXECUTED"

    production = _promote_entry_for_test(
        entry_id, ModelLifecycleState.PRODUCTION, "run_promotion_001"
    )
    assert isinstance(production, ModelPromotionApprovalResponse)
    assert production.entry.lifecycle_state is ModelLifecycleState.PRODUCTION

    apply_model_lifecycle_transition(
        entry_id, _transition_request(to_state=ModelLifecycleState.DEPRECATED), GOVERNED_REQUESTER
    )
    retired = apply_model_lifecycle_transition(
        entry_id, _transition_request(to_state=ModelLifecycleState.RETIRED), GOVERNED_REQUESTER
    )
    assert retired.entry.lifecycle_state is ModelLifecycleState.RETIRED

    with pytest.raises(HTTPException) as excinfo:
        apply_model_lifecycle_transition(
            entry_id,
            _transition_request(to_state=ModelLifecycleState.CATALOGUED),
            GOVERNED_REQUESTER,
        )
    assert excinfo.value.status_code == 422
    assert "terminal" in str(excinfo.value.detail)

    detail = build_model_catalogue_entry_detail(entry_id)
    assert [event.to_state for event in reversed(detail.lifecycle_events)] == [
        ModelLifecycleState.EVALUATING,
        ModelLifecycleState.APPROVED,
        ModelLifecycleState.PRODUCTION,
        ModelLifecycleState.DEPRECATED,
        ModelLifecycleState.RETIRED,
    ]
    assert all(event.reason for event in detail.lifecycle_events)


def test_promotion_request_validates_target_edge_and_evidence(_durable_catalogue: str) -> None:
    """A pending approval is never parked on a promotion that cannot execute:
    the serving-target shape, the lifecycle edge, and the PASS-verdict eval
    evidence are all vetted before any intent is recorded (issue #245)."""

    from fastapi import HTTPException

    from app.contracts.model_catalogue import ModelPromotionIntentRequest
    from app.services.model_catalogue import (
        apply_model_lifecycle_transition,
        request_model_promotion,
    )
    from tests.support.governed_control import GOVERNED_REQUESTER

    entry_id = _durable_catalogue

    def _intent(
        to_state: ModelLifecycleState, run_id: str = "run_promotion_ok"
    ) -> ModelPromotionIntentRequest:
        return ModelPromotionIntentRequest(
            to_state=to_state,
            reason="Promotion backed by evaluation evidence.",
            evaluation_run_id=run_id,
        )

    # A non-serving target has no business on the promotion flow.
    with pytest.raises(HTTPException) as excinfo:
        request_model_promotion(
            entry_id, _intent(ModelLifecycleState.DEPRECATED), GOVERNED_REQUESTER
        )
    assert excinfo.value.status_code == 422
    assert "not a serving-promotion target" in str(excinfo.value.detail)

    # The lifecycle edge table still applies on the governed flow.
    _seed_evaluation_run("run_promotion_ok")
    with pytest.raises(HTTPException) as excinfo:
        request_model_promotion(
            entry_id, _intent(ModelLifecycleState.PRODUCTION), GOVERNED_REQUESTER
        )
    assert excinfo.value.status_code == 422
    assert "not allowed" in str(excinfo.value.detail)

    apply_model_lifecycle_transition(entry_id, _transition_request(), GOVERNED_REQUESTER)

    # Evidence must exist ...
    with pytest.raises(HTTPException) as excinfo:
        request_model_promotion(
            entry_id, _intent(ModelLifecycleState.APPROVED, "run_missing"), GOVERNED_REQUESTER
        )
    assert excinfo.value.status_code == 422
    assert "does not exist" in str(excinfo.value.detail)

    # ... and must actually have passed: a FAIL verdict or an unfinished run
    # is not promotion evidence.
    _seed_evaluation_run("run_promotion_fail", verdict="FAIL")
    with pytest.raises(HTTPException) as excinfo:
        request_model_promotion(
            entry_id,
            _intent(ModelLifecycleState.APPROVED, "run_promotion_fail"),
            GOVERNED_REQUESTER,
        )
    assert excinfo.value.status_code == 422
    assert "verdict PASS" in str(excinfo.value.detail)

    _seed_evaluation_run("run_promotion_running", lifecycle_status="RUNNING", verdict=None)
    with pytest.raises(HTTPException) as excinfo:
        request_model_promotion(
            entry_id,
            _intent(ModelLifecycleState.APPROVED, "run_promotion_running"),
            GOVERNED_REQUESTER,
        )
    assert excinfo.value.status_code == 422
    assert "RUNNING" in str(excinfo.value.detail)

    # A valid intent records PENDING and changes nothing until approval.
    pending = request_model_promotion(
        entry_id, _intent(ModelLifecycleState.APPROVED), GOVERNED_REQUESTER
    )
    assert pending.governed_action.status.value == "PENDING"
    entry = get_model_catalogue_repository().get_entry(entry_id)
    assert entry is not None
    assert entry.lifecycle_state is ModelLifecycleState.EVALUATING


def test_promotion_approval_refuses_a_stale_baseline(_durable_catalogue: str) -> None:
    """An approval reviewed against one lifecycle baseline must not execute
    against another: the payload pins the entry's state at request time, and
    a transition in between refuses the stale approval (issue #245)."""

    from fastapi import HTTPException

    from app.contracts.model_catalogue import (
        ModelPromotionApprovalRequest,
        ModelPromotionIntentRequest,
    )
    from app.services.model_catalogue import (
        apply_model_lifecycle_transition,
        approve_model_promotion,
        request_model_promotion,
    )
    from tests.support.governed_control import GOVERNED_APPROVER, GOVERNED_REQUESTER

    entry_id = _durable_catalogue
    apply_model_lifecycle_transition(entry_id, _transition_request(), GOVERNED_REQUESTER)
    _seed_evaluation_run("run_promotion_stale")
    pending = request_model_promotion(
        entry_id,
        ModelPromotionIntentRequest(
            to_state=ModelLifecycleState.APPROVED,
            reason="Promotion backed by evaluation evidence.",
            evaluation_run_id="run_promotion_stale",
        ),
        GOVERNED_REQUESTER,
    )

    # The entry moves off the reviewed baseline before the approval lands.
    apply_model_lifecycle_transition(
        entry_id,
        _transition_request(
            to_state=ModelLifecycleState.CATALOGUED,
            reason="Evaluation paused; return to catalogued.",
        ),
        GOVERNED_REQUESTER,
    )

    with pytest.raises(HTTPException) as excinfo:
        approve_model_promotion(
            entry_id,
            ModelPromotionApprovalRequest(
                action_id=pending.governed_action.action_id,
                action_hash=pending.governed_action.action_hash,
            ),
            GOVERNED_APPROVER,
        )
    assert excinfo.value.status_code == 409
    assert "submit a new request" in str(excinfo.value.detail)

    entry = get_model_catalogue_repository().get_entry(entry_id)
    assert entry is not None
    assert entry.lifecycle_state is ModelLifecycleState.CATALOGUED


def test_promotion_approval_requires_a_distinct_credential(_durable_catalogue: str) -> None:
    from fastapi import HTTPException

    from app.contracts.model_catalogue import (
        ModelPromotionApprovalRequest,
        ModelPromotionIntentRequest,
    )
    from app.services.model_catalogue import (
        apply_model_lifecycle_transition,
        approve_model_promotion,
        request_model_promotion,
    )
    from tests.support.governed_control import GOVERNED_REQUESTER

    entry_id = _durable_catalogue
    apply_model_lifecycle_transition(entry_id, _transition_request(), GOVERNED_REQUESTER)
    _seed_evaluation_run("run_promotion_distinct")
    pending = request_model_promotion(
        entry_id,
        ModelPromotionIntentRequest(
            to_state=ModelLifecycleState.APPROVED,
            reason="Promotion backed by evaluation evidence.",
            evaluation_run_id="run_promotion_distinct",
        ),
        GOVERNED_REQUESTER,
    )

    with pytest.raises(HTTPException) as excinfo:
        approve_model_promotion(
            entry_id,
            ModelPromotionApprovalRequest(
                action_id=pending.governed_action.action_id,
                action_hash=pending.governed_action.action_hash,
            ),
            GOVERNED_REQUESTER,
        )
    assert excinfo.value.status_code == 403
    assert "distinct" in str(excinfo.value.detail)


def test_seed_authority_change_never_resurrects_an_operator_terminal_state(
    monkeypatch: pytest.MonkeyPatch, _local_unpinned_settings: None
) -> None:
    ensure_model_catalogue_seeded()
    repository = get_model_catalogue_repository()
    seeded = repository.get_entry("text.local:qwen3:8b")
    assert seeded is not None
    repository.upsert_entry(
        seeded.model_copy(update={"lifecycle_state": ModelLifecycleState.RETIRED})
    )

    # The inventory now claims the same identity: a seeding-authority change
    # that would normally re-assert APPROVED. Retirement must survive it.
    monkeypatch.setattr(
        settings,
        "workflow_run_model_risk_inventory_json",
        json.dumps(
            [
                {
                    "provider_id": "text.local",
                    "provider_mode": "local_openai_compatible",
                    "model_id": "qwen3:8b",
                    "model_version": "qwen3:8b",
                    "workflow_pack_ids": ["advisor_brief.pack"],
                    "approval_ref": "mrm-approval-2026-030",
                    "approved_from_utc": "2026-08-01T00:00:00Z",
                    "approved_until_utc": None,
                }
            ]
        ),
    )
    monkeypatch.setattr(settings, "live_text_model_version", "qwen3:8b")

    ensure_model_catalogue_seeded()

    resurrected = repository.get_entry("text.local:qwen3:8b")
    assert resurrected is not None
    assert resurrected.lifecycle_state is ModelLifecycleState.RETIRED
    assert resurrected.seed_source is ModelCatalogueSeedSource.APPROVED_WORKFLOW_RUN_MODEL_INVENTORY


def test_drift_recording_distinguishes_agreement_reveal_and_repetition(
    _local_unpinned_settings: None,
) -> None:
    from app.services.model_catalogue import record_model_revision_drift

    ensure_model_catalogue_seeded()
    repository = get_model_catalogue_repository()
    entry = repository.get_entry("text.local:qwen3:8b")
    assert entry is not None

    # Agreement with the family/revision identity is not drift.
    record_model_revision_drift(entry=entry, observed_model_id="qwen3:8b")
    record_model_revision_drift(entry=entry, observed_model_id=None)
    assert repository.list_drift_observations(entry.entry_id) == []

    # An unpinned entry whose provider reveals a concrete revision IS an
    # observation - the exact exposure revision_pinned=False warns about.
    record_model_revision_drift(entry=entry, observed_model_id="qwen3:8b-q4-2026-03")
    observations = repository.list_drift_observations(entry.entry_id)
    assert len(observations) == 1
    first = observations[0]
    assert first.observed_model_id == "qwen3:8b-q4-2026-03"
    assert first.expected_identity == "qwen3:8b"
    assert first.revision_pinned_at_observation is False
    assert first.observation_count == 1

    # Repetition deduplicates: same observation, count and last_observed move.
    record_model_revision_drift(entry=entry, observed_model_id="qwen3:8b-q4-2026-03")
    repeated = repository.list_drift_observations(entry.entry_id)[0]
    assert repeated.observation_count == 2
    assert repeated.first_observed_at == first.first_observed_at
    assert repeated.last_observed_at >= first.last_observed_at

    # A different observed identity is its own observation.
    record_model_revision_drift(entry=entry, observed_model_id="qwen3:8b-q5-2026-06")
    assert len(repository.list_drift_observations(entry.entry_id)) == 2


def test_memory_lifecycle_events_append_and_list() -> None:
    from app.contracts.model_catalogue import ModelLifecycleTransitionRecord

    repository = get_model_catalogue_repository()
    for index, instant in enumerate(["2026-08-30T01:00:00Z", "2026-08-30T02:00:00Z"]):
        repository.append_lifecycle_event(
            ModelLifecycleTransitionRecord(
                event_id=f"mlc_mem_{index}",
                entry_id="text.local:qwen3:8b",
                from_state=ModelLifecycleState.CATALOGUED,
                to_state=ModelLifecycleState.EVALUATING,
                reason="memory round trip",
                requested_by="ops.primary@lotus",
                approved_by="ops.secondary@lotus",
                recorded_at=instant,
            )
        )
    events = repository.list_lifecycle_events("text.local:qwen3:8b")
    assert [event.event_id for event in events] == ["mlc_mem_1", "mlc_mem_0"]
    assert repository.list_lifecycle_events("other:entry") == []


def test_lifecycle_transition_on_an_unknown_entry_is_404(_durable_catalogue: str) -> None:
    from fastapi import HTTPException

    from app.services.model_catalogue import apply_model_lifecycle_transition

    from tests.support.governed_control import GOVERNED_REQUESTER

    with pytest.raises(HTTPException) as excinfo:
        apply_model_lifecycle_transition(
            "text.unknown:nope", _transition_request(), GOVERNED_REQUESTER
        )
    assert excinfo.value.status_code == 404


def test_drift_observations_survive_a_store_restart_in_sqlalchemy_mode(
    _durable_catalogue: str,
) -> None:
    from app.services.model_catalogue import record_model_revision_drift

    repository = get_model_catalogue_repository()
    entry = repository.get_entry(_durable_catalogue)
    assert entry is not None
    record_model_revision_drift(entry=entry, observed_model_id="qwen3:8b-q4-2026-03")
    record_model_revision_drift(entry=entry, observed_model_id="qwen3:8b-q4-2026-03")
    record_model_revision_drift(entry=entry, observed_model_id="qwen3:8b-q5-2026-06")

    # Restart: drop every in-process handle; observations must come back from SQL.
    reset_model_catalogue_store_cache()
    observations = get_model_catalogue_repository().list_drift_observations(_durable_catalogue)
    by_observed = {o.observed_model_id: o for o in observations}
    assert set(by_observed) == {"qwen3:8b-q4-2026-03", "qwen3:8b-q5-2026-06"}
    assert by_observed["qwen3:8b-q4-2026-03"].observation_count == 2
    assert by_observed["qwen3:8b-q5-2026-06"].observation_count == 1


def test_capability_facts_are_seeded_only_from_approval_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Issue #244 S2: a pack-approved model has provably produced output the
    deterministic validator held to the pack's strict-JSON schema contract,
    so structured-output support is a fact. Configuration alone proves
    nothing, and no other dimension has in-repo evidence - unknown stays
    unknown rather than becoming an optimistic default."""

    monkeypatch.setattr(settings, "provider_mode", "openai")
    monkeypatch.setattr(settings, "provider_rollout_state", "CANARY_ENABLED")
    monkeypatch.setattr(settings, "live_text_provider_id", "text.openai")
    monkeypatch.setattr(settings, "live_text_model_id", "gpt-5.4")
    monkeypatch.setattr(settings, "live_text_provider_api_key", "secret")
    monkeypatch.setattr(settings, "workflow_run_model_risk_inventory_json", APPROVED_INVENTORY_JSON)

    entries = {entry.model_family: entry for entry in build_seed_model_catalogue_entries()}

    approved = entries["gpt-5.2"]
    assert approved.supports_structured_output is True
    assert approved.supports_tool_calling is None
    assert approved.supports_streaming is None
    assert approved.context_window_tokens is None

    configured = entries["gpt-5.4"]
    assert configured.supports_structured_output is None
    assert configured.supports_tool_calling is None


def test_reseeding_never_unassesses_a_known_capability_fact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Null means not assessed. The seed may add facts it can prove; it must
    never subtract ones it cannot - otherwise every startup reconcile would
    quietly erase operator assessments back to unknown."""

    monkeypatch.setattr(settings, "provider_mode", "openai")
    monkeypatch.setattr(settings, "provider_rollout_state", "CANARY_ENABLED")
    monkeypatch.setattr(settings, "live_text_provider_id", "text.openai")
    monkeypatch.setattr(settings, "live_text_model_id", "gpt-5.4")
    monkeypatch.setattr(settings, "live_text_provider_api_key", "secret")
    monkeypatch.setattr(settings, "workflow_run_model_risk_inventory_json", "[]")

    first = ensure_model_catalogue_seeded()
    assert first.created_count == 1
    repository = get_model_catalogue_repository()
    [entry] = repository.list_entries()
    assert entry.supports_tool_calling is None

    # An operator assessment lands on the row the seed knows nothing about.
    upsert_model_catalogue_entry(
        entry.model_copy(
            update={
                "supports_tool_calling": False,
                "supports_structured_output": True,
                "context_window_tokens": 128_000,
            }
        )
    )

    report = ensure_model_catalogue_seeded()
    [reconciled] = repository.list_entries()
    assert reconciled.supports_tool_calling is False
    assert reconciled.supports_structured_output is True
    assert reconciled.context_window_tokens == 128_000
    assert report.updated_count == 0
