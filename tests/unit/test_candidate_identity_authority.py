"""Canonical candidate identity is authoritative at write, seed, bind and
accounting boundaries (issue #326).

The legacy row key omits the model family and is delimiter-ambiguous, so two
DISTINCT canonical candidates can share it. These are the audit
counterexamples, kept as permanent regressions: no overwrite, no governance
inheritance, no identity-mismatched binding, and no debit collision.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import app.services.model_catalogue as catalogue_service
import app.services.provider_budget_policy as budget_policy
from app.contracts.model_catalogue import (
    ModelCatalogueEntry,
    ModelCatalogueSeedSource,
    ModelLifecycleState,
    derive_model_catalogue_entry_id,
)
from app.providers.base import ProviderExecutionError
from app.repositories.memory_model_catalogue_repository import (
    InMemoryModelCatalogueRepository,
)
from app.repositories.memory_provider_operations_repository import (
    InMemoryProviderOperationsRepository,
)
from app.services.model_catalogue import (
    CandidateIdentityConflictError,
    bind_live_text_model_catalogue_entry,
    ensure_model_catalogue_seeded,
    upsert_model_catalogue_entry,
)
from app.services.provider_budget_policy import (
    reserve_attempt_spend,
    settle_attempt_spend,
    spent_for_execution,
)
from app.services.provider_usage_accounting import AttemptDebit

_NOW = "2026-09-05T00:00:00Z"


def _entry(
    family: str,
    state: ModelLifecycleState,
    *,
    provider_id: str = "text.shared",
    model_revision: str = "rev-1",
    deployment: str | None = None,
) -> ModelCatalogueEntry:
    return ModelCatalogueEntry(
        entry_id=derive_model_catalogue_entry_id(
            provider_id=provider_id,
            model_revision=model_revision,
            deployment=deployment,
        ),
        provider_id=provider_id,
        provider_mode="openai",
        model_family=family,
        model_revision=model_revision,
        deployment=deployment,
        lifecycle_state=state,
        revision_pinned=True,
        seed_source=ModelCatalogueSeedSource.SETTINGS_LIVE_TEXT,
        created_at=_NOW,
        last_updated_at=_NOW,
    )


@pytest.fixture()
def catalogue_repo(monkeypatch: pytest.MonkeyPatch) -> InMemoryModelCatalogueRepository:
    repository = InMemoryModelCatalogueRepository()
    monkeypatch.setattr(catalogue_service, "get_model_catalogue_repository", lambda: repository)
    return repository


def test_upsert_refuses_replacing_a_different_canonical_candidate(
    catalogue_repo: InMemoryModelCatalogueRepository,
) -> None:
    family_a = _entry("family-a", ModelLifecycleState.APPROVED)
    family_b = _entry("family-b", ModelLifecycleState.CATALOGUED)
    assert family_a.entry_id == family_b.entry_id
    assert family_a.candidate_id_v2 != family_b.candidate_id_v2
    upsert_model_catalogue_entry(family_a)

    with pytest.raises(CandidateIdentityConflictError, match="row identity is immutable"):
        upsert_model_catalogue_entry(family_b)

    stored = catalogue_repo.get_entry(family_a.entry_id)
    assert stored is not None
    assert stored.model_family == "family-a"
    assert stored.lifecycle_state is ModelLifecycleState.APPROVED


def test_reseed_never_transfers_governance_posture_across_identities(
    catalogue_repo: InMemoryModelCatalogueRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    family_a = _entry("family-a", ModelLifecycleState.APPROVED)
    family_a.supports_tool_calling = True
    family_a.candidate_id_v2 = ""
    family_a = ModelCatalogueEntry.model_validate(family_a.model_dump())
    upsert_model_catalogue_entry(family_a)

    family_b = _entry("family-b", ModelLifecycleState.CATALOGUED)
    monkeypatch.setattr(catalogue_service, "build_seed_model_catalogue_entries", lambda: [family_b])

    report = ensure_model_catalogue_seeded()

    assert report.identity_conflict_count == 1
    assert report.created_count == report.updated_count == 0
    stored = catalogue_repo.get_entry(family_a.entry_id)
    assert stored is not None
    assert stored.model_family == "family-a"
    assert stored.lifecycle_state is ModelLifecycleState.APPROVED
    assert stored.supports_tool_calling is True
    assert catalogue_repo.get_entry_by_candidate_id(family_a.candidate_id_v2) is not None
    assert catalogue_repo.get_entry_by_candidate_id(family_b.candidate_id_v2) is None


def test_reseed_refuses_delimiter_collision_identities(
    catalogue_repo: InMemoryModelCatalogueRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bare = _entry("qwen", ModelLifecycleState.APPROVED, model_revision="qwen3:8b")
    deployed = _entry(
        "qwen", ModelLifecycleState.CATALOGUED, model_revision="qwen3", deployment="8b"
    )
    assert bare.entry_id == deployed.entry_id
    assert bare.candidate_id_v2 != deployed.candidate_id_v2
    upsert_model_catalogue_entry(bare)
    monkeypatch.setattr(catalogue_service, "build_seed_model_catalogue_entries", lambda: [deployed])

    report = ensure_model_catalogue_seeded()

    assert report.identity_conflict_count == 1
    stored = catalogue_repo.get_entry(bare.entry_id)
    assert stored is not None
    assert stored.model_revision == "qwen3:8b"
    assert stored.lifecycle_state is ModelLifecycleState.APPROVED


def test_binding_refuses_an_identity_mismatched_row(
    catalogue_repo: InMemoryModelCatalogueRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A legacy/SQL row can hold a drifted tuple under the requested key; the
    # bind authority compares the structured tuple, never just the key.
    drifted = _entry("family-a", ModelLifecycleState.APPROVED, model_revision="qwen3:8b")
    catalogue_repo.upsert_entry(drifted)
    from types import SimpleNamespace

    monkeypatch.setattr(catalogue_service, "ensure_model_catalogue_seeded", lambda: None)
    monkeypatch.setattr(
        catalogue_service,
        "resolve_provider_execution_config",
        lambda: SimpleNamespace(
            provider_id="text.shared",
            model_id="qwen3",
            model_version="qwen3",
            deployment="8b",
        ),
    )
    monkeypatch.setattr(
        catalogue_service,
        "derive_model_catalogue_entry_id",
        lambda **_: drifted.entry_id,
    )

    with pytest.raises(ProviderExecutionError, match="identity-mismatched binding"):
        bind_live_text_model_catalogue_entry()


@pytest.fixture()
def operations_repo(monkeypatch: pytest.MonkeyPatch) -> InMemoryProviderOperationsRepository:
    repository = InMemoryProviderOperationsRepository()
    monkeypatch.setattr(budget_policy, "get_provider_operations_store", lambda: repository)
    from types import SimpleNamespace

    monkeypatch.setattr(
        budget_policy,
        "resolve_provider_execution_config",
        lambda: SimpleNamespace(
            enforcement=SimpleNamespace(hard_budget_usd=10.0, budget_enforced=True)
        ),
    )
    return repository


def _debit(amount: float) -> AttemptDebit:
    return AttemptDebit(
        amount_usd=amount,
        basis="ACTUAL_USAGE",
        input_tokens=1,
        output_tokens=1,
        rate_card_ref="identity-authority-test",
    )


def test_distinct_candidates_sharing_the_legacy_key_debit_separately(
    operations_repo: InMemoryProviderOperationsRepository,
) -> None:
    family_a = _entry("family-a", ModelLifecycleState.APPROVED)
    family_b = _entry("family-b", ModelLifecycleState.APPROVED)

    def reserve(entry: ModelCatalogueEntry) -> str:
        return reserve_attempt_spend(
            execution_id="exec-identity",
            candidate_entry_id=entry.entry_id,
            provider_id=entry.provider_id,
            model_revision=entry.model_revision,
            attempt_index=0,
            reservation=_debit(0.7),
            candidate_id_v2=entry.candidate_id_v2,
        )

    assert reserve(family_a) == "RESERVED"
    assert reserve(family_b) == "RESERVED"
    assert settle_attempt_spend(
        execution_id="exec-identity",
        candidate_entry_id=family_a.entry_id,
        attempt_index=0,
        debit=_debit(0.7),
        candidate_id_v2=family_a.candidate_id_v2,
        billable_risk=True,
    )
    assert settle_attempt_spend(
        execution_id="exec-identity",
        candidate_entry_id=family_b.entry_id,
        attempt_index=0,
        debit=_debit(0.5),
        candidate_id_v2=family_b.candidate_id_v2,
        billable_risk=True,
    )

    rows = operations_repo.list_attempt_debits()
    assert len(rows) == 2
    assert {row.candidate_id_v2 for row in rows} == {
        family_a.candidate_id_v2,
        family_b.candidate_id_v2,
    }
    budget_state = operations_repo.get_budget_state(budget_key=budget_policy._BUDGET_KEY)
    assert budget_state is not None
    assert budget_state.current_spend_usd == pytest.approx(1.2)
    assert spent_for_execution("exec-identity") == pytest.approx(1.2)


def test_same_candidate_replay_stays_a_replay(
    operations_repo: InMemoryProviderOperationsRepository,
) -> None:
    family_a = _entry("family-a", ModelLifecycleState.APPROVED)

    def reserve() -> str:
        return reserve_attempt_spend(
            execution_id="exec-replay",
            candidate_entry_id=family_a.entry_id,
            provider_id=family_a.provider_id,
            model_revision=family_a.model_revision,
            attempt_index=0,
            reservation=_debit(0.7),
            candidate_id_v2=family_a.candidate_id_v2,
        )

    assert reserve() == "RESERVED"
    assert reserve() == "DUPLICATE"
    assert len(operations_repo.list_attempt_debits()) == 1


def test_execution_spend_sums_canonical_and_legacy_debit_generations(
    operations_repo: InMemoryProviderOperationsRepository,
) -> None:
    family_a = _entry("family-a", ModelLifecycleState.APPROVED)
    assert (
        reserve_attempt_spend(
            execution_id="exec-mixed",
            candidate_entry_id=family_a.entry_id,
            provider_id=family_a.provider_id,
            model_revision=family_a.model_revision,
            attempt_index=0,
            reservation=_debit(0.4),
            candidate_id_v2=family_a.candidate_id_v2,
        )
        == "RESERVED"
    )
    # A provider-keyed debit (no candidate named) keeps the legacy identity.
    assert (
        reserve_attempt_spend(
            execution_id="exec-mixed",
            candidate_entry_id="text.shared",
            provider_id="text.shared",
            model_revision=None,
            attempt_index=1,
            reservation=_debit(0.3),
            candidate_id_v2=None,
        )
        == "RESERVED"
    )

    rows = {row.debit_id for row in operations_repo.list_attempt_debits()}
    assert any(debit_id.startswith("adbt2:exec-mixed:cand2_") for debit_id in rows)
    assert any(debit_id.startswith("adbt:exec-mixed:text.shared:") for debit_id in rows)
    assert spent_for_execution("exec-mixed") == pytest.approx(0.7)


def test_sql_upsert_refuses_replacing_a_different_canonical_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.repositories.sqlalchemy_model_catalogue_repository import (
        SqlAlchemyModelCatalogueRepository,
    )
    from tests.support.migration_runner import upgrade_database_to_head

    database_url = f"sqlite:///{Path(tmp_path) / 'identity-authority.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyModelCatalogueRepository(database_url)
    monkeypatch.setattr(catalogue_service, "get_model_catalogue_repository", lambda: repository)
    family_a = _entry("family-a", ModelLifecycleState.APPROVED)
    family_b = _entry("family-b", ModelLifecycleState.CATALOGUED)
    upsert_model_catalogue_entry(family_a)

    with pytest.raises(CandidateIdentityConflictError):
        upsert_model_catalogue_entry(family_b)

    stored = repository.get_entry(family_a.entry_id)
    assert stored is not None
    assert stored.model_family == "family-a"
    assert stored.lifecycle_state is ModelLifecycleState.APPROVED
    assert repository.get_entry_by_candidate_id(family_b.candidate_id_v2) is None


def test_sql_debit_lifecycle_keys_on_the_canonical_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace

    from app.repositories.sqlalchemy_provider_operations_repository import (
        SqlAlchemyProviderOperationsRepository,
    )
    from tests.support.migration_runner import upgrade_database_to_head

    database_url = f"sqlite:///{Path(tmp_path) / 'identity-debits.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyProviderOperationsRepository(database_url)
    monkeypatch.setattr(budget_policy, "get_provider_operations_store", lambda: repository)
    monkeypatch.setattr(
        budget_policy,
        "resolve_provider_execution_config",
        lambda: SimpleNamespace(
            enforcement=SimpleNamespace(hard_budget_usd=10.0, budget_enforced=True)
        ),
    )
    family_a = _entry("family-a", ModelLifecycleState.APPROVED)
    family_b = _entry("family-b", ModelLifecycleState.APPROVED)

    for entry in (family_a, family_b):
        assert (
            reserve_attempt_spend(
                execution_id="exec-sql",
                candidate_entry_id=entry.entry_id,
                provider_id=entry.provider_id,
                model_revision=entry.model_revision,
                attempt_index=0,
                reservation=_debit(0.6),
                candidate_id_v2=entry.candidate_id_v2,
            )
            == "RESERVED"
        )
    assert settle_attempt_spend(
        execution_id="exec-sql",
        candidate_entry_id=family_a.entry_id,
        attempt_index=0,
        debit=_debit(0.6),
        candidate_id_v2=family_a.candidate_id_v2,
        billable_risk=True,
    )
    assert settle_attempt_spend(
        execution_id="exec-sql",
        candidate_entry_id=family_b.entry_id,
        attempt_index=0,
        debit=_debit(0.4),
        candidate_id_v2=family_b.candidate_id_v2,
        billable_risk=True,
    )
    # A pre-existing legacy-format row still counts toward the execution.
    assert (
        reserve_attempt_spend(
            execution_id="exec-sql",
            candidate_entry_id="text.shared",
            provider_id="text.shared",
            model_revision=None,
            attempt_index=1,
            reservation=_debit(0.2),
            candidate_id_v2=None,
        )
        == "RESERVED"
    )

    debit_ids = {row.debit_id for row in repository.list_attempt_debits()}
    assert (
        f"adbt2:exec-sql:{family_a.candidate_id_v2}:0" in debit_ids
        and f"adbt2:exec-sql:{family_b.candidate_id_v2}:0" in debit_ids
        and "adbt:exec-sql:text.shared:1" in debit_ids
    )
    assert spent_for_execution("exec-sql") == pytest.approx(1.2)
