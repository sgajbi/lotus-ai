import pytest

from app.config import settings
from app.main import app, health_ready
from app.services.startup_policy import evaluate_startup_readiness


def test_startup_readiness_is_independent_of_local_header_identity_setting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "local_header_caller_identity_enabled", True)
    monkeypatch.setattr(settings, "startup_readiness_policy", "enforce")

    evaluation = evaluate_startup_readiness()

    assert evaluation.blocking is False
    assert evaluation.findings == []


def test_startup_readiness_warn_policy_records_non_ready_sql_store_without_blocking() -> None:
    settings.audit_store_mode = "memory"
    settings.retrieval_store_mode = "sqlalchemy"
    settings.database_url = None
    settings.startup_readiness_policy = "warn"

    evaluation = evaluate_startup_readiness()

    assert evaluation.blocking is False
    assert any("retrieval store:" in finding for finding in evaluation.findings)

    settings.retrieval_store_mode = "memory"
    settings.startup_readiness_policy = "warn"


def test_startup_readiness_enforce_policy_blocks_non_ready_sql_store() -> None:
    settings.audit_store_mode = "sqlalchemy"
    settings.retrieval_store_mode = "memory"
    settings.database_url = None
    settings.startup_readiness_policy = "enforce"

    evaluation = evaluate_startup_readiness()

    assert evaluation.blocking is True
    assert any("audit store:" in finding for finding in evaluation.findings)

    settings.audit_store_mode = "memory"
    settings.startup_readiness_policy = "warn"


def test_split_runtime_refuses_process_local_shared_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Audit F7 (issue #331): with a dedicated worker active, every store
    shared by API and worker must be durable - the worker looks up
    ADMISSION_QUEUED in a queue-event store the API wrote in its own
    process, so per-process memory is a broken topology, not a degraded
    mode. Under the enforce policy the finding blocks startup."""

    monkeypatch.setattr(settings, "async_cutover_state", "dedicated_workers_active")
    monkeypatch.setattr(settings, "startup_readiness_policy", "enforce")
    for field in (
        "workflow_pack_registry_store_mode",
        "workflow_pack_run_store_mode",
        "workflow_pack_task_flow_store_mode",
        "workflow_pack_queue_event_store_mode",
        "workflow_pack_admission_store_mode",
        "async_runtime_store_mode",
        "kill_switch_store_mode",
        "provider_operations_store_mode",
        "rate_card_store_mode",
        "model_catalogue_store_mode",
    ):
        monkeypatch.setattr(settings, field, "memory")

    evaluation = evaluate_startup_readiness()

    split_findings = [f for f in evaluation.findings if f.startswith("split runtime:")]
    assert len(split_findings) == 10
    assert evaluation.blocking is True
    assert any("queue-event" in finding for finding in split_findings)
    assert any("execution idempotency" in finding for finding in split_findings)
    # The worker's execution path also reads operator protections and
    # economics: a kill switch the executor cannot see, or a per-process
    # budget counter two processes jointly overshoot, is the same broken
    # topology with a worse risk direction (review finding on #347).
    assert any("kill-switch" in finding for finding in split_findings)
    assert any("provider-operations" in finding for finding in split_findings)


def test_split_runtime_with_durable_shared_state_raises_no_split_findings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "async_cutover_state", "dedicated_workers_active")
    for field in (
        "workflow_pack_registry_store_mode",
        "workflow_pack_run_store_mode",
        "workflow_pack_task_flow_store_mode",
        "workflow_pack_queue_event_store_mode",
        "workflow_pack_admission_store_mode",
        "async_runtime_store_mode",
        "kill_switch_store_mode",
        "provider_operations_store_mode",
        "rate_card_store_mode",
        "model_catalogue_store_mode",
    ):
        monkeypatch.setattr(settings, field, "sqlalchemy")

    evaluation = evaluate_startup_readiness()

    assert not [f for f in evaluation.findings if f.startswith("split runtime:")]


def test_single_process_runtime_accepts_memory_stores(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Memory stores reporting READY is appropriate for single-process local
    use - the split coherence check is scoped to the split topology."""

    monkeypatch.setattr(settings, "async_cutover_state", "in_process_only")
    monkeypatch.setattr(settings, "workflow_pack_queue_event_store_mode", "memory")

    evaluation = evaluate_startup_readiness()

    assert not [f for f in evaluation.findings if f.startswith("split runtime:")]


def test_health_ready_degrades_when_probe_policy_requires_it() -> None:
    settings.readiness_probe_policy = "degrade"
    app.state.startup_readiness_findings = ["retrieval store: missing tables"]
    import anyio
    from fastapi import Response

    response = Response()
    result = anyio.run(health_ready, response)

    assert response.status_code == 503
    assert result["status"] == "degraded"

    settings.readiness_probe_policy = "observe"
    app.state.startup_readiness_findings = []
