"""Accepted-output integrity drift seams (issue #336, follow-ups to #328/#334).

Two boundaries: the WRITE side is pinned to bare-hex checksum grammar at the
contract, and the READ side has exactly one authority for run_output_summary
bytes - every consumer (accepted-output surface and projection readers)
resolves through `load_verified_summary_object`, so tampered bytes are
withheld everywhere, not just on the surface #328 repaired.
"""

from __future__ import annotations

import hashlib
import json
import logging

import pytest
from pydantic import ValidationError

from app.contracts.artifacts import ArtifactDescriptor
from app.services import workflow_pack_run_output_summary as summary_module
from app.services.artifact_payloads import persist_json_artifact
from app.services.workflow_pack_run_output_summary import (
    SummaryIntegrityMismatchError,
    load_verified_summary_object,
    load_workflow_pack_run_output_summary,
)


def _descriptor(checksum: str) -> dict[str, object]:
    return {
        "artifact_id": "artifact_test_0001",
        "domain": "workflow_pack",
        "artifact_type": "run_output_summary",
        "source_object_kind": "workflow_pack_run",
        "source_object_id": "wfr-grammar-001",
        "lifecycle_status": "runtime_generated",
        "retention_posture": "active",
        "media_type": "application/json",
        "byte_size": 2,
        "checksum_sha256": checksum,
        "storage_backend": "memory",
        "storage_reference": "memory://workflow_pack/run/wfr-grammar-001/a.json",
        "created_at": "2026-09-06T00:00:00Z",
        "created_by": "worker",
    }


def test_checksum_grammar_is_pinned_to_bare_lowercase_hex() -> None:
    """A writer adopting the platform's `sha256:<hex>` travel form would
    fail-closed the whole accepted-output surface; the contract refuses the
    drift at persistence instead."""

    bare = hashlib.sha256(b"ok").hexdigest()
    ArtifactDescriptor.model_validate(_descriptor(bare))

    for drifted in (f"sha256:{bare}", bare.upper(), bare[:63], ""):
        with pytest.raises(ValidationError):
            ArtifactDescriptor.model_validate(_descriptor(drifted))


def test_persisted_artifact_round_trips_through_the_verified_reader() -> None:
    payload = json.dumps({"pack_id": "idea_explanation.pack"}).encode("utf-8")
    descriptor = persist_json_artifact(
        domain="workflow_pack",
        artifact_type="run_output_summary",
        source_object_kind="workflow_pack_run",
        source_object_id="wfr-roundtrip-001",
        created_at="2026-09-06T00:00:00Z",
        created_by="worker",
        payload_json=payload,
    )
    loaded_descriptor, stored_object = load_verified_summary_object([descriptor])
    assert loaded_descriptor.artifact_id == descriptor.artifact_id
    assert stored_object.payload == payload


def test_tampered_summary_bytes_are_withheld_from_projections(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The read monopoly in action: the projection readers (consumer view,
    source events) resolve through the same verified reader, so tampered
    bytes degrade the projection to absent - logged, never served."""

    payload = json.dumps({"pack_id": "idea_explanation.pack"}).encode("utf-8")
    descriptor = persist_json_artifact(
        domain="workflow_pack",
        artifact_type="run_output_summary",
        source_object_kind="workflow_pack_run",
        source_object_id="wfr-tamper-001",
        created_at="2026-09-06T00:00:00Z",
        created_by="worker",
        payload_json=payload,
    )

    from app.services.artifact_store import get_artifact_object_store

    real_store = get_artifact_object_store()
    real_object = real_store.get_object(object_key=descriptor.storage_reference.partition("://")[2])
    assert real_object is not None
    tampered = type(real_object)(
        object_key=real_object.object_key,
        payload=b'{"pack_id": "idea_explanation.pack", "tampered": true}',
        content_type=real_object.content_type,
    )

    class _TamperedStore:
        def get_object(self, *, object_key: str) -> object:
            return tampered

    monkeypatch.setattr(summary_module, "get_artifact_object_store", lambda: _TamperedStore())

    with pytest.raises(SummaryIntegrityMismatchError):
        load_verified_summary_object([descriptor])
    with caplog.at_level(logging.WARNING):
        assert load_workflow_pack_run_output_summary([descriptor]) == {}
    assert any("integrity mismatch" in r.getMessage() for r in caplog.records)
