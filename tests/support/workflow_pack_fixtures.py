from __future__ import annotations

from app.contracts.tasks import (
    CallerMetadata,
    OutputLabel,
    TaskContextEnvelope,
    TaskExecutionRequest,
    TaskInputMode,
)
from app.services.portfolio_memory_context_guardrails import PORTFOLIO_MEMORY_EVENT_REF_LIMIT


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


def advisory_copilot_payload(*, requested_outputs: list[str] | None = None) -> dict[str, object]:
    return {
        "copilot_evidence_packet": {
            "evidence_packet_id": "copilot_packet_pb_sg_001",
            "evidence_packet_hash": "sha256:copilot-evidence-packet-001",
            "action_family": "PROPOSAL_EXPLANATION",
            "portfolio_id": "PB_SG_GLOBAL_BAL_001",
            "proposal_id": "proposal_sg_structured_note_001",
            "client_ready_publication": "BLOCKED",
            "sections": [
                {
                    "section_key": "POLICY_POSTURE",
                    "title": "Policy posture",
                    "evidence_class": "COMPLIANCE_REVIEW_EVIDENCE",
                    "summary_items": ["Policy evaluation requires compliance review."],
                    "source_refs": [
                        {
                            "source_system": "lotus-advise",
                            "source_type": "POLICY_EVALUATION",
                            "source_id": "policy_eval_sg_001",
                            "content_hash": "sha256:policy-evaluation",
                        }
                    ],
                }
            ],
            "unsupported_evidence": [],
        },
        "copilot_request": {
            "action_family": "PROPOSAL_EXPLANATION",
            "audience": "ADVISOR",
            "requested_outputs": requested_outputs or ["advisor_review_summary"],
            "requested_by": "advisor_001",
        },
        "model_risk_controls": {
            "approved_provider_id": "lotus-ai",
            "approved_model_version": "lotus-ai-governed-model.v1",
            "approved_instruction_set": "advisory-copilot-instructions.v1",
            "prompt_template_version": "advisory-copilot-prompt-template.v1",
            "output_schema_version": "advisory-copilot-output-schema.v1",
            "evaluation_pack_ref": "advisory-copilot-eval-pack.v1",
        },
        "supportability": {
            "human_review_required": True,
            "client_ready_publication": "BLOCKED",
            "unsupported_claims": [
                "client_ready_publication",
                "policy_approval",
                "trade_or_order_action",
                "missing_evidence_inference",
            ],
        },
    }


