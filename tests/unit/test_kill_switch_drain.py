"""Drain semantics for kill switches (issue #177, S3)."""

from pathlib import Path

from fastapi import HTTPException
from pytest import MonkeyPatch, raises

from app.config import settings
from app.contracts.kill_switches import (
    KillSwitchActivationRequest,
    KillSwitchScope,
    KillSwitchSemantics,
)
from app.providers.base import ProviderExecutionError
from app.services.kill_switch_control import (
    activate_kill_switch,
    drain_completion_permit,
    enforce_kill_switch_intake,
    enforce_kill_switches,
)
from app.services.kill_switch_store import get_kill_switch_repository
from tests.support.migration_runner import upgrade_database_to_head
from tests.unit.test_provider_gateway import _request


def _activate(
    scope: KillSwitchScope,
    *,
    semantics: KillSwitchSemantics,
    target: str | None,
) -> str:
    response = activate_kill_switch(
        KillSwitchActivationRequest(
            caller_app="lotus-platform",
            scope=scope,
            semantics=semantics,
            target=target,
            reason="Drain-semantics test activation.",
            requested_by="alice@lotus.test",
            approved_by="bob@lotus.test",
        )
    )
    return response.activation.switch_id


def _use_durable_store(tmp_path: Path) -> None:
    settings.kill_switch_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'kill-switch-drain.db'}"
    upgrade_database_to_head(settings.database_url)


def test_drain_refuses_sync_execution_but_permits_claimed_completion(
    tmp_path: Path,
) -> None:
    _use_durable_store(tmp_path)
    _activate(KillSwitchScope.TASK, semantics=KillSwitchSemantics.DRAIN, target="explain.v1")

    # Sync requests are never drained: they refuse immediately.
    with raises(ProviderExecutionError) as exc_info:
        enforce_kill_switches(_request())
    assert exc_info.value.category.value == "KILL_SWITCH_ACTIVE"

    # Already-claimed async work completes under the drain permit.
    with drain_completion_permit():
        enforce_kill_switches(_request())


def test_hard_kill_refuses_even_under_the_completion_permit(tmp_path: Path) -> None:
    _use_durable_store(tmp_path)
    _activate(KillSwitchScope.TASK, semantics=KillSwitchSemantics.HARD_KILL, target="explain.v1")

    with drain_completion_permit():
        with raises(ProviderExecutionError):
            enforce_kill_switches(_request())


def test_intake_is_refused_under_both_semantics(tmp_path: Path) -> None:
    _use_durable_store(tmp_path)
    _activate(KillSwitchScope.TENANT, semantics=KillSwitchSemantics.DRAIN, target="tenant-sg-001")

    with raises(HTTPException) as exc_info:
        enforce_kill_switch_intake(
            task_id="explain.v1", tenant_id="tenant-sg-001", caller_app="lotus-manage"
        )
    assert exc_info.value.status_code == 503
    assert "KILL_SWITCH_ACTIVE" in str(exc_info.value.detail)
    assert "DRAIN" in str(exc_info.value.detail)

    # Out-of-scope intake proceeds.
    enforce_kill_switch_intake(
        task_id="explain.v1", tenant_id="tenant-us-002", caller_app="lotus-manage"
    )


def test_semantics_round_trip_through_the_durable_store(tmp_path: Path) -> None:
    _use_durable_store(tmp_path)
    switch_id = _activate(
        KillSwitchScope.CALLER_APP, semantics=KillSwitchSemantics.DRAIN, target="lotus-manage"
    )

    stored = get_kill_switch_repository().get_activation(switch_id)
    assert stored is not None
    assert stored.semantics is KillSwitchSemantics.DRAIN

    # Default remains hard kill - the safe interpretation.
    default_id = _activate(
        KillSwitchScope.PROVIDER, semantics=KillSwitchSemantics.HARD_KILL, target="text.openai"
    )
    default_stored = get_kill_switch_repository().get_activation(default_id)
    assert default_stored is not None
    assert default_stored.semantics is KillSwitchSemantics.HARD_KILL


def test_async_submission_intake_checks_kill_switches(monkeypatch: MonkeyPatch) -> None:
    """The workflow-pack async submission preflight calls the intake check."""

    calls: list[tuple[str, str | None, str]] = []

    def _spy(*, task_id: str, tenant_id: str | None, caller_app: str) -> None:
        calls.append((task_id, tenant_id, caller_app))

    monkeypatch.setattr(
        "app.services.workflow_pack_async_execution.enforce_kill_switch_intake",
        _spy,
    )
    from app.services.workflow_pack_async_execution import (
        _preflight_workflow_pack_execution_request,
    )
    from app.contracts.workflow_packs import WorkflowPackExecutionRequest
    from app.contracts.tasks import (
        CallerMetadata,
        TaskContextEnvelope,
        TaskExecutionRequest,
        TaskInputMode,
    )

    request = WorkflowPackExecutionRequest(
        pack_id="advisor_brief.pack",
        version="v1",
        environment="PRODUCTION",
        caller_identity_class="INTERNAL_SERVICE",
        task_request=TaskExecutionRequest(
            task_id="explain.v1",
            input_mode=TaskInputMode.STRUCTURED_CONTEXT,
            caller=CallerMetadata(
                caller_app="lotus-gateway",
                correlation_id="corr-drain-intake",
                tenant_id="tenant-sg-001",
            ),
            context=TaskContextEnvelope(
                summary="Drain intake probe",
                payload={"status": "OK"},
                source_refs=[],
            ),
        ),
    )
    try:
        _preflight_workflow_pack_execution_request(request=request)
    except HTTPException:
        pass
    assert calls == [("explain.v1", "tenant-sg-001", "lotus-gateway")]
