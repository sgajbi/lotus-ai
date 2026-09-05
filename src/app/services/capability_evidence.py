"""Scope-aware observed-capability evidence (issue #312).

The write side records the authoritative claims a PASS evaluation run
proves - one record per proof its fixture family declares, bound to the
candidate that served every case. The read side answers eligibility's
question: does applicable PASS evidence exist for this exact candidate,
dimension and scope? Evidence ENABLES the governed lifecycle decision; it
never makes it, and unknown never upgrades into truth.
"""

from __future__ import annotations

import logging

from datetime import UTC, datetime

from app.contracts.evals import CapabilityEvidenceScopeType, EvaluationRunVerdict
from app.contracts.model_catalogue import CapabilityEvidenceRecord, ModelCatalogueEntry
from app.repositories.evaluation_runtime_repository import (
    EvaluationCaseResultRecord,
    EvaluationRunRecord,
)
from app.services.model_catalogue_store import get_model_catalogue_repository

_logger = logging.getLogger(__name__)


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
    digest_mismatch = (
        run.manifest_content_digest is not None
        and manifest.manifest_content_digest != run.manifest_content_digest
    )
    if manifest.manifest_version != run.manifest_version or digest_mismatch:
        # Version pinning, fail-closed (issue #332): the run executed under
        # one manifest version but the CURRENT manifest is another - loading
        # today's declarations would label them with the run's version,
        # certifying content the run never exercised. A queued run across a
        # fixture change yields no evidence, loudly.
        # Both must match (issue #351): the digest catches unbumped content
        # drift, the label catches undigested operator intent - either
        # mismatch refuses. Historical runs without a digest stay guarded by
        # the label alone, stated rather than backfilled.
        _logger.warning(
            "capability evidence refused: run %s executed under manifest %s "
            "(digest %s) but the current manifest is %s (digest %s) - "
            "proof-producing content cannot be re-established",
            run.run_id,
            run.manifest_version,
            run.manifest_content_digest,
            manifest.manifest_version,
            manifest.manifest_content_digest,
        )
        return
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
                manifest_content_digest=run.manifest_content_digest,
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

    from app.services.evaluation_runtime_store import get_evaluation_runtime_store

    repository = get_model_catalogue_repository()
    runtime_store = get_evaluation_runtime_store()
    for record in repository.list_capability_evidence(
        candidate_id_v2=entry.candidate_id_v2, dimension=dimension
    ):
        if record.verdict != EvaluationRunVerdict.PASS.value:
            continue
        if record.model_revision != entry.model_revision:
            continue
        # Committed-producing-run contingency (issue #332): a claim is
        # applicable only when its producing run exists as a COMPLETED PASS
        # record - evidence orphaned by a failure between claim creation and
        # run commitment (or surviving a deleted run) is never honored.
        producing_run = runtime_store.get_run(run_id=record.evaluation_run_id)
        if (
            producing_run is None
            or producing_run.lifecycle_status != "COMPLETED"
            or producing_run.verdict != EvaluationRunVerdict.PASS.value
        ):
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