def advisory_copilot_workflow_pack_execution_request_json(
    *,
    correlation_id: str,
    requested_outputs: list[str] | None = None,
    tenant_id: str = "tenant-sg-001",
) -> dict[str, object]:
    return {
        "pack_id": "advisory_copilot_proposal_explanation.pack",
        "version": "v1",
        "environment": "DEVELOPMENT",
        "caller_identity_class": "INTERNAL_SERVICE",
        "workflow_surface": "advisory-copilot-proposal-explanation",
        "task_request": {
            "task_id": "explain.v1",
            "input_mode": "STRUCTURED_CONTEXT",
            "caller": {
                "caller_app": "lotus-advise",
                "correlation_id": correlation_id,
                "tenant_id": tenant_id,
            },
            "context": {
                "summary": "Generate review-gated advisory copilot draft from bounded evidence.",
                "payload": advisory_copilot_payload(requested_outputs=requested_outputs),
                "source_refs": [
                    "lotus-advise:copilot-evidence-packet:copilot_packet_pb_sg_001",
                    ("lotus-advise:POLICY_EVALUATION:policy_eval_sg_001:sha256:policy-evaluation"),
                ],
            },
            "expected_output_label": "EXPLANATION_ONLY",
        },
    }


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
    include_portfolio_memory_context: bool = False,
) -> dict[str, object]:
    payload: dict[str, object] = {
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
    if include_portfolio_memory_context:
        payload["portfolio_memory_context"] = portfolio_memory_context_payload(
            portfolio_id=portfolio_id
        )
    return payload


def outcome_review_narrative_workflow_pack_execution_request_json(
    *,
    correlation_id: str,
    task_id: str = "explain.v1",
    caller_app: str = "lotus-manage",
    workflow_surface: str | None = "dpm-outcome-review-ai-evidence",
    environment: str = "DEVELOPMENT",
    caller_identity_class: str = "INTERNAL_SERVICE",
    requested_outputs: list[str] | None = None,
    include_portfolio_memory_context: bool = False,
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
                    include_portfolio_memory_context=include_portfolio_memory_context,
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


def proof_pack_pm_memo_payload(
    *,
    proof_pack_id: str = "dpp_c09f73d0",
    portfolio_id: str = "PB_SG_GLOBAL_BAL_001",
    content_hash: str = "sha256:proof-pack-ai-evidence-001",
    requested_outputs: list[str] | None = None,
    include_portfolio_memory_context: bool = False,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "ai_evidence_input": {
            "contract_version": "1.0",
            "proof_pack_id": proof_pack_id,
            "proof_pack_content_hash": "sha256:proof-pack-001",
            "portfolio_id": portfolio_id,
            "mandate_id": "MANDATE_PB_SG_GLOBAL_BAL_001",
            "as_of_date": "2026-05-03",
            "generated_at": "2026-05-03T09:30:00Z",
            "permitted_use": (
                "Draft support-only PM, compliance, and operations narratives from evidence."
            ),
            "forbidden_actions": [
                "place_orders",
                "approve_rebalance",
                "override_controls",
                "invent_missing_evidence",
                "contact_client",
            ],
            "forbidden_fields_removed": [],
            "decision_summary": {
                "selected_alternative_id": "ALT_REBALANCE_TO_MODEL",
                "recommendation": "Review rebalance back to approved balanced model.",
                "main_tradeoffs": ["Reduce drift while preserving liquidity buffer."],
            },
            "supportability_status": "READY",
            "reason_codes": ["PROOF_PACK_READY"],
            "sections": [
                {
                    "section_id": "selected_alternative",
                    "section_type": "SELECTED_ALTERNATIVE",
                    "state": "READY",
                    "summary": "Selected alternative rebalances toward model within guardrails.",
                    "reason_codes": ["SELECTED_ALTERNATIVE_READY"],
                    "bounded_facts": {"alternative_id": "ALT_REBALANCE_TO_MODEL"},
                    "bounded_metrics": {"cash_weight_after": "0.041"},
                    "content_hash": "sha256:proof-pack-section-001",
                }
            ],
            "source_refs": [
                {
                    "source_system": "lotus-manage",
                    "source_type": "DPM_PRE_TRADE_PROOF_PACK",
                    "source_id": proof_pack_id,
                    "content_hash": "sha256:proof-pack-001",
                }
            ],
            "evidence_ref": {
                "ref_type": "DPM_PROOF_PACK_AI_EVIDENCE_INPUT",
                "ref_id": f"{proof_pack_id}:dpm_proof_pack_ai_evidence_input",
                "source_system": "lotus-manage",
                "content_hash": content_hash,
            },
            "content_hash": content_hash,
        },
        "memo_request": {
            "requested_outputs": requested_outputs
            or [
                "pm_memo",
                "rationale_summary",
                "approval_checklist",
                "risk_caveats",
                "evidence_gaps",
            ],
            "audience": ["portfolio_manager", "investment_control", "operations"],
        },
        "supportability": {
            "source_state": "READY",
            "requires_human_review": True,
            "unsupported_claims": [
                "trade_approval",
                "order_instruction",
                "client_message",
            ],
        },
    }
    if include_portfolio_memory_context:
        payload["portfolio_memory_context"] = portfolio_memory_context_payload(
            portfolio_id=portfolio_id
        )
    return payload


def portfolio_memory_context_payload(
    *,
    portfolio_id: str = "PB_SG_GLOBAL_BAL_001",
    event_ref_count: int = 2,
) -> dict[str, object]:
    event_refs = [
        {
            "event_identity": (
                f"lotus-manage:DPM_PRE_TRADE_PROOF_PACK:dpp_c09f73d0:sha256:proof-pack-{index:03d}"
            ),
            "event_type": "PROOF_PACK_CREATED" if index == 0 else "OUTCOME_REVIEW_CREATED",
            "source_system": "lotus-manage",
            "source_type": ("DPM_PRE_TRADE_PROOF_PACK" if index == 0 else "DPM_OUTCOME_REVIEW"),
            "source_id": "dpp_c09f73d0" if index == 0 else "or_pb_sg_001",
            "event_time": f"2026-05-{10 + index:02d}T09:00:00Z",
            "event_ref_selection_rank": index + 1,
            "content_hash": f"sha256:portfolio-memory-source-{index:03d}",
            "retention_policy": "DPM_PORTFOLIO_MEMORY_SOURCE_LINEAGE_7Y",
            "redaction_policy": "NO_RAW_PAYLOADS",
            "audit_policy": "AUDIT_READ_AND_EXPORT",
            "access_classification": "CLIENT_CONFIDENTIAL_INTERNAL",
        }
        for index in range(event_ref_count)
    ]
    return {
        "portfolio_id": portfolio_id,
        "supportability_state": "READY",
        "context_content_hash": "sha256:portfolio-memory-context-envelope-001",
        "support_boundary": "AI_SOURCE_LINEAGE_ONLY_NO_RECONSTRUCTION",
        "event_ref_limit": PORTFOLIO_MEMORY_EVENT_REF_LIMIT,
        "event_ref_selection_policy": "MOST_RECENT_SOURCE_AUTHORITY_EVENTS",
        "event_refs_returned": event_ref_count,
        "event_refs_omitted": 0,
        "event_refs_truncated": False,
        "event_count": event_ref_count,
        "source_systems": ["lotus-manage"],
        "reason_codes": ["PORTFOLIO_MEMORY_READY"],
        "content_hash": "sha256:portfolio-memory-context-001",
        "governance_policy": {
            "event_identity_scheme": (
                "source_system:source_type:source_id:content_hash_or_content_hash_unavailable"
            ),
            "retention_policy": "DPM_PORTFOLIO_MEMORY_SOURCE_LINEAGE_7Y",
            "redaction_policy": "NO_RAW_PAYLOADS",
            "audit_policy": "AUDIT_READ_AND_EXPORT",
            "access_classification": "CLIENT_CONFIDENTIAL_INTERNAL",
            "source_authority_policy": (
                "portfolio memory projects source-owned facts; consumers must not reconstruct "
                "risk, performance, mandate-health, execution, tax, cash, FX, report, or AI truth"
            ),
        },
        "event_refs": event_refs,
    }


def proof_pack_pm_memo_workflow_pack_execution_request_json(
    *,
    correlation_id: str,
    task_id: str = "explain.v1",
    caller_app: str = "lotus-manage",
    workflow_surface: str | None = "dpm-proof-pack-ai-evidence",
    environment: str = "DEVELOPMENT",
    caller_identity_class: str = "INTERNAL_SERVICE",
    requested_outputs: list[str] | None = None,
    include_portfolio_memory_context: bool = False,
) -> dict[str, object]:
    request: dict[str, object] = {
        "pack_id": "dpm_pm_memo.pack",
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
                "summary": "Generate review-gated PM memo from bounded proof-pack AI evidence.",
                "payload": proof_pack_pm_memo_payload(
                    requested_outputs=requested_outputs,
                    include_portfolio_memory_context=include_portfolio_memory_context,
                ),
                "source_refs": [
                    "lotus-manage:proof-pack:dpp_c09f73d0",
                    "lotus-manage:proof-pack-ai-evidence:dpp_c09f73d0",
                ],
            },
            "expected_output_label": "EXPLANATION_ONLY",
        },
    }
    if workflow_surface is not None:
        request["workflow_surface"] = workflow_surface
    return request


