from __future__ import annotations

from app.contracts.tasks import (
    CallerMetadata,
    OutputLabel,
    TaskContextEnvelope,
    TaskExecutionRequest,
    TaskInputMode,
)


def advisor_brief_payload(
    *,
    portfolio_return_pct: float = 1.25,
    benchmark_return_pct: float = 7.93,
    active_return_pct: float = -6.68,
) -> dict[str, object]:
    return {
        "portfolio": {"portfolio_id": "PB_SG_GLOBAL_BAL_001"},
        "period": {"period": "YTD"},
        "performance": {
            "portfolio_return_pct": portfolio_return_pct,
            "benchmark_return_pct": benchmark_return_pct,
            "active_return_pct": active_return_pct,
        },
        "supportability": [{"key": "portfolio_context", "value": "ready"}],
    }


def advisor_brief_task_execution_request(
    *,
    correlation_id: str,
    task_id: str = "explain.v1",
    caller_app: str = "lotus-gateway",
    summary: str = "Draft advisor brief from source performance facts.",
    source_refs: list[str] | None = None,
    portfolio_return_pct: float = 1.25,
    benchmark_return_pct: float = 7.93,
    active_return_pct: float = -6.68,
) -> TaskExecutionRequest:
    return TaskExecutionRequest(
        task_id=task_id,
        input_mode=TaskInputMode.STRUCTURED_CONTEXT,
        caller=CallerMetadata(
            caller_app=caller_app,
            correlation_id=correlation_id,
        ),
        context=TaskContextEnvelope(
            summary=summary,
            payload=advisor_brief_payload(
                portfolio_return_pct=portfolio_return_pct,
                benchmark_return_pct=benchmark_return_pct,
                active_return_pct=active_return_pct,
            ),
            source_refs=source_refs or ["lotus-gateway:performance-summary:YTD"],
        ),
        expected_output_label=OutputLabel.EXPLANATION_ONLY,
    )


def advisor_brief_task_execution_request_json(
    *,
    correlation_id: str,
    task_id: str = "explain.v1",
    caller_app: str = "lotus-gateway",
    summary: str = "Draft advisor brief from source performance facts.",
    source_refs: list[str] | None = None,
    portfolio_return_pct: float = 1.25,
    benchmark_return_pct: float = 7.93,
    active_return_pct: float = -6.68,
) -> dict[str, object]:
    return {
        "task_id": task_id,
        "input_mode": "STRUCTURED_CONTEXT",
        "caller": {
            "caller_app": caller_app,
            "correlation_id": correlation_id,
        },
        "context": {
            "summary": summary,
            "payload": advisor_brief_payload(
                portfolio_return_pct=portfolio_return_pct,
                benchmark_return_pct=benchmark_return_pct,
                active_return_pct=active_return_pct,
            ),
            "source_refs": source_refs or ["lotus-gateway:performance-summary:YTD"],
        },
        "expected_output_label": "EXPLANATION_ONLY",
    }


def advisor_brief_workflow_pack_execution_request_json(
    *,
    correlation_id: str,
    task_id: str = "explain.v1",
    workflow_surface: str | None = "advisor-brief-workspace",
    environment: str = "DEVELOPMENT",
    caller_identity_class: str = "BANKER_PRODUCT",
    portfolio_return_pct: float = 1.25,
    benchmark_return_pct: float = 7.93,
    active_return_pct: float = -6.68,
) -> dict[str, object]:
    request: dict[str, object] = {
        "pack_id": "advisor_brief.pack",
        "version": "v1",
        "environment": environment,
        "caller_identity_class": caller_identity_class,
        "task_request": advisor_brief_task_execution_request_json(
            correlation_id=correlation_id,
            task_id=task_id,
            portfolio_return_pct=portfolio_return_pct,
            benchmark_return_pct=benchmark_return_pct,
            active_return_pct=active_return_pct,
        ),
    }
    if workflow_surface is not None:
        request["workflow_surface"] = workflow_surface
    return request
