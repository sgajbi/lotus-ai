"""Canonical serving-candidate identity v2 (issue #314).

The v1 delimiter-concatenated entry id has an ACTUAL collision - two distinct
serving tuples render 'text.local:qwen3:8b' - so identity v2 is a versioned
opaque deterministic digest of the canonical serialization of the structured
serving tuple. These are the steering's adversarial goldens, the executable
collision audit over current configuration, and the persistence invariant
that survives an id-derivation regression.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.contracts.model_catalogue import (
    CANDIDATE_IDENTITY_V2_PREFIX,
    ModelCatalogueEntry,
    ModelCatalogueSeedSource,
    ModelLifecycleState,
    derive_candidate_identity_v2,
    derive_model_catalogue_entry_id,
)


def _v2(provider: str, family: str, revision: str, deployment: str | None) -> str:
    return derive_candidate_identity_v2(
        provider_id=provider,
        model_family=family,
        model_revision=revision,
        deployment=deployment,
    )


def test_the_recorded_v1_collision_is_impossible_under_v2() -> None:
    """The collision audit's finding, pinned forever: the default local
    configuration's v1 identity is delimiter-ambiguous, and v2 separates the
    two tuples that collide onto it."""

    v1_a = derive_model_catalogue_entry_id(
        provider_id="text.local", model_revision="qwen3:8b", deployment=None
    )
    v1_b = derive_model_catalogue_entry_id(
        provider_id="text.local", model_revision="qwen3", deployment="8b"
    )
    assert v1_a == v1_b == "text.local:qwen3:8b"  # the v1 defect, stated

    assert _v2("text.local", "qwen3:8b", "qwen3:8b", None) != _v2(
        "text.local", "qwen3", "qwen3", "8b"
    )


def test_adversarial_goldens_for_v2_distinctness() -> None:
    # Same provider, different model family, same revision: v1 cannot even
    # express the difference (family is not in v1 identity); v2 must.
    assert _v2("text.openai", "family-a", "rev-1", None) != _v2(
        "text.openai", "family-b", "rev-1", None
    )
    # Same provider/family/revision, different deployment.
    assert _v2("text.openai", "fam", "rev-1", "eu-1") != _v2("text.openai", "fam", "rev-1", "eu-2")
    # Null deployment is distinct from every string, including "".
    assert _v2("text.openai", "fam", "rev-1", None) != _v2("text.openai", "fam", "rev-1", "")
    # Components stuffed with delimiter-like characters cannot cross-collide.
    assert _v2("p", "f", "a:b", None) != _v2("p", "f", "a", "b")
    assert _v2("p:x", "f", "r", None) != _v2("p", "f", "x:r", None)
    assert _v2("p", "f:g", "r", None) != _v2("p", "f", "g:r", None)


def test_v2_is_deterministic_versioned_and_divergent_on_any_change() -> None:
    first = _v2("text.openai", "gpt-5.4", "gpt-5.4-2026-06-01", "eu-frankfurt-1")
    second = _v2("text.openai", "gpt-5.4", "gpt-5.4-2026-06-01", "eu-frankfurt-1")
    assert first == second  # exact replay
    assert first.startswith(CANDIDATE_IDENTITY_V2_PREFIX)  # versioned scheme
    assert len(first) == len(CANDIDATE_IDENTITY_V2_PREFIX) + 64
    # Any changed tuple component diverges.
    for changed in (
        _v2("text.other", "gpt-5.4", "gpt-5.4-2026-06-01", "eu-frankfurt-1"),
        _v2("text.openai", "gpt-5.5", "gpt-5.4-2026-06-01", "eu-frankfurt-1"),
        _v2("text.openai", "gpt-5.4", "gpt-5.4-2026-07-01", "eu-frankfurt-1"),
        _v2("text.openai", "gpt-5.4", "gpt-5.4-2026-06-01", None),
    ):
        assert changed != first


def test_the_migration_backfill_derivation_matches_the_live_derivation() -> None:
    """The migration carries a frozen copy of the derivation so replay is
    stable forever; this pins that the frozen copy and the live function
    agree - drift between them would backfill a different identity than new
    writes stamp."""

    import importlib.util

    migration_path = (
        Path(__file__).resolve().parents[2]
        / "alembic"
        / "versions"
        / "0070_candidate_identity_v2.py"
    )
    spec = importlib.util.spec_from_file_location("migration_0070", migration_path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    samples = [
        ("text.local", "qwen3:8b", "qwen3:8b", None),
        ("text.openai", "gpt-5.4", "gpt-5.4-2026-06-01", "eu-frankfurt-1"),
        ("p", "f", "a:b", ""),
    ]
    for provider, family, revision, deployment in samples:
        assert migration._derive_candidate_identity_v2(
            provider, family, revision, deployment
        ) == _v2(provider, family, revision, deployment)


def test_entry_model_stamps_and_defends_the_canonical_identity() -> None:
    entry = _entry("text.regional", "claude-sonnet-5", "claude-sonnet-5-2026-05", "eu-1")
    assert entry.candidate_id_v2 == _v2(
        "text.regional", "claude-sonnet-5", "claude-sonnet-5-2026-05", "eu-1"
    )

    with pytest.raises(ValueError, match="must equal the canonical identity"):
        _entry(
            "text.regional",
            "claude-sonnet-5",
            "claude-sonnet-5-2026-05",
            "eu-1",
            candidate_id_v2="cand2_" + "0" * 64,
        )


def _entry(
    provider: str,
    family: str,
    revision: str,
    deployment: str | None,
    *,
    entry_id: str | None = None,
    candidate_id_v2: str = "",
) -> ModelCatalogueEntry:
    return ModelCatalogueEntry(
        entry_id=entry_id
        or derive_model_catalogue_entry_id(
            provider_id=provider, model_revision=revision, deployment=deployment
        ),
        candidate_id_v2=candidate_id_v2,
        provider_id=provider,
        provider_mode="openai",
        model_family=family,
        model_revision=revision,
        deployment=deployment,
        sku=None,
        lifecycle_state=ModelLifecycleState.CATALOGUED,
        revision_pinned=True,
        modalities=["text"],
        seed_source=ModelCatalogueSeedSource.SETTINGS_LIVE_TEXT,
        created_at="2026-09-04T00:00:00Z",
        last_updated_at="2026-09-04T00:00:00Z",
    )


def test_persistence_refuses_two_rows_for_one_serving_tuple(tmp_path: Path) -> None:
    """The steering's regression shield: even if id derivation regressed and
    produced two different row keys for one logical candidate, the
    structural uniqueness over (provider, family, revision, deployment_key)
    refuses the second row instead of silently collapsing candidates."""

    from app.repositories.sqlalchemy_model_catalogue_repository import (
        SqlAlchemyModelCatalogueRepository,
    )
    from tests.support.migration_runner import upgrade_database_to_head

    database_url = f"sqlite:///{tmp_path / 'identity-v2.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyModelCatalogueRepository(database_url)

    repository.upsert_entry(_entry("text.openai", "fam", "rev-1", "eu-1"))
    regressed = _entry("text.openai", "fam", "rev-1", "eu-1", entry_id="regressed:row:key")
    with pytest.raises(IntegrityError):
        repository.upsert_entry(regressed)

    # Round-trip: the stored canonical id survives restartable reads intact.
    stored = repository.get_entry(
        derive_model_catalogue_entry_id(
            provider_id="text.openai", model_revision="rev-1", deployment="eu-1"
        )
    )
    assert stored is not None
    assert stored.candidate_id_v2 == _v2("text.openai", "fam", "rev-1", "eu-1")


def test_collision_audit_over_current_configuration() -> None:
    """The executable audit (issue #314): enumerate the currently derivable
    candidates - settings seeds plus declared connection material - derive
    each structured tuple independently, and prove every pair of distinct
    tuples has distinct v2 identities, with any v1 string collision named
    rather than silent."""

    from app.services.model_catalogue import build_seed_model_catalogue_entries
    from app.services.provider_connection_material import configured_connection_materials
    from app.services.provider_execution_config import resolve_provider_execution_config

    settings.provider_mode = "local_openai_compatible"
    settings.live_text_provider_id = "text.local"
    settings.live_text_model_id = "qwen3:8b"
    settings.live_text_model_version = None
    settings.workflow_run_model_risk_inventory_json = "[]"
    settings.provider_connections_json = json.dumps(
        [
            {
                "provider_id": "text.regional",
                "model_id": "claude-sonnet-5",
                "api_base": "https://eu.example/v1",
                "deployment": "eu-frankfurt-1",
            }
        ]
    )

    tuples: list[tuple[str, str, str, str | None]] = []
    for entry in build_seed_model_catalogue_entries():
        tuples.append(
            (entry.provider_id, entry.model_family, entry.model_revision, entry.deployment)
        )
    config = resolve_provider_execution_config()
    for material in configured_connection_materials(config).values():
        tuples.append(
            (
                material.provider_id,
                material.model_id,
                material.model_version or material.model_id,
                material.deployment,
            )
        )

    distinct_tuples = sorted(set(tuples))
    v2_ids = [_v2(*serving_tuple) for serving_tuple in distinct_tuples]
    assert len(set(v2_ids)) == len(distinct_tuples), "v2 collision between distinct tuples"
    # The audit names the known v1 ambiguity honestly: the default local
    # identity contains the delimiter inside its revision.
    assert any(":" in revision for (_, _, revision, _) in distinct_tuples)


def test_canonical_lookup_resolves_hits_and_misses_on_both_adapters(tmp_path: Path) -> None:
    """resolve_catalogue_entry_by_identity accepts either representation by
    exact key on both store adapters, and a canonical id no row carries
    resolves to None rather than being parsed or guessed."""

    from app.repositories.sqlalchemy_model_catalogue_repository import (
        SqlAlchemyModelCatalogueRepository,
    )
    from app.services.model_catalogue import resolve_catalogue_entry_by_identity
    from app.services.model_catalogue_store import get_model_catalogue_repository
    from tests.support.migration_runner import upgrade_database_to_head

    entry = _entry("text.openai", "fam", "rev-1", "eu-1")
    get_model_catalogue_repository().upsert_entry(entry)
    by_canonical = resolve_catalogue_entry_by_identity(entry.candidate_id_v2)
    assert by_canonical is not None and by_canonical.entry_id == entry.entry_id
    by_row_key = resolve_catalogue_entry_by_identity(entry.entry_id)
    assert by_row_key is not None and by_row_key.candidate_id_v2 == entry.candidate_id_v2
    assert resolve_catalogue_entry_by_identity("cand2_" + "f" * 64) is None

    database_url = f"sqlite:///{tmp_path / 'identity-v2-lookup.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyModelCatalogueRepository(database_url)
    repository.upsert_entry(entry)
    stored = repository.get_entry_by_candidate_id(entry.candidate_id_v2)
    assert stored is not None and stored.entry_id == entry.entry_id
    assert repository.get_entry_by_candidate_id("cand2_" + "f" * 64) is None


def test_both_adapters_refuse_a_drifted_canonical_id(tmp_path: Path) -> None:
    """The drift shield (issue #314 S2a): model_copy that changes identity
    fields but keeps the original canonical id is refused loudly by BOTH
    write adapters - never stored, never silently corrected past a
    contradiction."""

    from app.repositories.sqlalchemy_model_catalogue_repository import (
        SqlAlchemyModelCatalogueRepository,
    )
    from app.services.model_catalogue_store import get_model_catalogue_repository
    from tests.support.migration_runner import upgrade_database_to_head

    original = _entry("text.openai", "fam", "rev-1", None)
    drifted = original.model_copy(
        update={"entry_id": "text.openai:rev-2", "model_revision": "rev-2"}
    )

    with pytest.raises(ValueError, match="drifted"):
        get_model_catalogue_repository().upsert_entry(drifted)

    database_url = f"sqlite:///{tmp_path / 'identity-v2-drift.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyModelCatalogueRepository(database_url)
    with pytest.raises(ValueError, match="drifted"):
        repository.upsert_entry(drifted)


def test_candidate_identity_v2_grammar_is_the_debit_segment_guarantee() -> None:
    """The attempt-debit identity embeds candidate_id_v2 between colon
    delimiters (``adbt2:{execution}:{candidate_id_v2}:{attempt}``). This
    grammar is what keeps that segment delimiter-unambiguous -- the defect
    the legacy entry-id segment had: ``cand2_`` plus exactly 64 hex digits,
    colon-free by construction, for every input including hostile ones."""

    import re as _re

    for deployment in (None, "eu-west-1", "with:colons", "unicode-\u2603"):
        identity = derive_candidate_identity_v2(
            provider_id="provider:with:colons",
            model_family="family:x",
            model_revision="rev:1",
            deployment=deployment,
        )
        assert _re.fullmatch(r"cand2_[0-9a-f]{64}", identity), identity
