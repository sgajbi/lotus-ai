from app.contracts.tasks import (
    CallerMetadata,
    TaskContextEnvelope,
    TaskExecutionRequest,
    TaskInputMode,
)
from app.services.workflow_pack_registry import get_workflow_pack_registration
from app.services.task_execution_context_builder import build_task_execution_context
from app.services.workflow_pack_bindings import (
    get_workflow_pack_execution_binding,
    resolve_workflow_pack_execution_binding_for_task,
    validate_workflow_pack_execution_bindings,
)


def test_get_workflow_pack_execution_binding_returns_phase1_binding() -> None:
    binding = get_workflow_pack_execution_binding(pack_id="advisor_brief.pack", version="v1")

    assert binding is not None
    assert binding.task_id == "explain.v1"
    assert binding.default_workflow_surface == "advisor-brief-workspace"


def test_validate_workflow_pack_execution_bindings_accepts_registered_scope() -> None:
    validate_workflow_pack_execution_bindings()


def test_resolve_workflow_pack_execution_binding_for_task_matches_phase1_payload() -> None:
    context = build_task_execution_context(
        TaskExecutionRequest(
            task_id="explain.v1",
            input_mode=TaskInputMode.STRUCTURED_CONTEXT,
            caller=CallerMetadata(
                caller_app="lotus-gateway",
                correlation_id="corr-binding-001",
            ),
            context=TaskContextEnvelope(
                summary="Draft advisor brief from source performance facts.",
                payload={
                    "portfolio": {"portfolio_id": "PB_SG_GLOBAL_BAL_001"},
                    "period": {"period": "YTD"},
                    "performance": {
                        "portfolio_return_pct": 1.25,
                        "benchmark_return_pct": 7.93,
                        "active_return_pct": -6.68,
                    },
                    "supportability": [{"key": "portfolio_context", "value": "ready"}],
                },
                source_refs=["lotus-gateway:performance-summary:YTD"],
            ),
            expected_output_label="EXPLANATION_ONLY",
        )
    )

    binding = resolve_workflow_pack_execution_binding_for_task(context=context)

    assert binding is not None
    assert binding.pack_id == "advisor_brief.pack"
    assert binding.version == "v1"


def test_resolve_workflow_pack_execution_binding_for_task_uses_registration_caller_scope(
    monkeypatch,
) -> None:
    context = build_task_execution_context(
        TaskExecutionRequest(
            task_id="explain.v1",
            input_mode=TaskInputMode.STRUCTURED_CONTEXT,
            caller=CallerMetadata(
                caller_app="lotus-gateway",
                correlation_id="corr-binding-registration-scope-001",
            ),
            context=TaskContextEnvelope(
                summary="Draft advisor brief from source performance facts.",
                payload={
                    "portfolio": {"portfolio_id": "PB_SG_GLOBAL_BAL_001"},
                    "period": {"period": "YTD"},
                    "performance": {
                        "portfolio_return_pct": 1.25,
                        "benchmark_return_pct": 7.93,
                        "active_return_pct": -6.68,
                    },
                    "supportability": [{"key": "portfolio_context", "value": "ready"}],
                },
                source_refs=["lotus-gateway:performance-summary:YTD"],
            ),
            expected_output_label="EXPLANATION_ONLY",
        )
    )

    registration = get_workflow_pack_registration(pack_id="advisor_brief.pack", version="v1")
    assert registration is not None
    monkeypatch.setattr(
        "app.services.workflow_pack_bindings.get_workflow_pack_registration",
        lambda *, pack_id, version: registration.model_copy(
            update={"supported_callers": ["lotus-workbench"]}
        ),
    )

    binding = resolve_workflow_pack_execution_binding_for_task(context=context)

    assert binding is None


def test_resolve_workflow_pack_execution_binding_for_task_rejects_nonmatching_payload() -> None:
    context = build_task_execution_context(
        TaskExecutionRequest(
            task_id="explain.v1",
            input_mode=TaskInputMode.STRUCTURED_CONTEXT,
            caller=CallerMetadata(
                caller_app="lotus-gateway",
                correlation_id="corr-binding-002",
            ),
            context=TaskContextEnvelope(
                summary="Generic explanation payload.",
                payload={"portfolio": {"portfolio_id": "PB_SG_GLOBAL_BAL_001"}},
                source_refs=["lotus-gateway:performance-summary:YTD"],
            ),
            expected_output_label="EXPLANATION_ONLY",
        )
    )

    binding = resolve_workflow_pack_execution_binding_for_task(context=context)

    assert binding is None


def test_validate_workflow_pack_execution_bindings_rejects_default_surface_outside_registration_scope(
    monkeypatch,
) -> None:
    registration = get_workflow_pack_registration(pack_id="advisor_brief.pack", version="v1")
    assert registration is not None

    monkeypatch.setattr(
        "app.services.workflow_pack_bindings.get_workflow_pack_registration",
        lambda *, pack_id, version: registration.model_copy(
            update={"surface_scope": ["advisor-brief-panel"]}
        ),
    )

    try:
        validate_workflow_pack_execution_bindings()
    except ValueError as exc:
        assert "default surface is outside registration scope" in str(exc)
    else:
        raise AssertionError("expected binding validation to reject scope drift")
