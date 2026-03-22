from app.contracts.audit import AuditRecordResponse
from app.contracts.safety import RedactionPosture
from app.repositories.memory_audit_repository import InMemoryAuditRepository


def test_in_memory_audit_store_save_and_get() -> None:
    store = InMemoryAuditRepository()
    record = AuditRecordResponse(
        request_id="air_test",
        task_id="explain.v1",
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
    )

    store.save(record)

    assert store.get("air_test") == record
    assert store.get("air_missing") is None