def wave_pm_memo_payload(
    *,
    wave_id: str = "wave_20260508_001",
    portfolio_id: str = "PB_SG_GLOBAL_BAL_001",
    content_hash: str = "sha256:wave-report-input-001",
    requested_outputs: list[str] | None = None,
    include_portfolio_memory_context: bool = False,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "wave_report_input": {
            "contract_version": "1.0",
            "wave_id": wave_id,
            "wave_content_hash": "sha256:wave-domain-001",
            "wave_state": "PENDING_REVIEW",
            "trigger_type": "CIO_MODEL_CHANGE",
            "trigger_id": "cio_model_change_20260508",
            "trigger_rationale": "Balanced DPM model drift review after CIO model update.",
            "as_of_date": "2026-05-08",
            "generated_at": "2026-05-08T08:00:00Z",
            "report_title": f"Rebalance Wave Evidence - {wave_id}",
            "report_audience": [
                "portfolio_manager",
                "chief_investment_office",
                "investment_control",
                "operations",
            ],
            "aggregate_metrics": {
                "portfolio_count": 1,
                "ready_item_count": 1,
                "blocked_item_count": 0,
                "estimated_turnover_pct": "0.032",
            },
            "supportability": {
                "source_state": "READY",
                "reason_codes": ["WAVE_READY_FOR_REVIEW"],
            },
            "proof_pack_posture": {
                "proof_pack_count": 1,
                "proof_pack_refs": [
                    {
                        "proof_pack_id": "dpp_c09f73d0",
                        "portfolio_id": portfolio_id,
                        "state": "READY",
                        "content_hash": "sha256:proof-pack-001",
                    }
                ],
                "external_execution_claimed": False,
            },
            "items": [
                {
                    "wave_item_id": "wave_item_001",
                    "portfolio_id": portfolio_id,
                    "mandate_id": "MANDATE_PB_SG_GLOBAL_BAL_001",
                    "model_portfolio_id": "MODEL_PB_SG_GLOBAL_BAL_DPM",
                    "state": "READY",
                    "reason_codes": ["READY_FOR_PM_REVIEW"],
                    "selected_alternative_id": "ALT_REBALANCE_TO_MODEL",
                    "proof_pack_id": "dpp_c09f73d0",
                    "proof_pack_state": "READY",
                    "source_refs": [
                        {
                            "source_system": "lotus-manage",
                            "source_type": "DPM_WAVE_ITEM",
                            "source_id": "wave_item_001",
                            "content_hash": "sha256:wave-item-001",
                        }
                    ],
                    "diagnostics": {"proof_pack_state": "READY"},
                }
            ],
            "events": [
                {
                    "event_id": "wave_event_001",
                    "event_type": "WAVE_CREATED",
                    "from_state": None,
                    "to_state": "PENDING_REVIEW",
                    "actor_id": "lotus-manage",
                    "reason_code": "CIO_MODEL_CHANGE",
                    "correlation_id": "corr-wave-001",
                    "created_at": "2026-05-08T08:00:00Z",
                    "metadata": {"source": "governed_wave_orchestration"},
                }
            ],
            "handoff_refs": [
                {
                    "ref_type": "DPM_PRE_TRADE_PROOF_PACK",
                    "ref_id": "dpp_c09f73d0",
                    "source_system": "lotus-manage",
                    "content_hash": "sha256:proof-pack-001",
                }
            ],
            "source_refs": [
                {
                    "source_system": "lotus-manage",
                    "source_type": "DPM_WAVE_REPORT_INPUT",
                    "source_id": f"{wave_id}:dpm_wave_report_input",
                    "content_hash": content_hash,
                }
            ],
            "redaction_policy": "NO_RAW_PAYLOADS",
            "external_execution_claimed": False,
            "evidence_ref": {
                "ref_type": "DPM_WAVE_REPORT_INPUT",
                "ref_id": f"{wave_id}:dpm_wave_report_input",
                "source_system": "lotus-manage",
                "content_hash": content_hash,
            },
            "content_hash": content_hash,
        },
        "memo_request": {
            "requested_outputs": requested_outputs
            or [
                "wave_pm_memo",
                "wave_rationale_summary",
                "approval_checklist",
                "risk_caveats",
                "evidence_gaps",
            ],
            "audience": ["portfolio_manager", "cio_office", "investment_control"],
        },
        "supportability": {
            "source_state": "READY",
            "requires_human_review": True,
            "forbidden_actions": [
                "place_orders",
                "approve_rebalance",
                "override_controls",
                "invent_missing_evidence",
                "contact_client",
            ],
            "unsupported_claims": [
                "trade_approval",
                "order_instruction",
                "client_message",
                "external_execution",
            ],
        },
    }
    if include_portfolio_memory_context:
        payload["portfolio_memory_context"] = portfolio_memory_context_payload(
            portfolio_id=portfolio_id
        )
    return payload


