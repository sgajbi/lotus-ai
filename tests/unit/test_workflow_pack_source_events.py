from __future__ import annotations

import app.services.workflow_pack_source_events as source_events
from app.contracts.workflow_pack_runs import WorkflowPackRunSupportabilityStatus
from app.repositories.memory_workflow_pack_run_repository import InMemoryWorkflowPackRunRepository
from app.repositories.workflow_pack_run_repository import (
    WorkflowPackRunEventRecord,
    WorkflowPackRunRecord,
)


class _NoBroadListWorkflowPackRunRepository(InMemoryWorkflowPackRunRepository):
    def __init__(self) -> None:
        super().__init__()
        self.query_count = 0

    def list_runs(self, *, limit: int | None = None) -> list[WorkflowPackRunRecord]:
        raise AssertionError("source-event catalog must query filtered runs at repository boundary")

    def query_runs(
        self,
        *,
        registration_ref: str | None = None,
        pack_id: str | None = None,
        caller_app: str | None = None,
        tenant_id: str | None = None,
        workflow_surface: str | None = None,
        runtime_state: str | None = None,
        review_state: str | None = None,
        workflow_authority_owner: str | None = None,
        limit: int,
    ) -> list[WorkflowPackRunRecord]:
        self.query_count += 1
        return super().query_runs(
            registration_ref=registration_ref,
            pack_id=pack_id,
            caller_app=caller_app,
            tenant_id=tenant_id,
            workflow_surface=workflow_surface,
            runtime_state=runtime_state,
            review_state=review_state,
            workflow_authority_owner=workflow_authority_owner,
            limit=limit,
        )


def _run_record() -> WorkflowPackRunRecord:
    return WorkflowPackRunRecord(
        run_id="run-source-events-001",
        pack_id="advisor_brief.pack",
        pack_family="advisor_brief",
        pack_version="v1",
        registration_ref="advisor_brief.pack@v1",
        task_id="explain.v1",
        request_id="req-source-events-001",
        caller_app="lotus-gateway",
        correlation_id="corr-source-events-001",
        tenant_id="tenant-sg-001",
        workflow_surface="advisor-brief-workspace",
        workflow_authority_owner="lotus-gateway",
        runtime_state="COMPLETED",
        review_state="AWAITING_REVIEW",
        review_required=True,
        provider_mode="catalog_only",
        stubbed=True,
        output_preview="preview",
        structured_output_keys=[],
        evidence_descriptors=[],
        artifact_refs=[],
        supersedes_run_id=None,
        superseded_by_run_id=None,
        created_at="2026-04-19T10:00:00Z",
        completed_at="2026-04-19T10:00:00Z",
        last_updated_at="2026-04-19T10:00:00Z",
    )


def test_source_event_catalog_uses_filtered_run_query_without_broad_scan(
    monkeypatch,
) -> None:
    repository = _NoBroadListWorkflowPackRunRepository()
    repository.save_run(_run_record())
    repository.save_event(
        WorkflowPackRunEventRecord(
            event_id="event-source-events-001",
            run_id="run-source-events-001",
            event_type="RUN_RECORDED",
            runtime_state="COMPLETED",
            review_state="AWAITING_REVIEW",
            actor="lotus-ai.workflow-pack-run-ledger",
            message="Workflow-pack run recorded.",
            recorded_at="2026-04-19T10:00:00Z",
        )
    )
    monkeypatch.setattr(source_events, "get_workflow_pack_run_store", lambda: repository)

    catalog = source_events.build_workflow_pack_source_event_catalog(
        pack_id="advisor_brief.pack",
        caller_app="lotus-gateway",
        tenant_id="tenant-sg-001",
        workflow_surface="advisor-brief-workspace",
        supportability_status=WorkflowPackRunSupportabilityStatus.ACTION_REQUIRED,
        limit=10,
    )

    assert repository.query_count == 1
    assert catalog.filters_applied["source_run_limit"] == 100
    assert catalog.filters_applied["source_run_count"] == 1
    assert [event.run_id for event in catalog.events] == ["run-source-events-001"]
