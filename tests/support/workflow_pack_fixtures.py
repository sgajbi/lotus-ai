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
    tenant_id: str | None = "tenant-sg-001",
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
            tenant_id=tenant_id,
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
    tenant_id: str | None = "tenant-sg-001",
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
            "tenant_id": tenant_id,
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
    queue_lane: str | None = None,
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
    if queue_lane is not None:
        request["queue_lane"] = queue_lane
    return request


def workspace_rationale_payload(
    *,
    workspace_id: str = "aws_001",
    proposal_status: str = "READY",
    instruction: str = "Summarize the proposal rationale for an advisor review note.",
) -> dict[str, object]:
    return {
        "workspace": {
            "workspace_id": workspace_id,
            "input_mode": "stateless",
            "requested_by": "advisor_123",
        },
        "evaluation_summary": {
            "status": proposal_status,
            "impact_summary": {
                "trade_count": 1,
                "cash_flow_count": 0,
            },
        },
        "proposal_status": {"value": proposal_status},
        "instruction": {"text": instruction},
        "resolved_context": {
            "portfolio_id": "pf_advisory_01",
            "as_of": "2026-03-25",
        },
    }


def workspace_rationale_workflow_pack_execution_request_json(
    *,
    correlation_id: str,
    task_id: str = "explain.v1",
    workflow_surface: str | None = "advisory-workspace-assistant",
    environment: str = "DEVELOPMENT",
    caller_identity_class: str = "INTERNAL_SERVICE",
    workspace_id: str = "aws_001",
    proposal_status: str = "READY",
    instruction: str = "Summarize the proposal rationale for an advisor review note.",
) -> dict[str, object]:
    request: dict[str, object] = {
        "pack_id": "workspace_rationale.pack",
        "version": "v1",
        "environment": environment,
        "caller_identity_class": caller_identity_class,
        "task_request": {
            "task_id": task_id,
            "input_mode": "STRUCTURED_CONTEXT",
            "caller": {
                "caller_app": "lotus-advise",
                "correlation_id": correlation_id,
                "tenant_id": "tenant-us-002",
            },
            "context": {
                "summary": (f"Advisory workspace rationale request for workspace {workspace_id}."),
                "payload": workspace_rationale_payload(
                    workspace_id=workspace_id,
                    proposal_status=proposal_status,
                    instruction=instruction,
                ),
                "source_refs": [
                    f"lotus-advise:workspace:{workspace_id}",
                    "lotus-advise:proposal-decision-summary",
                ],
            },
            "expected_output_label": "EXPLANATION_ONLY",
        },
    }
    if workflow_surface is not None:
        request["workflow_surface"] = workflow_surface
    return request


def twr_inspection_support_brief_payload(
    *,
    inspection_id: str = "9d000001-1111-4222-8333-abcdefabcdef",
    portfolio_id: str = "PB_SG_GLOBAL_BAL_001",
    verdict: str = "supportable_with_warnings",
) -> dict[str, object]:
    return {
        "inspection": {
            "inspection_id": inspection_id,
            "portfolio_id": portfolio_id,
            "verdict": verdict,
            "inspection_profile": "support_triage",
        },
        "findings": [
            {
                "code": "EXTERNAL_CASHFLOW_NORMALIZATION_MISMATCH",
                "severity": "high",
                "category": "cashflow_classification",
                "owner_repo": "lotus-performance",
                "summary": "External cash-flow economics do not tie to served TWR valuation points.",
                "recommended_action": (
                    "Review the source-economics artifact and fix the normalization path or upstream payload."
                ),
            }
        ],
        "owner_summary": {
            "primary_owner_repo": "lotus-performance",
            "secondary_owner_repos": ["lotus-core"],
        },
        "evidence_summary": {
            "completed_check_families": 5,
            "reconciliation_gap_date_count": 0,
        },
        "check_coverage": {
            "completed_check_families": [
                "calculation_consistency",
                "source_quality",
                "economic_plausibility",
                "reconciliation",
                "cashflow_classification",
            ],
            "pending_check_families": [],
        },
    }


def twr_inspection_support_brief_workflow_pack_execution_request_json(
    *,
    correlation_id: str,
    task_id: str = "explain.v1",
    workflow_surface: str | None = "twr-supportability-inspection",
    environment: str = "DEVELOPMENT",
    caller_identity_class: str = "INTERNAL_SERVICE",
    inspection_id: str = "9d000001-1111-4222-8333-abcdefabcdef",
    portfolio_id: str = "PB_SG_GLOBAL_BAL_001",
    verdict: str = "supportable_with_warnings",
) -> dict[str, object]:
    request: dict[str, object] = {
        "pack_id": "twr_inspection_support_brief.pack",
        "version": "v1",
        "environment": environment,
        "caller_identity_class": caller_identity_class,
        "task_request": {
            "task_id": task_id,
            "input_mode": "STRUCTURED_CONTEXT",
            "caller": {
                "caller_app": "lotus-performance",
                "correlation_id": correlation_id,
                "tenant_id": "tenant-sg-001",
            },
            "context": {
                "summary": (
                    f"TWR inspection support brief request for inspection {inspection_id}."
                ),
                "payload": twr_inspection_support_brief_payload(
                    inspection_id=inspection_id,
                    portfolio_id=portfolio_id,
                    verdict=verdict,
                ),
                "source_refs": [
                    f"lotus-performance:twr-inspection:{inspection_id}",
                    f"lotus-performance:portfolio:{portfolio_id}",
                ],
            },
            "expected_output_label": "EXPLANATION_ONLY",
        },
    }
    if workflow_surface is not None:
        request["workflow_surface"] = workflow_surface
    return request


