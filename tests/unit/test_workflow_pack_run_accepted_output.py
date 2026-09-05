"""Projector-level pins for the accepted-output projection (issue #162).

The API contract tests cover the reachable lifecycle postures end to end; these
pin the postures only a corrupted or edited ledger can produce, plus hash
determinism and sensitivity, directly against the service.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from typing import Any

import pytest

from collections.abc import Callable

from app.contracts.artifacts import (
    ArtifactDescriptor,
    ArtifactLifecycleStatus,
    ArtifactStorageBackend,
)
from app.contracts.workflow_pack_run_accepted_output import (
    AdvisorBriefAcceptedReviewIdentity,
)
from app.repositories.workflow_pack_run_repository import WorkflowPackRunRecord
from app.services import workflow_pack_run_accepted_output as module
from app.services.workflow_pack_run_accepted_output import (
    AcceptedOutputNotAvailableError,
    AcceptedOutputNotFoundError,
    build_workflow_pack_run_accepted_output,
)
from tests.support.workflow_pack_run_builders import validated_output_evidence
from app.contracts.evidence import ExecutionEvidenceDescriptor

TENANT = "tenant-sg-001"


def _record(**overrides: Any) -> WorkflowPackRunRecord:
    payload: dict[str, Any] = {
        "run_id": "wfr-accepted-001",
        "pack_id": "advisor_brief.pack",
        "pack_family": "advisor_brief",
        "pack_version": "v1",
        "registration_ref": "advisor_brief.pack@v1",
        "task_id": "explain.v1",
        "request_id": "req-001",
        "caller_app": "lotus-gateway",
        "correlation_id": "corr-001",
        "tenant_id": TENANT,
        "workflow_surface": "advisor-brief-workspace",
        "workflow_authority_owner": "lotus-gateway",
        "runtime_state": "COMPLETED",
        "review_state": "ACCEPTED",
        "review_required": True,
        "provider_mode": "stub",
        "stubbed": True,
        "output_preview": "preview",
        "structured_output_keys": ["grounded_summary"],
        "evidence_descriptors": [validated_output_evidence()],
        "artifact_refs": [
            ArtifactDescriptor(
                artifact_id="art-001",
                domain="workflow_pack",
                artifact_type="run_output_summary",
                source_object_kind="workflow_pack_run",
                source_object_id="wfr-accepted-001",
                lifecycle_status=ArtifactLifecycleStatus.RUNTIME_GENERATED,
                retention_posture="retained_for_review",
                media_type="application/json",
                byte_size=512,
                checksum_sha256="0" * 64,
                storage_backend=ArtifactStorageBackend.MEMORY,
                storage_reference="artifact://runs/wfr-accepted-001.json",
                created_at="2026-08-30T09:00:00Z",
                created_by="lotus-ai.workflow-pack-run-ledger",
            )
        ],
        "supersedes_run_id": None,
        "superseded_by_run_id": None,
        "created_at": "2026-08-30T09:00:00Z",
        "completed_at": "2026-08-30T09:00:05Z",
        "last_updated_at": "2026-08-30T09:00:05Z",
    }
    payload.update(overrides)
    return WorkflowPackRunRecord(**payload)


def _artifact_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "run_id": "wfr-accepted-001",
        "pack_id": "advisor_brief.pack",
        "source_refs": ["lotus-gateway:performance-summary:YTD"],
        "evidence_types": ["task_contract"],
        "structured_output": {
            "advisor_brief_status": "complete",
            "coverage_state": "complete",
            "portfolio_id": "PB_SG_GLOBAL_BAL_001",
            "period": "YTD",
            "grounded_summary": "The portfolio returned 1.25% in YTD.",
            "talking_points": [
                {
                    "headline": "Active return was -6.68%.",
                    "detail": "Portfolio 1.25% versus benchmark 7.93%.",
                    "tone": "warning",
                    "evidence_refs": [
                        {
                            "metric_label": "Active Return",
                            "metric_value": "-6.68%",
                            "source_ref": "lotus-gateway:performance-summary:YTD",
                        }
                    ],
                }
            ],
            "risks_and_exceptions": [],
        },
    }
    payload.update(overrides)
    return payload


class _StoreStub:
    def __init__(self, record: WorkflowPackRunRecord | None) -> None:
        self._record = record

    def get_run(self, *, run_id: str) -> WorkflowPackRunRecord | None:
        return self._record

    def list_events(self, *, run_id: str) -> list[Any]:
        return []


class _ObjectStoreStub:
    def __init__(self, payload: bytes | None) -> None:
        self._payload = payload

    def get_object(self, *, object_key: str) -> Any:
        if self._payload is None:
            return None

        class _Stored:
            payload = self._payload

        return _Stored()


WireCallable = Callable[..., None]


def _serialize(payload: dict[str, Any] | bytes | None) -> bytes | None:
    if isinstance(payload, dict):
        return json.dumps(payload).encode("utf-8")
    return payload


@pytest.fixture
def _wired(monkeypatch: pytest.MonkeyPatch) -> WireCallable:
    def wire(
        record: WorkflowPackRunRecord | None,
        artifact_payload: dict[str, Any] | bytes | None,
        *,
        recorded_payload: dict[str, Any] | bytes | None = None,
    ) -> None:
        raw = _serialize(artifact_payload)
        # The descriptor records the checksum/size of the bytes that existed at
        # persistence time (issue #328): by default that is what the store now
        # holds; a tamper scenario records the ORIGINAL bytes while the store
        # holds changed ones.
        recorded = _serialize(recorded_payload) if recorded_payload is not None else raw
        if record is not None and recorded is not None:
            refreshed_refs = [
                artifact.model_copy(
                    update={
                        "checksum_sha256": hashlib.sha256(recorded).hexdigest(),
                        "byte_size": len(recorded),
                    }
                )
                if artifact.artifact_type == "run_output_summary"
                else artifact
                for artifact in record.artifact_refs
            ]
            record = dataclasses.replace(record, artifact_refs=refreshed_refs)
        monkeypatch.setattr(module, "ensure_workflow_pack_run_store_ready", lambda: None)
        monkeypatch.setattr(module, "get_workflow_pack_run_store", lambda: _StoreStub(record))
        monkeypatch.setattr(module, "get_artifact_object_store", lambda: _ObjectStoreStub(raw))
        monkeypatch.setattr(
            module,
            "_accepting_review_identity",
            lambda **_: AdvisorBriefAcceptedReviewIdentity(
                reviewed_by="banker.sg.301",
                reviewed_at="2026-08-30T09:05:00Z",
            ),
        )

    return wire


def _reason(excinfo: pytest.ExceptionInfo[AcceptedOutputNotAvailableError]) -> str:
    return excinfo.value.reason_code


def test_tenantless_and_foreign_runs_share_the_not_found_shape(_wired: WireCallable) -> None:
    _wired(_record(tenant_id=None), _artifact_payload())
    with pytest.raises(AcceptedOutputNotFoundError):
        build_workflow_pack_run_accepted_output(run_id="wfr-accepted-001", caller_tenant_id=TENANT)

    _wired(_record(), _artifact_payload())
    with pytest.raises(AcceptedOutputNotFoundError):
        build_workflow_pack_run_accepted_output(
            run_id="wfr-accepted-001", caller_tenant_id="tenant-uk-999"
        )


def test_unregistered_pack_version_is_refused(_wired: WireCallable) -> None:
    _wired(_record(pack_version="v2", registration_ref="advisor_brief.pack@v2"), None)
    with pytest.raises(AcceptedOutputNotAvailableError) as excinfo:
        build_workflow_pack_run_accepted_output(run_id="wfr-accepted-001", caller_tenant_id=TENANT)
    assert _reason(excinfo) == "pack_projection_unsupported"


def test_superseded_accepted_run_is_refused(_wired: WireCallable) -> None:
    _wired(_record(superseded_by_run_id="wfr-accepted-002"), _artifact_payload())
    with pytest.raises(AcceptedOutputNotAvailableError) as excinfo:
        build_workflow_pack_run_accepted_output(run_id="wfr-accepted-001", caller_tenant_id=TENANT)
    assert _reason(excinfo) == "run_superseded"


def test_artifact_identity_mismatch_is_malformed(_wired: WireCallable) -> None:
    _wired(_record(), _artifact_payload(run_id="wfr-some-other-run"))
    with pytest.raises(AcceptedOutputNotAvailableError) as excinfo:
        build_workflow_pack_run_accepted_output(run_id="wfr-accepted-001", caller_tenant_id=TENANT)
    assert _reason(excinfo) == "output_artifact_malformed"


def test_missing_artifact_object_is_missing_not_malformed(_wired: WireCallable) -> None:
    _wired(_record(), None)
    with pytest.raises(AcceptedOutputNotAvailableError) as excinfo:
        build_workflow_pack_run_accepted_output(run_id="wfr-accepted-001", caller_tenant_id=TENANT)
    assert _reason(excinfo) == "output_artifact_missing"


def test_unparseable_artifact_is_malformed(_wired: WireCallable) -> None:
    _wired(_record(), b"\xff not json")
    with pytest.raises(AcceptedOutputNotAvailableError) as excinfo:
        build_workflow_pack_run_accepted_output(run_id="wfr-accepted-001", caller_tenant_id=TENANT)
    assert _reason(excinfo) == "output_artifact_malformed"


def test_missing_required_narrative_field_is_malformed(_wired: WireCallable) -> None:
    payload = _artifact_payload()
    del payload["structured_output"]["grounded_summary"]
    _wired(_record(), payload)
    with pytest.raises(AcceptedOutputNotAvailableError) as excinfo:
        build_workflow_pack_run_accepted_output(run_id="wfr-accepted-001", caller_tenant_id=TENANT)
    assert _reason(excinfo) == "output_artifact_malformed"


def test_accepted_but_incomplete_run_is_refused(_wired: WireCallable) -> None:
    _wired(_record(runtime_state="FAILED"), _artifact_payload())
    with pytest.raises(AcceptedOutputNotAvailableError) as excinfo:
        build_workflow_pack_run_accepted_output(run_id="wfr-accepted-001", caller_tenant_id=TENANT)
    assert _reason(excinfo) == "run_not_completed"


def test_accepted_state_without_recorded_review_event_is_malformed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Deliberately NOT using `_wired`: it stubs `_accepting_review_identity`, and
    # this pin is about that function refusing an ACCEPTED record whose event
    # ledger carries no review transition.
    raw = json.dumps(_artifact_payload()).encode("utf-8")
    record = _record()
    record = dataclasses.replace(
        record,
        artifact_refs=[
            artifact.model_copy(
                update={
                    "checksum_sha256": hashlib.sha256(raw).hexdigest(),
                    "byte_size": len(raw),
                }
            )
            for artifact in record.artifact_refs
        ],
    )
    monkeypatch.setattr(module, "ensure_workflow_pack_run_store_ready", lambda: None)
    monkeypatch.setattr(module, "get_workflow_pack_run_store", lambda: _StoreStub(record))
    monkeypatch.setattr(module, "get_artifact_object_store", lambda: _ObjectStoreStub(raw))
    with pytest.raises(AcceptedOutputNotAvailableError) as excinfo:
        build_workflow_pack_run_accepted_output(run_id="wfr-accepted-001", caller_tenant_id=TENANT)
    assert _reason(excinfo) == "output_artifact_malformed"


def test_unlinked_output_artifact_is_missing(_wired: WireCallable) -> None:
    _wired(_record(artifact_refs=[]), _artifact_payload())
    with pytest.raises(AcceptedOutputNotAvailableError) as excinfo:
        build_workflow_pack_run_accepted_output(run_id="wfr-accepted-001", caller_tenant_id=TENANT)
    assert _reason(excinfo) == "output_artifact_missing"


def test_non_object_artifact_document_is_malformed(_wired: WireCallable) -> None:
    _wired(_record(), json.dumps(["not", "an", "object"]).encode("utf-8"))
    with pytest.raises(AcceptedOutputNotAvailableError) as excinfo:
        build_workflow_pack_run_accepted_output(run_id="wfr-accepted-001", caller_tenant_id=TENANT)
    assert _reason(excinfo) == "output_artifact_malformed"


def test_non_object_structured_output_is_malformed(_wired: WireCallable) -> None:
    _wired(_record(), _artifact_payload(structured_output="a bare narrative string"))
    with pytest.raises(AcceptedOutputNotAvailableError) as excinfo:
        build_workflow_pack_run_accepted_output(run_id="wfr-accepted-001", caller_tenant_id=TENANT)
    assert _reason(excinfo) == "output_artifact_malformed"


def test_non_list_narrative_collection_is_malformed(_wired: WireCallable) -> None:
    payload = _artifact_payload()
    payload["structured_output"]["talking_points"] = "not-a-list"
    _wired(_record(), payload)
    with pytest.raises(AcceptedOutputNotAvailableError) as excinfo:
        build_workflow_pack_run_accepted_output(run_id="wfr-accepted-001", caller_tenant_id=TENANT)
    assert _reason(excinfo) == "output_artifact_malformed"


def test_non_object_narrative_entry_is_malformed(_wired: WireCallable) -> None:
    payload = _artifact_payload()
    payload["structured_output"]["risks_and_exceptions"] = ["not-a-dict"]
    _wired(_record(), payload)
    with pytest.raises(AcceptedOutputNotAvailableError) as excinfo:
        build_workflow_pack_run_accepted_output(run_id="wfr-accepted-001", caller_tenant_id=TENANT)
    assert _reason(excinfo) == "output_artifact_malformed"


def test_content_hash_is_deterministic_and_sensitive(_wired: WireCallable) -> None:
    _wired(_record(), _artifact_payload())
    first = build_workflow_pack_run_accepted_output(
        run_id="wfr-accepted-001", caller_tenant_id=TENANT
    )
    _wired(_record(), _artifact_payload())
    second = build_workflow_pack_run_accepted_output(
        run_id="wfr-accepted-001", caller_tenant_id=TENANT
    )
    assert first.content_hash == second.content_hash

    changed_payload = _artifact_payload()
    changed_payload["structured_output"]["grounded_summary"] = (
        "The portfolio returned 1.26% in YTD."
    )
    _wired(_record(), changed_payload)
    changed = build_workflow_pack_run_accepted_output(
        run_id="wfr-accepted-001", caller_tenant_id=TENANT
    )
    assert changed.content_hash != first.content_hash

    context_changed_payload = _artifact_payload()
    context_changed_payload["structured_output"]["period"] = "1Y"
    _wired(_record(), context_changed_payload)
    context_changed = build_workflow_pack_run_accepted_output(
        run_id="wfr-accepted-001", caller_tenant_id=TENANT
    )
    assert context_changed.content_hash != first.content_hash


def test_projected_evidence_refs_carry_the_metric_grounding(_wired: WireCallable) -> None:
    """Regression for the silent grounding loss: the guardrail persists refs as
    metric dicts, and the projection must publish them - not filter them out."""

    _wired(_record(), _artifact_payload())
    response = build_workflow_pack_run_accepted_output(
        run_id="wfr-accepted-001", caller_tenant_id=TENANT
    )
    refs = response.talking_points[0].evidence_refs
    assert len(refs) == 1
    assert refs[0].metric_label == "Active Return"
    assert refs[0].metric_value == "-6.68%"
    assert refs[0].source_ref == "lotus-gateway:performance-summary:YTD"


def test_malformed_evidence_reference_entries_fail_closed(_wired: WireCallable) -> None:
    payload = _artifact_payload()
    payload["structured_output"]["talking_points"][0]["evidence_refs"] = ["a-bare-string"]
    _wired(_record(), payload)
    with pytest.raises(AcceptedOutputNotAvailableError) as excinfo:
        build_workflow_pack_run_accepted_output(run_id="wfr-accepted-001", caller_tenant_id=TENANT)
    assert _reason(excinfo) == "output_artifact_malformed"

    payload = _artifact_payload()
    payload["structured_output"]["talking_points"][0]["evidence_refs"] = [
        {"metric_label": "Active Return", "metric_value": "", "source_ref": "x"}
    ]
    _wired(_record(), payload)
    with pytest.raises(AcceptedOutputNotAvailableError) as excinfo:
        build_workflow_pack_run_accepted_output(run_id="wfr-accepted-001", caller_tenant_id=TENANT)
    assert _reason(excinfo) == "output_artifact_malformed"

    payload = _artifact_payload()
    payload["structured_output"]["talking_points"][0]["evidence_refs"] = "not-a-list"
    _wired(_record(), payload)
    with pytest.raises(AcceptedOutputNotAvailableError) as excinfo:
        build_workflow_pack_run_accepted_output(run_id="wfr-accepted-001", caller_tenant_id=TENANT)
    assert _reason(excinfo) == "output_artifact_malformed"


def test_absent_evidence_refs_key_projects_as_empty(_wired: WireCallable) -> None:
    payload = _artifact_payload()
    del payload["structured_output"]["talking_points"][0]["evidence_refs"]
    _wired(_record(), payload)
    response = build_workflow_pack_run_accepted_output(
        run_id="wfr-accepted-001", caller_tenant_id=TENANT
    )
    assert response.talking_points[0].evidence_refs == []


def _validation_evidence(state: str) -> ExecutionEvidenceDescriptor:
    return ExecutionEvidenceDescriptor(
        evidence_type="output_validation",
        summary=f"Deterministic output validation returned {state}.",
        attributes={
            "validation_state": state,
            "authority": "non_authoritative_ai_output",
            "ruleset_version": "output-validation.v4",
            "failed_rule_ids": [] if state == "VALIDATED" else ["numeric_grounding"],
        },
    )


@pytest.mark.parametrize("state", ["UNVALIDATED_LOCAL_ONLY", "REJECTED", "VALIDATION_UNAVAILABLE"])
def test_output_without_a_validated_verdict_is_refused(state: str, _wired: WireCallable) -> None:
    """A review ACCEPT is human oversight, not a validation verdict.

    Without this, an UNVALIDATED_LOCAL_ONLY output could be reviewed,
    accepted, and composed into a client document with nothing marking it
    (issue #231).
    """

    _wired(_record(evidence_descriptors=[_validation_evidence(state)]), _artifact_payload())
    with pytest.raises(AcceptedOutputNotAvailableError) as excinfo:
        build_workflow_pack_run_accepted_output(run_id="wfr-accepted-001", caller_tenant_id=TENANT)
    assert _reason(excinfo) == "output_not_validated"
    assert state in excinfo.value.message


def test_a_run_predating_validation_evidence_is_refused_not_grandfathered(
    _wired: WireCallable,
) -> None:
    """The explicit decision, not an oversight.

    Runs accepted before output-validation evidence existed cannot have their
    authority established after the fact, and accepted-output feeds new client
    and advisor document generation. Authority is proven at generation time or
    it is absent; age is not evidence.
    """

    _wired(_record(evidence_descriptors=[]), _artifact_payload())
    with pytest.raises(AcceptedOutputNotAvailableError) as excinfo:
        build_workflow_pack_run_accepted_output(run_id="wfr-accepted-001", caller_tenant_id=TENANT)
    assert _reason(excinfo) == "output_not_validated"
    assert "absent" in excinfo.value.message


def test_the_refusal_precedes_reading_the_output_artifact(_wired: WireCallable) -> None:
    """Authority is settled before the content is loaded, so an unvalidated
    run cannot be published even if its artifact is intact and vice versa."""

    _wired(_record(evidence_descriptors=[_validation_evidence("REJECTED")]), None)
    with pytest.raises(AcceptedOutputNotAvailableError) as excinfo:
        build_workflow_pack_run_accepted_output(run_id="wfr-accepted-001", caller_tenant_id=TENANT)
    assert _reason(excinfo) == "output_not_validated"


def test_every_refusal_reason_is_declared_in_the_vocabulary() -> None:
    """The reason set is the published error vocabulary - each code becomes a
    LOTUS_AI_ACCEPTED_* error code - so a raised reason that is not declared
    would ship an undocumented failure mode."""

    raised = {
        module.REASON_PACK_PROJECTION_UNSUPPORTED,
        module.REASON_RUN_NOT_COMPLETED,
        module.REASON_RUN_NOT_ACCEPTED,
        module.REASON_RUN_SUPERSEDED,
        module.REASON_OUTPUT_ARTIFACT_MISSING,
        module.REASON_OUTPUT_ARTIFACT_MALFORMED,
        module.REASON_OUTPUT_ARTIFACT_INTEGRITY,
        module.REASON_OUTPUT_NOT_VALIDATED,
    }
    assert raised == set(module.ACCEPTED_OUTPUT_REASON_CODES)


def test_the_published_response_carries_the_verdict_that_made_it_publishable(
    _wired: WireCallable,
) -> None:
    """lotus-report composes this projection into a governed client document
    and cannot check a field it is not sent. Refusing to publish unvalidated
    output is the guarantee; carrying the verdict is what makes the guarantee
    checkable by the consumer rather than assumed."""

    _wired(_record(), _artifact_payload())
    response = build_workflow_pack_run_accepted_output(
        run_id="wfr-accepted-001", caller_tenant_id=TENANT
    )
    assert response.output_validation.validation_state == "VALIDATED"
    assert response.output_validation.authority == "non_authoritative_ai_output"
    assert response.output_validation.ruleset_version == "output-validation.v4"


def test_the_verdict_is_not_part_of_content_identity(_wired: WireCallable) -> None:
    """`content_hash` means "this exact narrative and context".

    Consumers hold stored hashes from immutable snapshots, so the hash basis
    must not shift when a field is added beside it. Two runs identical except
    for the ruleset version that validated them publish the same content.
    """

    _wired(_record(), _artifact_payload())
    first = build_workflow_pack_run_accepted_output(
        run_id="wfr-accepted-001", caller_tenant_id=TENANT
    )

    later_ruleset = _validation_evidence("VALIDATED")
    later_ruleset.attributes["ruleset_version"] = "output-validation.v9"
    _wired(_record(evidence_descriptors=[later_ruleset]), _artifact_payload())
    second = build_workflow_pack_run_accepted_output(
        run_id="wfr-accepted-001", caller_tenant_id=TENANT
    )

    assert second.output_validation.ruleset_version == "output-validation.v9"
    assert second.content_hash == first.content_hash


@pytest.mark.parametrize("missing", ["authority", "ruleset_version"])
def test_incomplete_validation_evidence_fails_closed(missing: str, _wired: WireCallable) -> None:
    """A verdict without its authority marking or ruleset version is not
    something a consumer can act on, so it is refused rather than published
    with a blank marking."""

    evidence = _validation_evidence("VALIDATED")
    del evidence.attributes[missing]
    _wired(_record(evidence_descriptors=[evidence]), _artifact_payload())
    with pytest.raises(AcceptedOutputNotAvailableError) as excinfo:
        build_workflow_pack_run_accepted_output(run_id="wfr-accepted-001", caller_tenant_id=TENANT)
    assert _reason(excinfo) == "output_not_validated"
    assert missing in excinfo.value.message


def test_tampered_bytes_with_original_checksum_are_refused(_wired: WireCallable) -> None:
    original = _artifact_payload()
    changed = _artifact_payload()
    changed["structured_output"]["grounded_summary"] = "A different unreviewed narrative."
    _wired(_record(), changed, recorded_payload=original)

    with pytest.raises(AcceptedOutputNotAvailableError) as excinfo:
        module.build_workflow_pack_run_accepted_output(
            run_id="wfr-accepted-001", caller_tenant_id=TENANT
        )

    assert _reason(excinfo) == module.REASON_OUTPUT_ARTIFACT_INTEGRITY


def test_artifact_without_a_recorded_checksum_is_refused(_wired: WireCallable) -> None:
    record = _record()
    stripped_refs = [
        artifact.model_copy(update={"checksum_sha256": ""}) for artifact in record.artifact_refs
    ]
    payload = _artifact_payload()
    _wired(dataclasses.replace(record, artifact_refs=stripped_refs), payload)
    # Undo the wire fixture's checksum refresh: this scenario is exactly "no
    # recorded integrity evidence".
    import app.services.workflow_pack_run_accepted_output as service_module

    class _Store:
        def get_run(self, *, run_id: str) -> Any:
            return dataclasses.replace(record, artifact_refs=stripped_refs)

        def list_events(self, *, run_id: str) -> list[Any]:
            return []

    import pytest as _pytest

    with _pytest.MonkeyPatch.context() as mp:
        mp.setattr(service_module, "get_workflow_pack_run_store", lambda: _Store())
        with pytest.raises(AcceptedOutputNotAvailableError) as excinfo:
            module.build_workflow_pack_run_accepted_output(
                run_id="wfr-accepted-001", caller_tenant_id=TENANT
            )

    assert _reason(excinfo) == module.REASON_OUTPUT_ARTIFACT_INTEGRITY