def wave_pm_memo_workflow_pack_execution_request_json(
    *,
    correlation_id: str,
    task_id: str = "explain.v1",
    caller_app: str = "lotus-manage",
    workflow_surface: str | None = "dpm-wave-ai-evidence",
    environment: str = "DEVELOPMENT",
    caller_identity_class: str = "INTERNAL_SERVICE",
    requested_outputs: list[str] | None = None,
    include_portfolio_memory_context: bool = False,
) -> dict[str, object]:
    request: dict[str, object] = {
        "pack_id": "dpm_wave_pm_memo.pack",
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
                "summary": "Generate review-gated PM memo from bounded rebalance-wave evidence.",
                "payload": wave_pm_memo_payload(
                    requested_outputs=requested_outputs,
                    include_portfolio_memory_context=include_portfolio_memory_context,
                ),
                "source_refs": [
                    "lotus-manage:wave:wave_20260508_001",
                    "lotus-manage:wave-report-input:wave_20260508_001",
                ],
            },
            "expected_output_label": "EXPLANATION_ONLY",
        },
    }
    if workflow_surface is not None:
        request["workflow_surface"] = workflow_surface
    return request


def operations_handoff_summary_payload(
    *,
    requested_outputs: list[str] | None = None,
    include_portfolio_memory_context: bool = False,
) -> dict[str, object]:
    payload = wave_pm_memo_payload(
        requested_outputs=["operations_handoff"],
        include_portfolio_memory_context=include_portfolio_memory_context,
    )
    payload.pop("memo_request")
    payload["handoff_summary_request"] = {
        "requested_outputs": requested_outputs
        or [
            "operations_summary",
            "execution_prerequisites",
            "blocking_conditions",
            "support_references",
            "evidence_gaps",
        ],
        "audience": ["operations", "portfolio_manager", "investment_control"],
    }
    return payload


