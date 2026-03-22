from app.contracts.audit import AuditRecordResponse
from app.services.audit_store import InMemoryAuditStore


def test_in_memory_audit_store_save_and_get() -> None:
    store = InMemoryAuditStore()
    record = AuditRecordResponse(
        request_id="air_test",
        task_id="explain.v1",
        caller_app="lotus-manage",
        correlation_id="corr-123",
        prompt_version="foundation.explain.v1",
        provider_mode="disabled",
        generated_at="2026-03-22T00:00:00Z",
        stubbed=True,
        context_summary="Explain rebalance outcome",
        context_keys=["status"],
        source_refs=["lotus-manage:run:reb_1"],
        result_preview="Stub execution completed.",
        structured_output={"phase": "foundation"},
    )

    store.save(record)

    assert store.get("air_test") == record
    assert store.get("air_missing") is None
