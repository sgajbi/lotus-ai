"""Projector-level pins for the accepted-output projection (issue #162).

The API contract tests cover the reachable lifecycle postures end to end; these
pin the postures only a corrupted or edited ledger can produce, plus hash
determinism and sensitivity, directly against the service.
"""

from __future__ import annotations

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
        "evidence_descriptors": [],
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


WireCallable = Callable[["WorkflowPackRunRecord | None", "dict[str, Any] | bytes | None"], None]


@pytest.fixture
def _wired(monkeypatch: pytest.MonkeyPatch) -> WireCallable:
    def wire(
        record: WorkflowPackRunRecord | None,
        artifact_payload: dict[str, Any] | bytes | None,
    ) -> None:
        raw = artifact_payload
        if isinstance(raw, dict):
            raw = json.dumps(raw).encode("utf-8")
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
    monkeypatch.setattr(module, "ensure_workflow_pack_run_store_ready", lambda: None)
    monkeypatch.setattr(module, "get_workflow_pack_run_store", lambda: _StoreStub(_record()))
    monkeypatch.setattr(
        module,
        "get_artifact_object_store",
        lambda: _ObjectStoreStub(json.dumps(_artifact_payload()).encode("utf-8")),
    )
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