def operations_handoff_summary_workflow_pack_execution_request_json(
    *,
    correlation_id: str,
    task_id: str = "explain.v1",
    caller_app: str = "lotus-manage",
    workflow_surface: str | None = "dpm-operations-handoff-ai-evidence",
    environment: str = "DEVELOPMENT",
    caller_identity_class: str = "INTERNAL_SERVICE",
    requested_outputs: list[str] | None = None,
    include_portfolio_memory_context: bool = False,
) -> dict[str, object]:
    request: dict[str, object] = {
        "pack_id": "dpm_operations_handoff_summary.pack",
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
                "summary": (
                    "Generate review-gated operations handoff summary from bounded "
                    "rebalance-wave handoff evidence."
                ),
                "payload": operations_handoff_summary_payload(
                    requested_outputs=requested_outputs,
                    include_portfolio_memory_context=include_portfolio_memory_context,
                ),
                "source_refs": [
                    "lotus-manage:wave:wave_20260508_001",
                    "lotus-manage:wave-report-input:wave_20260508_001",
                ],
            },
            "expected_output_label": "EXPLANATION_ONLY",
        },
    }
    if workflow_surface is not None:
        request["workflow_surface"] = workflow_surface
    return request


def dpm_exception_summary_payload(
    *,
    portfolio_id: str = "PB_SG_GLOBAL_BAL_001",
    content_hash: str = "sha256:dpm-exception-summary-input-001",
    requested_outputs: list[str] | None = None,
    include_portfolio_memory_context: bool = False,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "exception_summary_input": {
            "contract_version": "1.0",
            "portfolio_id": portfolio_id,
            "mandate_id": "MANDATE_PB_SG_GLOBAL_BAL_001",
            "as_of_date": "2026-05-12",
            "generated_at": "2026-05-12T08:00:00Z",
            "exception_count": 2,
            "exceptions": [
                {
                    "exception_id": "dpm_exception_001",
                    "portfolio_id": portfolio_id,
                    "mandate_id": "MANDATE_PB_SG_GLOBAL_BAL_001",
                    "severity": "HIGH",
                    "state": "OPEN",
                    "reason_code": "CASH_LIQUIDITY_ATTENTION",
                    "recommended_action": "REVIEW_WITH_PM",
                    "detected_at": "2026-05-12T07:50:00Z",
                    "source_refs": [
                        {
                            "source_system": "lotus-manage",
                            "source_type": "DPM_MONITORING_EXCEPTION",
                            "source_id": "dpm_exception_001",
                            "content_hash": "sha256:dpm-exception-001",
                        }
                    ],
                },
                {
                    "exception_id": "dpm_exception_002",
                    "portfolio_id": portfolio_id,
                    "mandate_id": "MANDATE_PB_SG_GLOBAL_BAL_001",
                    "severity": "MEDIUM",
                    "state": "OPEN",
                    "reason_code": "BENCHMARK_DRIFT_REVIEW",
                    "recommended_action": "CHECK_SOURCE_EVIDENCE",
                    "detected_at": "2026-05-12T07:55:00Z",
                    "source_refs": [
                        {
                            "source_system": "lotus-manage",
                            "source_type": "DPM_MONITORING_EXCEPTION",
                            "source_id": "dpm_exception_002",
                            "content_hash": "sha256:dpm-exception-002",
                        }
                    ],
                },
            ],
            "source_refs": [
                {
                    "source_system": "lotus-manage",
                    "source_type": "DPM_EXCEPTION_SUMMARY_INPUT",
                    "source_id": f"{portfolio_id}:dpm_exception_summary_input",
                    "content_hash": content_hash,
                }
            ],
            "redaction_policy": "NO_RAW_PAYLOADS",
            "evidence_ref": {
                "source_system": "lotus-manage",
                "source_type": "DPM_EXCEPTION_SUMMARY_INPUT",
                "source_id": f"{portfolio_id}:dpm_exception_summary_input",
                "content_hash": content_hash,
            },
            "content_hash": content_hash,
        },
        "exception_summary_request": {
            "requested_outputs": requested_outputs
            or [
                "exception_summary",
                "severity_summary",
                "recommended_triage",
                "support_references",
                "evidence_gaps",
            ],
            "audience": ["portfolio_manager", "investment_control", "operations"],
        },
        "supportability": {
            "source_state": "READY",
            "requires_human_review": True,
            "forbidden_actions": [
                "approve_rebalance",
                "contact_client",
                "invent_missing_evidence",
                "override_controls",
                "place_orders",
                "score_portfolio_manager",
            ],
            "unsupported_claims": [
                "trade_approval",
                "order_instruction",
                "client_message",
                "portfolio_manager_scoring",
            ],
        },
    }
    if include_portfolio_memory_context:
        payload["portfolio_memory_context"] = portfolio_memory_context_payload(
            portfolio_id=portfolio_id
        )
    return payload


