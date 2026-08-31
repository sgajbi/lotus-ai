"""Service-level pins for the latest-accepted lookup (issue #183).

The API contract tests prove the reachable postures end to end; these pin the
determinism rules and the fail-closed postures only a corrupted or edited
ledger can produce: accepting-review ordering with ties, filters that never
wildcard unasserted context, scan saturation, unresolvable candidates, and
tenant isolation without an existence oracle.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.contracts.artifacts import (
    ArtifactDescriptor,
    ArtifactLifecycleStatus,
    ArtifactStorageBackend,
)
from app.contracts.workflow_pack_runs import WorkflowPackRunEventType
from app.repositories.workflow_pack_run_repository import (
    WorkflowPackRunEventRecord,
    WorkflowPackRunRecord,
)
from app.services import workflow_pack_run_accepted_latest as module
from app.services import workflow_pack_run_accepted_output as output_module
from app.services.workflow_pack_run_accepted_latest import (
    AcceptedLatestNotFoundError,
    build_workflow_pack_run_accepted_latest,
)
from app.services.workflow_pack_run_accepted_output import AcceptedOutputNotAvailableError

TENANT = "tenant-sg-001"
PORTFOLIO = "PB_SG_GLOBAL_BAL_001"


class _Store:
    def __init__(self) -> None:
        self.runs: dict[str, WorkflowPackRunRecord] = {}
        self.events: dict[str, list[WorkflowPackRunEventRecord]] = {}

    def query_runs(self, *, limit: int, **filters: Any) -> list[WorkflowPackRunRecord]:
        records = [
            record
            for record in self.runs.values()
            if all(
                value is None or getattr(record, field) == value for field, value in filters.items()
            )
        ]
        records.sort(key=lambda record: record.created_at, reverse=True)
        return records[: max(limit, 0)]

    def get_run(self, *, run_id: str) -> WorkflowPackRunRecord | None:
        return self.runs.get(run_id)

    def list_events(self, *, run_id: str) -> list[WorkflowPackRunEventRecord]:
        return sorted(self.events.get(run_id, []), key=lambda event: event.recorded_at)


class _ObjectStore:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def get_object(self, *, object_key: str) -> Any:
        payload = self.objects.get(object_key)
        if payload is None:
            return None

        class _Stored:
            payload: bytes

        stored = _Stored()
        stored.payload = payload
        return stored


@pytest.fixture
def _stores(monkeypatch: pytest.MonkeyPatch) -> tuple[_Store, _ObjectStore]:
    store = _Store()
    objects = _ObjectStore()
    for target in (module, output_module):
        monkeypatch.setattr(target, "ensure_workflow_pack_run_store_ready", lambda: None)
        monkeypatch.setattr(target, "get_workflow_pack_run_store", lambda: store)
    monkeypatch.setattr(output_module, "get_artifact_object_store", lambda: objects)
    return store, objects


def _seed_run(
    stores: tuple[_Store, _ObjectStore],
    *,
    run_id: str,
    created_at: str,
    reviewed_at: str | None,
    portfolio_id: str = PORTFOLIO,
    as_of_date: str | None = None,
    reporting_currency: str | None = None,
    tenant_id: str | None = TENANT,
    pack_version: str = "v1",
    superseded_by_run_id: str | None = None,
    artifact_intact: bool = True,
) -> None:
    store, objects = stores
    store.runs[run_id] = WorkflowPackRunRecord(
        run_id=run_id,
        pack_id="advisor_brief.pack",
        pack_family="advisor_brief",
        pack_version=pack_version,
        registration_ref=f"advisor_brief.pack@{pack_version}",
        task_id="explain.v1",
        request_id=f"req-{run_id}",
        caller_app="lotus-gateway",
        correlation_id=f"corr-{run_id}",
        tenant_id=tenant_id,
        workflow_surface="advisor-brief-workspace",
        workflow_authority_owner="lotus-gateway",
        runtime_state="COMPLETED",
        review_state="ACCEPTED",
        review_required=True,
        provider_mode="stub",
        stubbed=True,
        output_preview="preview",
        structured_output_keys=["grounded_summary"],
        evidence_descriptors=[],
        artifact_refs=[
            ArtifactDescriptor(
                artifact_id=f"art-{run_id}",
                domain="workflow_pack",
                artifact_type="run_output_summary",
                source_object_kind="workflow_pack_run",
                source_object_id=run_id,
                lifecycle_status=ArtifactLifecycleStatus.RUNTIME_GENERATED,
                retention_posture="retained_for_review",
                media_type="application/json",
                byte_size=512,
                checksum_sha256="0" * 64,
                storage_backend=ArtifactStorageBackend.MEMORY,
                storage_reference=f"artifact://runs/{run_id}.json",
                created_at=created_at,
                created_by="lotus-ai.workflow-pack-run-ledger",
            )
        ],
        supersedes_run_id=None,
        superseded_by_run_id=superseded_by_run_id,
        created_at=created_at,
        completed_at=created_at,
        last_updated_at=created_at,
    )
    if reviewed_at is not None:
        store.events.setdefault(run_id, []).append(
            WorkflowPackRunEventRecord(
                event_id=f"evt-{run_id}",
                run_id=run_id,
                event_type=WorkflowPackRunEventType.REVIEW_STATE_UPDATED.value,
                runtime_state="COMPLETED",
                review_state="ACCEPTED",
                actor="review:banker.sg.301",
                message="Accepted.",
                recorded_at=reviewed_at,
            )
        )
    if artifact_intact:
        structured: dict[str, Any] = {
            "advisor_brief_status": "complete",
            "coverage_state": "complete",
            "portfolio_id": portfolio_id,
            "period": "YTD",
            "grounded_summary": f"Summary for {run_id}.",
            "talking_points": [],
            "risks_and_exceptions": [],
        }
        if as_of_date is not None:
            structured["as_of_date"] = as_of_date
        if reporting_currency is not None:
            structured["reporting_currency"] = reporting_currency
        objects.objects[f"runs/{run_id}.json"] = json.dumps(
            {
                "run_id": run_id,
                "pack_id": "advisor_brief.pack",
                "source_refs": [],
                "evidence_types": [],
                "structured_output": structured,
            }
        ).encode("utf-8")


def _lookup(**overrides: Any) -> Any:
    params: dict[str, Any] = {
        "pack_family": "advisor_brief",
        "portfolio_id": PORTFOLIO,
        "caller_tenant_id": TENANT,
    }
    params.update(overrides)
    return build_workflow_pack_run_accepted_latest(**params)


def test_unsupported_pack_family_is_refused(_stores: tuple[_Store, _ObjectStore]) -> None:
    with pytest.raises(AcceptedOutputNotAvailableError) as excinfo:
        _lookup(pack_family="fund_teaser")
    assert excinfo.value.reason_code == "pack_projection_unsupported"


def test_latest_is_ordered_by_accepting_review_not_creation(
    _stores: tuple[_Store, _ObjectStore],
) -> None:
    """The run created FIRST but accepted LAST is the latest accepted run."""

    _seed_run(
        _stores,
        run_id="wfr-early",
        created_at="2026-08-30T08:00:00Z",
        reviewed_at="2026-08-30T12:00:00Z",
    )
    _seed_run(
        _stores,
        run_id="wfr-late",
        created_at="2026-08-30T09:00:00Z",
        reviewed_at="2026-08-30T10:00:00Z",
    )

    envelope = _lookup()

    assert envelope.run_id == "wfr-early"
    assert envelope.review.reviewed_at == "2026-08-30T12:00:00Z"
    assert envelope.review.reviewed_by == "banker.sg.301"


def test_review_time_ties_break_on_run_id_descending(
    _stores: tuple[_Store, _ObjectStore],
) -> None:
    _seed_run(
        _stores,
        run_id="wfr-a",
        created_at="2026-08-30T08:00:00Z",
        reviewed_at="2026-08-30T10:00:00Z",
    )
    _seed_run(
        _stores,
        run_id="wfr-b",
        created_at="2026-08-30T08:30:00Z",
        reviewed_at="2026-08-30T10:00:00Z",
    )

    assert _lookup().run_id == "wfr-b"


def test_unknown_portfolio_and_unknown_tenant_share_no_accepted_run(
    _stores: tuple[_Store, _ObjectStore],
) -> None:
    _seed_run(
        _stores,
        run_id="wfr-001",
        created_at="2026-08-30T08:00:00Z",
        reviewed_at="2026-08-30T09:00:00Z",
    )

    with pytest.raises(AcceptedLatestNotFoundError) as unknown_portfolio:
        _lookup(portfolio_id="PB_UK_UNKNOWN_999")
    with pytest.raises(AcceptedLatestNotFoundError) as unknown_tenant:
        _lookup(caller_tenant_id="tenant-uk-999")

    assert unknown_portfolio.value.reason_code == "no_accepted_run"
    assert unknown_tenant.value.reason_code == "no_accepted_run"


def test_context_filters_distinguish_no_context_match(
    _stores: tuple[_Store, _ObjectStore],
) -> None:
    _seed_run(
        _stores,
        run_id="wfr-001",
        created_at="2026-08-30T08:00:00Z",
        reviewed_at="2026-08-30T09:00:00Z",
        as_of_date="2026-04-22",
    )

    with pytest.raises(AcceptedLatestNotFoundError) as excinfo:
        _lookup(as_of_date="2026-05-31")
    assert excinfo.value.reason_code == "no_context_match"

    assert _lookup(as_of_date="2026-04-22").run_id == "wfr-001"


def test_unasserted_context_never_wildcard_matches_a_filter(
    _stores: tuple[_Store, _ObjectStore],
) -> None:
    _seed_run(
        _stores,
        run_id="wfr-001",
        created_at="2026-08-30T08:00:00Z",
        reviewed_at="2026-08-30T09:00:00Z",
    )

    for filters in (
        {"as_of_date": "2026-04-22"},
        {"reporting_currency": "USD"},
    ):
        with pytest.raises(AcceptedLatestNotFoundError) as excinfo:
            _lookup(**filters)
        assert excinfo.value.reason_code == "no_context_match"


def test_filters_select_an_older_matching_accepted_run(
    _stores: tuple[_Store, _ObjectStore],
) -> None:
    """A newer accepted run that fails the filters yields to the newest run
    that asserts the requested context - never to a wildcard."""

    _seed_run(
        _stores,
        run_id="wfr-old-usd",
        created_at="2026-08-30T08:00:00Z",
        reviewed_at="2026-08-30T09:00:00Z",
        reporting_currency="USD",
    )
    _seed_run(
        _stores,
        run_id="wfr-new-sgd",
        created_at="2026-08-30T10:00:00Z",
        reviewed_at="2026-08-30T11:00:00Z",
        reporting_currency="SGD",
    )

    envelope = _lookup(reporting_currency="USD")

    assert envelope.run_id == "wfr-old-usd"
    assert envelope.context.reporting_currency == "USD"


def test_superseded_accepted_runs_are_not_candidates(
    _stores: tuple[_Store, _ObjectStore],
) -> None:
    _seed_run(
        _stores,
        run_id="wfr-001",
        created_at="2026-08-30T08:00:00Z",
        reviewed_at="2026-08-30T09:00:00Z",
        superseded_by_run_id="wfr-002",
    )

    with pytest.raises(AcceptedLatestNotFoundError) as excinfo:
        _lookup()
    assert excinfo.value.reason_code == "no_accepted_run"


def test_scan_saturation_fails_closed(
    _stores: tuple[_Store, _ObjectStore], monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_run(
        _stores,
        run_id="wfr-001",
        created_at="2026-08-30T08:00:00Z",
        reviewed_at="2026-08-30T09:00:00Z",
    )
    _seed_run(
        _stores,
        run_id="wfr-002",
        created_at="2026-08-30T08:30:00Z",
        reviewed_at="2026-08-30T09:30:00Z",
    )
    monkeypatch.setattr(module, "_CANDIDATE_SCAN_LIMIT", 2)

    with pytest.raises(AcceptedOutputNotAvailableError) as excinfo:
        _lookup()
    assert excinfo.value.reason_code == "lookup_scan_saturated"


def test_accepted_candidate_without_review_event_fails_the_lookup_closed(
    _stores: tuple[_Store, _ObjectStore],
) -> None:
    """An ACCEPTED run with no review transition has an unknowable position in
    the latest-accepted order - even when an intact candidate also exists."""

    _seed_run(
        _stores,
        run_id="wfr-intact",
        created_at="2026-08-30T08:00:00Z",
        reviewed_at="2026-08-30T09:00:00Z",
    )
    _seed_run(_stores, run_id="wfr-no-review", created_at="2026-08-30T08:30:00Z", reviewed_at=None)

    with pytest.raises(AcceptedOutputNotAvailableError) as excinfo:
        _lookup()
    assert excinfo.value.reason_code == "output_artifact_malformed"


def test_unresolvable_newer_candidate_fails_the_lookup_closed(
    _stores: tuple[_Store, _ObjectStore],
) -> None:
    """A corrupt candidate NEWER than an intact match could itself be the
    answer; the lookup refuses rather than serving possibly-stale content."""

    _seed_run(
        _stores,
        run_id="wfr-intact",
        created_at="2026-08-30T08:00:00Z",
        reviewed_at="2026-08-30T09:00:00Z",
    )
    _seed_run(
        _stores,
        run_id="wfr-corrupt",
        created_at="2026-08-30T08:30:00Z",
        reviewed_at="2026-08-30T10:00:00Z",
        artifact_intact=False,
    )

    with pytest.raises(AcceptedOutputNotAvailableError) as excinfo:
        _lookup()
    assert excinfo.value.reason_code == "output_artifact_missing"


def test_envelope_is_identity_only_and_pins_the_projection_hash(
    _stores: tuple[_Store, _ObjectStore],
) -> None:
    _seed_run(
        _stores,
        run_id="wfr-001",
        created_at="2026-08-30T08:00:00Z",
        reviewed_at="2026-08-30T09:00:00Z",
        as_of_date="2026-04-22",
        reporting_currency="USD",
    )

    envelope = _lookup()
    projection = output_module.build_workflow_pack_run_accepted_output(
        run_id="wfr-001", caller_tenant_id=TENANT
    )

    assert envelope.schema_id == "lotus-ai.workflow_pack_run.accepted_latest.v1"
    assert envelope.accepted_output_schema_id == projection.schema_id
    assert envelope.content_hash == projection.content_hash
    assert envelope.content_hash_algorithm == "sha256"
    assert envelope.context == projection.context
    published_fields = set(envelope.model_dump())
    assert published_fields == {
        "schema_id",
        "service",
        "version",
        "run_id",
        "pack_id",
        "pack_family",
        "pack_version",
        "tenant_id",
        "workflow_authority_owner",
        "context",
        "review",
        "accepted_output_schema_id",
        "content_hash",
        "content_hash_algorithm",
        "notes",
    }