def outcome_review_narrative_payload(
    *,
    outcome_review_id: str = "or_pb_sg_001",
    portfolio_id: str = "PB_SG_GLOBAL_BAL_001",
    content_hash: str = "sha256:outcome-ai-evidence-001",
    requested_outputs: list[str] | None = None,
) -> dict[str, object]:
    return {
        "ai_evidence_input": {
            "contract_version": "1.0",
            "outcome_review_id": outcome_review_id,
            "outcome_review_content_hash": "sha256:outcome-review-001",
            "portfolio_id": portfolio_id,
            "mandate_id": "mandate_pb_sg_balanced",
            "rebalance_run_id": "rr_20260505_001",
            "proof_pack_id": "pp_20260505_001",
            "wave_id": "wave_20260505_001",
            "review_window": {"start_date": "2026-04-01", "end_date": "2026-04-30"},
            "generated_at": "2026-05-05T08:00:00Z",
            "permitted_use": (
                "Draft support-only PM, CIO, compliance, and operations narratives from evidence."
            ),
            "forbidden_actions": [
                "place_orders",
                "approve_rebalance",
                "override_controls",
                "invent_missing_evidence",
                "score_portfolio_manager",
                "contact_client",
            ],
            "forbidden_fields_removed": [],
            "state": "COMPLETE",
            "overall_outcome": "Implemented rebalance stayed within expected risk and cash bands.",
            "reason_codes": ["OUTCOME_REVIEW_COMPLETE"],
            "dimensions": [
                {
                    "dimension": "cash",
                    "state": "MATCHED",
                    "reason_code": "CASH_WITHIN_TOLERANCE",
                    "expected": "4.0",
                    "realized": "4.1",
                    "variance": "0.1",
                    "explanation": "Realized cash weight remained inside the bounded tolerance.",
                }
            ],
            "source_refs": [
                {
                    "source_system": "lotus-manage",
                    "source_type": "DPM_OUTCOME_AI_EVIDENCE_INPUT",
                    "source_id": f"{outcome_review_id}:dpm_outcome_ai_evidence_input",
                    "content_hash": content_hash,
                }
            ],
            "evidence_ref": {
                "source_system": "lotus-manage",
                "source_type": "DPM_OUTCOME_AI_EVIDENCE_INPUT",
                "source_id": f"{outcome_review_id}:dpm_outcome_ai_evidence_input",
                "content_hash": content_hash,
            },
            "content_hash": content_hash,
        },
        "narrative_request": {
            "requested_outputs": requested_outputs
            or ["pm_summary", "cio_summary", "control_summary", "evidence_gaps"],
            "audience": ["portfolio_manager", "cio_office", "investment_control"],
        },
        "supportability": {
            "source_state": "READY",
            "requires_human_review": True,
            "unsupported_claims": [
                "client_contact",
                "trade_approval",
                "portfolio_manager_scoring",
            ],
        },
    }


def outcome_review_narrative_workflow_pack_execution_request_json(
    *,
    correlation_id: str,
    task_id: str = "explain.v1",
    caller_app: str = "lotus-manage",
    workflow_surface: str | None = "dpm-outcome-review-ai-evidence",
    environment: str = "DEVELOPMENT",
    caller_identity_class: str = "INTERNAL_SERVICE",
    requested_outputs: list[str] | None = None,
) -> dict[str, object]:
    request: dict[str, object] = {
        "pack_id": "outcome_review_narrative.pack",
        "version": "v1",
        "environment": environment,
        "caller_identity_class": caller_identity_class,
        "task_request": {
            "task_id": task_id,
            "input_mode": "STRUCTURED_CONTEXT",
            "caller": {
                "caller_app": caller_app,
                "correlation_id": correlation_id,
                "tenant_id": "tenant-sg-001",
            },
            "context": {
                "summary": "Generate review-gated outcome-review narrative from bounded AI evidence.",
                "payload": outcome_review_narrative_payload(
                    requested_outputs=requested_outputs,
                ),
                "source_refs": [
                    "lotus-manage:outcome-review:or_pb_sg_001",
                    "lotus-manage:outcome-ai-evidence:or_pb_sg_001",
                ],
            },
            "expected_output_label": "EXPLANATION_ONLY",
        },
    }
    if workflow_surface is not None:
        request["workflow_surface"] = workflow_surface
    return request