def dpm_exception_summary_workflow_pack_execution_request_json(
    *,
    correlation_id: str,
    task_id: str = "explain.v1",
    caller_app: str = "lotus-manage",
    workflow_surface: str | None = "dpm-exception-summary-ai-evidence",
    environment: str = "DEVELOPMENT",
    caller_identity_class: str = "INTERNAL_SERVICE",
    requested_outputs: list[str] | None = None,
    include_portfolio_memory_context: bool = False,
) -> dict[str, object]:
    request: dict[str, object] = {
        "pack_id": "dpm_exception_summary.pack",
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
                "summary": (
                    "Generate review-gated DPM exception summary from bounded monitoring evidence."
                ),
                "payload": dpm_exception_summary_payload(
                    requested_outputs=requested_outputs,
                    include_portfolio_memory_context=include_portfolio_memory_context,
                ),
                "source_refs": [
                    "lotus-manage:monitoring-exception:dpm_exception_001",
                    "lotus-manage:monitoring-exception:dpm_exception_002",
                ],
            },
            "expected_output_label": "EXPLANATION_ONLY",
        },
    }
    if workflow_surface is not None:
        request["workflow_surface"] = workflow_surface
    return request


def pm_quality_summary_payload(
    *,
    portfolio_id: str = "PB_SG_GLOBAL_BAL_001",
    content_hash: str = "sha256:pm-quality-score-run-001",
    requested_outputs: list[str] | None = None,
    include_portfolio_memory_context: bool = False,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "score_run": {
            "product_name": "PmOperatingQualityScoreRun",
            "product_version": "1.0",
            "score_run_id": "pmq_run_20260516_001",
            "policy_id": "pmq_policy_operating_quality",
            "policy_version": "2026.05",
            "portfolio_manager_id": "pm_sg_001",
            "portfolio_id": portfolio_id,
            "as_of_date": "2026-05-16",
            "state": "READY",
            "score": "0.86",
            "reason_codes": ["PM_QUALITY_WITHIN_POLICY"],
            "indicator_results": [
                {
                    "indicator_id": "source_evidence_completeness",
                    "state": "READY",
                    "score": "0.92",
                    "reason_codes": ["PM_QUALITY_SOURCE_EVIDENCE_COMPLETE"],
                    "source_refs": [
                        {
                            "source_system": "lotus-manage",
                            "source_type": "PmOperatingQualityScoreRun",
                            "source_id": "pmq_run_20260516_001",
                            "content_hash": content_hash,
                        }
                    ],
                }
            ],
            "governance_evidence": {
                "approval_ref": "PMQ-APPROVAL-2026-05",
                "fairness_review_ref": "PMQ-FAIRNESS-2026-05",
                "approved_by": "investment-control",
                "fairness_reviewed_by": "fairness-committee",
                "approved_at": "2026-05-15T09:00:00Z",
                "fairness_reviewed_at": "2026-05-15T10:00:00Z",
            },
            "source_refs": [
                {
                    "source_system": "lotus-manage",
                    "source_type": "PmOperatingQualityScoreRun",
                    "source_id": "pmq_run_20260516_001",
                    "content_hash": content_hash,
                }
            ],
            "content_hash": content_hash,
        },
        "summary_request": {
            "requested_outputs": requested_outputs
            or [
                "score_run_summary",
                "governance_summary",
                "fairness_review_posture",
                "support_references",
                "evidence_gaps",
            ],
            "audience": ["portfolio_manager", "investment_control", "cio_office"],
        },
        "supportability": {
            "source_state": "READY",
            "requires_human_review": True,
            "forbidden_actions": [
                "approve_rebalance",
                "contact_client",
                "enforce_conduct_action",
                "invent_missing_evidence",
                "make_compensation_decisions",
                "make_hr_decisions",
                "place_orders",
                "rank_portfolio_managers",
            ],
            "unsupported_claims": [
                "pm_ranking",
                "hr_decision",
                "compensation_decision",
                "conduct_enforcement",
                "client_message",
                "trade_approval",
                "execution_instruction",
            ],
        },
    }
    if include_portfolio_memory_context:
        payload["portfolio_memory_context"] = portfolio_memory_context_payload(
            portfolio_id=portfolio_id
        )
    return payload


