"""Scope-aware observed-capability evidence (issue #312 S3).

A PASS run over a declaring fixture family yields one authoritative record
per declared proof, bound to the candidate that served every case; mixed or
unknown serving candidates yield nothing; and eligibility consumes exactly
the matching scoped PASS claim - never a widened one.
"""

from __future__ import annotations


import pytest

from app.contracts.evals import (
    CapabilityEvidenceScopeType,
    CapabilityProofDeclaration,
    EvaluationAssetStatus,
    EvaluationFixtureDescriptor,
)
from app.contracts.model_catalogue import (
    ModelCatalogueEntry,
    ModelCatalogueSeedSource,
    ModelLifecycleState,
    derive_model_catalogue_entry_id,
)
from app.contracts.providers import ProviderFailureCategory
from app.providers.base import ProviderExecutionError
from app.repositories.evaluation_runtime_repository import (
    EvaluationCaseResultRecord,
    EvaluationRunRecord,
)
from app.services.capability_evidence import (
    applicable_capability_evidence,
    record_capability_evidence_for_pass_run,
)
from app.services.model_catalogue import (
    enforce_capability_requirements,
    upsert_model_catalogue_entry,
)
from app.services.model_catalogue_store import get_model_catalogue_repository

PROVIDER = "text.regional"
MODEL = "claude-sonnet-5"
REVISION = "claude-sonnet-5-2026-05"


def _catalogued_entry() -> ModelCatalogueEntry:
    entry = ModelCatalogueEntry(
        entry_id=derive_model_catalogue_entry_id(
            provider_id=PROVIDER, model_revision=REVISION, deployment=None
        ),
        provider_id=PROVIDER,
        provider_mode="openai",
        model_family=MODEL,
        model_revision=REVISION,
        deployment=None,
        sku=None,
        lifecycle_state=ModelLifecycleState.APPROVED,
        revision_pinned=True,
        modalities=["text"],
        seed_source=ModelCatalogueSeedSource.SETTINGS_LIVE_TEXT,
        created_at="2026-09-01T00:00:00Z",
        last_updated_at="2026-09-01T00:00:00Z",
    )
    upsert_model_catalogue_entry(entry)
    stored = get_model_catalogue_repository().get_entry(entry.entry_id)
    assert stored is not None
    return stored


def _run(fixture_id: str = "capability_proof_examples") -> EvaluationRunRecord:
    return EvaluationRunRecord(
        run_id="evalrun_cap_001",
        fixture_id=fixture_id,
        manifest_version="foundation.v1",
        lifecycle_status="COMPLETED",
        triggered_by="operator-a",
        submitted_at="2026-09-05T00:00:00Z",
        async_job_id=None,
        latest_message="done",
        verdict="PASS",
        case_count=2,
    )


def _case(case_id: str, candidate_id_v2: str | None) -> EvaluationCaseResultRecord:
    return EvaluationCaseResultRecord(
        case_result_id=f"attempt_{case_id}",
        run_id="evalrun_cap_001",
        attempt_id="attempt_001",
        case_id=case_id,
        fixture_id="capability_proof_examples",
        outcome="PASS",
        summary="ok",
        evidence_refs=[],
        artifact_ids=[],
        provider_config_sha256="d" * 64,
        candidate_id_v2=candidate_id_v2,
        recorded_at="2026-09-05T00:01:00Z",
    )


