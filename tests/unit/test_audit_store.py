from app.contracts.audit import AuditRecordResponse
from app.contracts.evidence import ExecutionEvidenceBundle, ExecutionEvidenceDescriptor
from app.contracts.safety import RedactionPosture
from app.contracts.tasks import OutputLabel, TaskCategory
from app.repositories.memory_audit_repository import InMemoryAuditRepository


def test_in_memory_audit_store_save_and_get() -> None:
    store = InMemoryAuditRepository()
    record = AuditRecordResponse(
        request_id="air_test",
        task_id="explain.v1",
        category=TaskCategory.EXPLAIN,
        output_label=OutputLabel.EXPLANATION_ONLY,
        caller_app="lotus-manage",
        correlation_id="corr-123",
        prompt_version="foundation.explain.v1",
        provider_mode="disabled",
        safety_mode="documented_only",
        redaction_posture=RedactionPosture.MINIMIZATION_REQUIRED,
        enforced_safety_controls=["response_labeling", "correlation_and_audit"],
        generated_at="2026-03-22T00:00:00Z",
        stubbed=True,
        context_summary="Explain rebalance outcome",
        context_keys=["status"],
        source_refs=["lotus-manage:run:reb_1"],
        result_preview="Stub execution completed.",
        structured_output={"phase": "foundation"},
        evidence=ExecutionEvidenceBundle(
            descriptors=[
                ExecutionEvidenceDescriptor(
                    evidence_type="task_contract",
                    summary="Task contract selected.",
                    attributes={"task_id": "explain.v1"},
                )
            ]
        ),
    )

    store.save(record)

    assert store.get("air_test") == record
    assert store.get("air_missing") is None


def test_in_memory_audit_store_list_filters_and_orders_latest_first() -> None:
    store = InMemoryAuditRepository()
    first = AuditRecordResponse(
        request_id="air_old",
        task_id="explain.v1",
        category=TaskCategory.EXPLAIN,
        output_label=OutputLabel.EXPLANATION_ONLY,
        caller_app="lotus-manage",
        correlation_id="corr-old",
        prompt_version="foundation.explain.v1",
        provider_mode="disabled",
        safety_mode="documented_only",
        redaction_posture=RedactionPosture.MINIMIZATION_REQUIRED,
        enforced_safety_controls=["response_labeling", "correlation_and_audit"],
        generated_at="2026-03-22T00:00:00Z",
        stubbed=True,
        context_summary="Old record",
        context_keys=["status"],
        source_refs=[],
        result_preview="Old",
        structured_output={},
        evidence=ExecutionEvidenceBundle(
            descriptors=[
                ExecutionEvidenceDescriptor(
                    evidence_type="task_contract",
                    summary="Task contract selected.",
                    attributes={"task_id": "explain.v1"},
                )
            ]
        ),
    )
    second = first.model_copy(
        update={
            "request_id": "air_new",
            "task_id": "summarize.v1",
            "category": TaskCategory.SUMMARIZE,
            "output_label": OutputLabel.DRAFT,
            "caller_app": "lotus-advise",
            "generated_at": "2026-03-22T01:00:00Z",
        }
    )
    store.save(first)
    store.save(second)

    all_records = store.list()
    advise_records = store.list(caller_app="lotus-advise")

    assert [record.request_id for record in all_records] == ["air_new", "air_old"]
    assert [record.request_id for record in advise_records] == ["air_new"]