def pm_quality_summary_workflow_pack_execution_request_json(
    *,
    correlation_id: str,
    task_id: str = "explain.v1",
    caller_app: str = "lotus-manage",
    workflow_surface: str | None = "dpm-pm-quality-ai-evidence",
    environment: str = "DEVELOPMENT",
    caller_identity_class: str = "INTERNAL_SERVICE",
    requested_outputs: list[str] | None = None,
    include_portfolio_memory_context: bool = False,
) -> dict[str, object]:
    request: dict[str, object] = {
        "pack_id": "pm_quality_summary.pack",
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
                "summary": (
                    "Generate review-gated PM operating quality summary from bounded score-run "
                    "evidence."
                ),
                "payload": pm_quality_summary_payload(
                    requested_outputs=requested_outputs,
                    include_portfolio_memory_context=include_portfolio_memory_context,
                ),
                "source_refs": [
                    "lotus-manage:pm-quality-score-run:pmq_run_20260516_001",
                    "lotus-manage:pm-quality-policy:pmq_policy_operating_quality:2026.05",
                ],
            },
            "expected_output_label": "EXPLANATION_ONLY",
        },
    }
    if workflow_surface is not None:
        request["workflow_surface"] = workflow_surface
    return request


def idea_explanation_payload(*, requested_outputs: list[str] | None = None) -> dict[str, object]:
    return {
        "redacted_evidence_packet": {
            "candidate_id": "idea_high_cash_001",
            "family": "HIGH_CASH",
            "lifecycle_status": "READY_FOR_REVIEW",
            "review_posture": "ADVISOR_REVIEW_REQUIRED",
            "evidence_packet_id": "idea_evidence_high_cash_001",
            "evidence_content_hash": "sha256:idea-evidence-high-cash-001",
            "supportability": "READY",
            "score_policy_version": "idea-score-policy.v1",
            "score": "0.82",
            "source_signal_count": 3,
            "reason_codes": [
                "HIGH_CASH_WEIGHT",
                "BENCHMARK_DRIFT_ATTENTION",
            ],
            "source_refs": [
                {
                    "source_system": "lotus-core",
                    "product_id": "core-position-snapshot",
                    "product_version": "2026.06",
                    "source_id": "PB_SG_GLOBAL_BAL_001:positions:2026-06-25",
                    "content_hash": "sha256:core-position-snapshot-001",
                },
                {
                    "source_system": "lotus-risk",
                    "product_id": "risk-concentration-snapshot",
                    "product_version": "2026.06",
                    "source_id": "PB_SG_GLOBAL_BAL_001:risk:2026-06-25",
                    "content_hash": "sha256:risk-concentration-snapshot-001",
                },
            ],
        },
        "explanation_request": {
            "request_id": "idea-explanation-request-001",
            "workflow_pack_id": "lotus-ai:idea-explanation:v1",
            "workflow_pack_version": "v1",
            "purpose": "unsupported_claim_verification",
            "evaluation_ref": "idea-explanation-eval-pack.v1",
            "audience": "advisor",
            "requested_outputs": requested_outputs
            or [
                "advisor_review_summary",
                "source_evidence_summary",
                "unsupported_claim_check",
            ],
        },
        "supportability": {
            "human_review_required": True,
            "client_ready_publication": "BLOCKED",
            "forbidden_actions": [
                "approve_suitability",
                "contact_client",
                "invent_missing_evidence",
                "make_final_recommendation",
                "place_orders",
            ],
            "unsupported_claims": [
                "client_ready_publication",
                "final_investment_recommendation",
                "suitability_approval",
                "trade_or_order_action",
            ],
        },
    }


def idea_explanation_workflow_pack_execution_request_json(
    *,
    correlation_id: str,
    task_id: str = "explain.v1",
    caller_app: str = "lotus-idea",
    workflow_surface: str | None = "idea-explanation-evidence",
    environment: str = "DEVELOPMENT",
    caller_identity_class: str = "INTERNAL_SERVICE",
    requested_outputs: list[str] | None = None,
) -> dict[str, object]:
    request: dict[str, object] = {
        "pack_id": "idea_explanation.pack",
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
                "summary": (
                    "Generate a review-gated Idea explanation from redacted source evidence."
                ),
                "payload": idea_explanation_payload(requested_outputs=requested_outputs),
                "source_refs": [
                    "lotus-idea:evidence-packet:idea_evidence_high_cash_001",
                    "lotus-core:positions:PB_SG_GLOBAL_BAL_001:2026-06-25",
                    "lotus-risk:concentration:PB_SG_GLOBAL_BAL_001:2026-06-25",
                ],
            },
            "expected_output_label": "EXPLANATION_ONLY",
        },
    }
    if workflow_surface is not None:
        request["workflow_surface"] = workflow_surface
    return request
