from dataclasses import replace

from pytest import MonkeyPatch

from app.contracts.tasks import (
    CallerMetadata,
    OutputLabel,
    TaskContextEnvelope,
    TaskExecutionRequest,
    TaskInputMode,
)
from app.contracts.workflow_packs import WorkflowPackRegistrationDescriptor
from app.services.workflow_pack_registry import get_workflow_pack_registration
from app.services.task_execution_context_builder import build_task_execution_context
from app.services.workflow_pack_bindings import (
    _build_execution_binding_from_spec,
    get_workflow_pack_execution_binding,
    get_resolved_workflow_pack_execution_binding,
    resolve_workflow_pack_execution_binding_for_task,
    validate_workflow_pack_execution_bindings,
)
from app.services.workflow_pack_phase1_specs import ADVISOR_BRIEF_V1_SPEC
from tests.support.workflow_pack_fixtures import outcome_review_narrative_payload
from tests.support.workflow_pack_fixtures import proof_pack_pm_memo_payload


def test_get_workflow_pack_execution_binding_returns_phase1_binding() -> None:
    binding = get_workflow_pack_execution_binding(pack_id="advisor_brief.pack", version="v1")

    assert binding is not None
    assert binding.task_id == "explain.v1"
    assert binding.default_workflow_surface == "advisor-brief-workspace"


def test_get_workflow_pack_execution_binding_returns_twr_inspection_support_brief_binding() -> None:
    binding = get_workflow_pack_execution_binding(
        pack_id="twr_inspection_support_brief.pack",
        version="v1",
    )

    assert binding is not None
    assert binding.task_id == "explain.v1"
    assert binding.default_workflow_surface == "twr-supportability-inspection"


def test_get_workflow_pack_execution_binding_returns_outcome_review_narrative_binding() -> None:
    binding = get_workflow_pack_execution_binding(
        pack_id="outcome_review_narrative.pack",
        version="v1",
    )

    assert binding is not None
    assert binding.task_id == "explain.v1"
    assert binding.default_workflow_surface == "dpm-outcome-review-ai-evidence"
    assert binding.validate_task_request_payload(payload=outcome_review_narrative_payload())


def test_get_workflow_pack_execution_binding_returns_proof_pack_pm_memo_binding() -> None:
    binding = get_workflow_pack_execution_binding(
        pack_id="dpm_pm_memo.pack",
        version="v1",
    )

    assert binding is not None
    assert binding.task_id == "explain.v1"
    assert binding.default_workflow_surface == "dpm-proof-pack-ai-evidence"
    assert binding.validate_task_request_payload(payload=proof_pack_pm_memo_payload())


def test_workflow_pack_execution_binding_spec_requires_task_and_surface() -> None:
    missing_task_spec = replace(ADVISOR_BRIEF_V1_SPEC, execution_task_id=None)
    try:
        _build_execution_binding_from_spec(missing_task_spec)
    except ValueError as exc:
        assert "missing execution_task_id" in str(exc)
    else:
        raise AssertionError("expected missing execution task id to block binding construction")

    missing_surface_spec = replace(ADVISOR_BRIEF_V1_SPEC, default_workflow_surface=None)
    try:
        _build_execution_binding_from_spec(missing_surface_spec)
    except ValueError as exc:
        assert "missing default_workflow_surface" in str(exc)
    else:
        raise AssertionError("expected missing default surface to block binding construction")


def test_get_resolved_workflow_pack_execution_binding_returns_binding_and_registration() -> None:
    resolved_binding = get_resolved_workflow_pack_execution_binding(
        pack_id="advisor_brief.pack",
        version="v1",
    )

    assert resolved_binding is not None
    assert resolved_binding.binding.pack_id == "advisor_brief.pack"
    assert resolved_binding.registration.pack_id == "advisor_brief.pack"
    assert resolved_binding.registration.version == "v1"


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
            expected_output_label=OutputLabel.EXPLANATION_ONLY,
        )
    )

    resolved_binding = resolve_workflow_pack_execution_binding_for_task(context=context)

    assert resolved_binding is not None
    assert resolved_binding.binding.pack_id == "advisor_brief.pack"
    assert resolved_binding.binding.version == "v1"
    assert resolved_binding.registration.pack_id == "advisor_brief.pack"


def test_resolve_workflow_pack_execution_binding_for_task_uses_registration_caller_scope(
    monkeypatch: MonkeyPatch,
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
            expected_output_label=OutputLabel.EXPLANATION_ONLY,
        )
    )

    registration = get_workflow_pack_registration(pack_id="advisor_brief.pack", version="v1")
    assert registration is not None
    original_get_registration = get_workflow_pack_registration

    def _registration_with_workbench_scope(
        *,
        pack_id: str,
        version: str,
    ) -> WorkflowPackRegistrationDescriptor:
        if pack_id == "advisor_brief.pack" and version == "v1":
            return registration.model_copy(update={"supported_callers": ["lotus-workbench"]})
        fallback = original_get_registration(pack_id=pack_id, version=version)
        assert fallback is not None
        return fallback

    monkeypatch.setattr(
        "app.services.workflow_pack_bindings.get_workflow_pack_registration",
        _registration_with_workbench_scope,
    )

    resolved_binding = resolve_workflow_pack_execution_binding_for_task(context=context)

    assert resolved_binding is None


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
            expected_output_label=OutputLabel.EXPLANATION_ONLY,
        )
    )

    resolved_binding = resolve_workflow_pack_execution_binding_for_task(context=context)

    assert resolved_binding is None


def test_validate_workflow_pack_execution_bindings_rejects_default_surface_outside_registration_scope(
    monkeypatch: MonkeyPatch,
) -> None:
    registration = get_workflow_pack_registration(pack_id="advisor_brief.pack", version="v1")
    assert registration is not None
    original_get_registration = get_workflow_pack_registration

    def _registration_with_narrow_surface_scope(
        *,
        pack_id: str,
        version: str,
    ) -> WorkflowPackRegistrationDescriptor:
        if pack_id == "advisor_brief.pack" and version == "v1":
            return registration.model_copy(update={"surface_scope": ["advisor-brief-panel"]})
        fallback = original_get_registration(pack_id=pack_id, version=version)
        assert fallback is not None
        return fallback

    monkeypatch.setattr(
        "app.services.workflow_pack_bindings.get_workflow_pack_registration",
        _registration_with_narrow_surface_scope,
    )

    try:
        validate_workflow_pack_execution_bindings()
    except ValueError as exc:
        assert "default surface is outside registration scope" in str(exc)
    else:
        raise AssertionError("expected binding validation to reject scope drift")