def _declaring_manifest(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.evals import fixture_manifest as manifest_module

    declaring = EvaluationFixtureDescriptor(
        fixture_id="capability_proof_examples",
        status=EvaluationAssetStatus.STAGED,
        description="Capability proof fixtures.",
        manifest_path="docs/evals/fixtures/explain.v1/basic_cases.json",
        proves=[
            CapabilityProofDeclaration(
                dimension="supports_tool_calling",
                scope_type=CapabilityEvidenceScopeType.GLOBAL,
            ),
            CapabilityProofDeclaration(
                dimension="supports_structured_output",
                scope_type=CapabilityEvidenceScopeType.OUTPUT_CONTRACT,
                scope_key="advisor_brief.pack",
            ),
        ],
    )
    manifest = manifest_module.EvaluationFixtureManifest(
        manifest_version="foundation.v1",
        evidence_categories=[],
        fixture_families=[declaring],
    )
    monkeypatch.setattr(
        "app.evals.fixture_manifest.load_evaluation_fixture_manifest", lambda: manifest
    )


def test_a_pass_run_records_one_claim_per_declared_proof(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entry = _catalogued_entry()
    _declaring_manifest(monkeypatch)

    record_capability_evidence_for_pass_run(
        run=_run(),
        results=[
            _case("case_001", entry.candidate_id_v2),
            _case("case_002", entry.candidate_id_v2),
        ],
    )

    repository = get_model_catalogue_repository()
    tool_rows = repository.list_capability_evidence(
        candidate_id_v2=entry.candidate_id_v2, dimension="supports_tool_calling"
    )
    assert len(tool_rows) == 1
    assert tool_rows[0].scope_type == "GLOBAL"
    assert tool_rows[0].model_revision == REVISION
    assert tool_rows[0].evaluation_run_id == "evalrun_cap_001"
    scoped_rows = repository.list_capability_evidence(
        candidate_id_v2=entry.candidate_id_v2, dimension="supports_structured_output"
    )
    assert len(scoped_rows) == 1
    assert scoped_rows[0].scope_key == "advisor_brief.pack"


def test_unknown_or_mixed_serving_candidates_yield_no_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entry = _catalogued_entry()
    _declaring_manifest(monkeypatch)

    record_capability_evidence_for_pass_run(
        run=_run(),
        results=[_case("case_001", entry.candidate_id_v2), _case("case_002", None)],
    )
    record_capability_evidence_for_pass_run(
        run=_run(),
        results=[
            _case("case_001", entry.candidate_id_v2),
            _case("case_002", "cand2_" + "b" * 64),
        ],
    )

    assert (
        get_model_catalogue_repository().list_capability_evidence(
            candidate_id_v2=entry.candidate_id_v2, dimension="supports_tool_calling"
        )
        == []
    )


def test_eligibility_consumes_exactly_the_matching_scoped_claim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The steering's core invariant: structured-output evidence for ONE
    approved output contract never becomes a universal statement, a global
    claim serves everywhere, and revision-mismatched evidence stays
    unknown."""

    from app.contracts.capability_requirements import CapabilityRequirements

    entry = _catalogued_entry()
    _declaring_manifest(monkeypatch)
    record_capability_evidence_for_pass_run(
        run=_run(),
        results=[_case("case_001", entry.candidate_id_v2)],
    )

    tool_required = CapabilityRequirements(tool_calling_required=True)
    # GLOBAL evidence satisfies the unknown declared fact everywhere.
    enforce_capability_requirements(requirements=tool_required, entry=entry)

    structured_required = CapabilityRequirements(structured_output_required=True)
    # The scoped claim satisfies exactly its contract...
    enforce_capability_requirements(
        requirements=structured_required,
        entry=entry,
        output_contract_key="advisor_brief.pack",
    )
    # ...and no other contract, and not the global question.
    with pytest.raises(ProviderExecutionError) as other_scope:
        enforce_capability_requirements(
            requirements=structured_required,
            entry=entry,
            output_contract_key="some_other.pack",
        )
    assert other_scope.value.category is ProviderFailureCategory.CAPABILITY_UNKNOWN
    with pytest.raises(ProviderExecutionError) as no_scope:
        enforce_capability_requirements(requirements=structured_required, entry=entry)
    assert no_scope.value.category is ProviderFailureCategory.CAPABILITY_UNKNOWN

    # Revision drift invalidates the claim: same candidate id cannot occur
    # with a different revision (identity binds it), so simulate via the
    # applicable-evidence check on a modified entry copy.
    drifted = entry.model_copy(
        update={"model_revision": "claude-sonnet-5-2026-06", "candidate_id_v2": ""}
    )
    assert (
        applicable_capability_evidence(
            entry=drifted,
            dimension="supports_tool_calling",
            output_contract_key=None,
        )
        is None
    )


def test_undeclared_families_and_vanished_candidates_record_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entry = _catalogued_entry()
    from app.evals import fixture_manifest as manifest_module

    manifest = manifest_module.EvaluationFixtureManifest(
        manifest_version="foundation.v1",
        evidence_categories=[],
        fixture_families=[
            EvaluationFixtureDescriptor(
                fixture_id="capability_proof_examples",
                status=EvaluationAssetStatus.STAGED,
                description="No declarations.",
                manifest_path="docs/evals/fixtures/explain.v1/basic_cases.json",
            )
        ],
    )
    monkeypatch.setattr(
        "app.evals.fixture_manifest.load_evaluation_fixture_manifest", lambda: manifest
    )
    record_capability_evidence_for_pass_run(
        run=_run(), results=[_case("case_001", entry.candidate_id_v2)]
    )
    assert (
        get_model_catalogue_repository().list_capability_evidence(
            candidate_id_v2=entry.candidate_id_v2, dimension="supports_tool_calling"
        )
        == []
    )

    _declaring_manifest(monkeypatch)
    record_capability_evidence_for_pass_run(
        run=_run(), results=[_case("case_001", "cand2_" + "c" * 64)]
    )
    assert (
        get_model_catalogue_repository().list_capability_evidence(
            candidate_id_v2="cand2_" + "c" * 64, dimension="supports_tool_calling"
        )
        == []
    )


def test_evidence_rows_round_trip_and_expire_on_both_adapters(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """The evidence store behaves identically on both adapters: save/list
    round-trips the full binding, list_all feeds the lifecycle engine, and
    delete removes exactly the named rows (expiry then honestly reverts the
    claim to unknown)."""

    from app.contracts.model_catalogue import CapabilityEvidenceRecord
    from app.repositories.sqlalchemy_model_catalogue_repository import (
        SqlAlchemyModelCatalogueRepository,
    )
    from tests.support.migration_runner import upgrade_database_to_head

    def _record(evidence_id: str, verdict: str = "PASS") -> CapabilityEvidenceRecord:
        return CapabilityEvidenceRecord(
            evidence_id=evidence_id,
            candidate_id_v2="cand2_" + "e" * 64,
            model_revision=REVISION,
            dimension="supports_tool_calling",
            scope_type="GLOBAL",
            scope_key=None,
            fixture_id="capability_proof_examples",
            manifest_version="foundation.v1",
            evaluation_run_id="evalrun_cap_002",
            verdict=verdict,
            triggered_by="operator-a",
            recorded_at="2026-09-05T01:00:00Z",
        )

    stores = [get_model_catalogue_repository()]
    database_url = f"sqlite:///{tmp_path_factory.mktemp('capev') / 'capev.db'}"
    upgrade_database_to_head(database_url)
    stores.append(SqlAlchemyModelCatalogueRepository(database_url))

    for store in stores:
        store.save_capability_evidence(_record("capev_a"))
        store.save_capability_evidence(_record("capev_b"))
        rows = store.list_capability_evidence(
            candidate_id_v2="cand2_" + "e" * 64, dimension="supports_tool_calling"
        )
        assert {row.evidence_id for row in rows} == {"capev_a", "capev_b"}
        assert rows[0].scope_type == "GLOBAL" and rows[0].model_revision == REVISION
        assert {row.evidence_id for row in store.list_all_capability_evidence(limit=10)} >= {
            "capev_a",
            "capev_b",
        }
        assert store.delete_capability_evidence(["capev_a", "missing"]) == 1
        remaining = store.list_capability_evidence(
            candidate_id_v2="cand2_" + "e" * 64, dimension="supports_tool_calling"
        )
        assert {row.evidence_id for row in remaining} == {"capev_b"}


def test_applicable_evidence_skips_non_pass_and_revision_mismatch() -> None:
    """The consumption filters, exercised directly: a FAIL row is never
    evidence, and a row for another revision of the same candidate id shape
    stays unknown."""

    from app.contracts.model_catalogue import CapabilityEvidenceRecord

    entry = _catalogued_entry()
    repository = get_model_catalogue_repository()
    repository.save_capability_evidence(
        CapabilityEvidenceRecord(
            evidence_id="capev_fail",
            candidate_id_v2=entry.candidate_id_v2,
            model_revision=REVISION,
            dimension="supports_tool_calling",
            scope_type="GLOBAL",
            scope_key=None,
            fixture_id="capability_proof_examples",
            manifest_version="foundation.v1",
            evaluation_run_id="evalrun_cap_003",
            verdict="FAIL",
            triggered_by=None,
            recorded_at="2026-09-05T01:01:00Z",
        )
    )
    repository.save_capability_evidence(
        CapabilityEvidenceRecord(
            evidence_id="capev_other_rev",
            candidate_id_v2=entry.candidate_id_v2,
            model_revision="claude-sonnet-5-2026-06",
            dimension="supports_tool_calling",
            scope_type="GLOBAL",
            scope_key=None,
            fixture_id="capability_proof_examples",
            manifest_version="foundation.v1",
            evaluation_run_id="evalrun_cap_004",
            verdict="PASS",
            triggered_by=None,
            recorded_at="2026-09-05T01:02:00Z",
        )
    )

    assert (
        applicable_capability_evidence(
            entry=entry, dimension="supports_tool_calling", output_contract_key=None
        )
        is None
    )
