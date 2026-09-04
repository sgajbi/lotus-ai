"""Scope-aware observed-capability evidence (issue #312).

The write side records the authoritative claims a PASS evaluation run
proves - one record per proof its fixture family declares, bound to the
candidate that served every case. The read side answers eligibility's
question: does applicable PASS evidence exist for this exact candidate,
dimension and scope? Evidence ENABLES the governed lifecycle decision; it
never makes it, and unknown never upgrades into truth.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.contracts.evals import CapabilityEvidenceScopeType, EvaluationRunVerdict
from app.contracts.model_catalogue import CapabilityEvidenceRecord, ModelCatalogueEntry
from app.repositories.evaluation_runtime_repository import (
    EvaluationCaseResultRecord,
    EvaluationRunRecord,
)
from app.services.model_catalogue_store import get_model_catalogue_repository


def record_capability_evidence_for_pass_run(
    *, run: EvaluationRunRecord, results: list[EvaluationCaseResultRecord]
) -> None:
    """Persist the scope-aware claims a PASS run proves.

    A run whose serving candidate is unknown for any case - or that more
    than one candidate served - yields no evidence rather than mis-binding.
    A candidate that vanished from the catalogue binds nothing.
    """

    from app.evals.fixture_manifest import load_evaluation_fixture_manifest

    manifest = load_evaluation_fixture_manifest()
    fixture = next((f for f in manifest.fixture_families if f.fixture_id == run.fixture_id), None)
    if fixture is None or not fixture.proves:
        return
    served = {result.candidate_id_v2 for result in results}
    if len(served) != 1 or None in served:
        return
    candidate_id_v2 = next(iter(served))
    assert candidate_id_v2 is not None
    repository = get_model_catalogue_repository()
    entry = repository.get_entry_by_candidate_id(candidate_id_v2)
    if entry is None:
        return
    for proof in fixture.proves:
        repository.save_capability_evidence(
            CapabilityEvidenceRecord(
                evidence_id=(f"capev_{run.run_id}_{proof.dimension}_{proof.scope_key or 'global'}"),
                candidate_id_v2=candidate_id_v2,
                model_revision=entry.model_revision,
                dimension=proof.dimension,
                scope_type=proof.scope_type.value,
                scope_key=proof.scope_key,
                fixture_id=run.fixture_id,
                manifest_version=run.manifest_version,
                evaluation_run_id=run.run_id,
                verdict=EvaluationRunVerdict.PASS.value,
                triggered_by=run.triggered_by,
                recorded_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            )
        )


def applicable_capability_evidence(
    *,
    entry: ModelCatalogueEntry,
    dimension: str,
    output_contract_key: str | None,
) -> CapabilityEvidenceRecord | None:
    """The observed-evidence answer eligibility consumes (issue #312).

    A PASS record applies when it binds this exact candidate AND revision,
    at GLOBAL scope or at the OUTPUT_CONTRACT scope this execution
    validates under. Revision-mismatched, scope-mismatched or absent
    evidence stays unknown - never widened, never inferred.
    """

    repository = get_model_catalogue_repository()
    for record in repository.list_capability_evidence(
        candidate_id_v2=entry.candidate_id_v2, dimension=dimension
    ):
        if record.verdict != EvaluationRunVerdict.PASS.value:
            continue
        if record.model_revision != entry.model_revision:
            continue
        if record.scope_type == CapabilityEvidenceScopeType.GLOBAL.value:
            return record
        if (
            record.scope_type == CapabilityEvidenceScopeType.OUTPUT_CONTRACT.value
            and output_contract_key is not None
            and record.scope_key == output_contract_key
        ):
            return record
    return None
