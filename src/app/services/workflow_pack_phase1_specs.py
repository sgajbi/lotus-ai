from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class WorkflowPackPhase1VersionSpec:
    pack_id: str
    pack_family: str
    version: str
    owner_repository: str
    owner_service: str
    truth_owner_services: tuple[str, ...]
    primary_use_case: str
    workflow_authority_owner: str
    supported_callers: tuple[str, ...]
    surface_scope: tuple[str, ...]
    default_workflow_surface: str | None = None
    execution_task_id: str | None = None
    required_payload_keys: frozenset[str] = field(default_factory=frozenset)


ADVISOR_BRIEF_V1_SPEC = WorkflowPackPhase1VersionSpec(
    pack_id="advisor_brief.pack",
    pack_family="advisor_brief",
    version="v1",
    owner_repository="lotus-gateway",
    owner_service="lotus-gateway",
    truth_owner_services=("lotus-gateway", "lotus-performance", "lotus-risk"),
    primary_use_case="advisor_brief",
    workflow_authority_owner="lotus-gateway",
    supported_callers=("lotus-gateway",),
    surface_scope=("advisor-brief-panel", "advisor-brief-workspace"),
    default_workflow_surface="advisor-brief-workspace",
    execution_task_id="explain.v1",
    required_payload_keys=frozenset({"portfolio", "period", "performance", "supportability"}),
)


ADVISOR_BRIEF_V2_SPEC = WorkflowPackPhase1VersionSpec(
    pack_id="advisor_brief.pack",
    pack_family="advisor_brief",
    version="v2",
    owner_repository="lotus-gateway",
    owner_service="lotus-gateway",
    truth_owner_services=("lotus-gateway", "lotus-performance", "lotus-risk"),
    primary_use_case="advisor_brief",
    workflow_authority_owner="lotus-gateway",
    supported_callers=("lotus-gateway",),
    surface_scope=("advisor-brief-panel",),
)


WORKSPACE_RATIONALE_V1_SPEC = WorkflowPackPhase1VersionSpec(
    pack_id="workspace_rationale.pack",
    pack_family="workspace_rationale",
    version="v1",
    owner_repository="lotus-advise",
    owner_service="lotus-advise",
    truth_owner_services=("lotus-advise", "lotus-core", "lotus-risk"),
    primary_use_case="advisory_workspace_rationale",
    workflow_authority_owner="lotus-advise",
    supported_callers=("lotus-advise",),
    surface_scope=("advisory-workspace-assistant",),
    default_workflow_surface="advisory-workspace-assistant",
    execution_task_id="explain.v1",
    required_payload_keys=frozenset(
        {"workspace", "evaluation_summary", "proposal_status", "instruction"}
    ),
)


PROPOSAL_MEMO_COMMENTARY_V1_SPEC = WorkflowPackPhase1VersionSpec(
    pack_id="proposal_memo_commentary.pack",
    pack_family="proposal_memo_commentary",
    version="v1",
    owner_repository="lotus-advise",
    owner_service="lotus-advise",
    truth_owner_services=("lotus-advise", "lotus-core", "lotus-risk"),
    primary_use_case="advisor_proposal_memo_review_gated_commentary",
    workflow_authority_owner="lotus-advise",
    supported_callers=("lotus-advise",),
    surface_scope=("advisor-proposal-memo-commentary",),
    default_workflow_surface="advisor-proposal-memo-commentary",
    execution_task_id="explain.v1",
    required_payload_keys=frozenset({"memo_evidence", "commentary_request", "supportability"}),
)


ADVISORY_COPILOT_V1_REQUIRED_PAYLOAD_KEYS = frozenset(
    {
        "copilot_evidence_packet",
        "copilot_request",
        "model_risk_controls",
        "supportability",
    }
)


ADVISORY_COPILOT_ACTION_PACK_SPECS = (
    WorkflowPackPhase1VersionSpec(
        pack_id="advisory_copilot_proposal_explanation.pack",
        pack_family="advisory_copilot_proposal_explanation",
        version="v1",
        owner_repository="lotus-advise",
        owner_service="lotus-advise",
        truth_owner_services=("lotus-advise", "lotus-core", "lotus-risk", "lotus-report"),
        primary_use_case="advisory_copilot_proposal_explanation",
        workflow_authority_owner="lotus-advise",
        supported_callers=("lotus-advise",),
        surface_scope=("advisory-copilot-proposal-explanation",),
        default_workflow_surface="advisory-copilot-proposal-explanation",
        execution_task_id="explain.v1",
        required_payload_keys=ADVISORY_COPILOT_V1_REQUIRED_PAYLOAD_KEYS,
    ),
    WorkflowPackPhase1VersionSpec(
        pack_id="advisory_copilot_evidence_qa.pack",
        pack_family="advisory_copilot_evidence_qa",
        version="v1",
        owner_repository="lotus-advise",
        owner_service="lotus-advise",
        truth_owner_services=("lotus-advise", "lotus-core", "lotus-risk"),
        primary_use_case="advisory_copilot_evidence_qa",
        workflow_authority_owner="lotus-advise",
        supported_callers=("lotus-advise",),
        surface_scope=("advisory-copilot-evidence-qa",),
        default_workflow_surface="advisory-copilot-evidence-qa",
        execution_task_id="explain.v1",
        required_payload_keys=ADVISORY_COPILOT_V1_REQUIRED_PAYLOAD_KEYS,
    ),
    WorkflowPackPhase1VersionSpec(
        pack_id="advisory_copilot_meeting_preparation.pack",
        pack_family="advisory_copilot_meeting_preparation",
        version="v1",
        owner_repository="lotus-advise",
        owner_service="lotus-advise",
        truth_owner_services=("lotus-advise", "lotus-core", "lotus-risk"),
        primary_use_case="advisory_copilot_meeting_preparation",
        workflow_authority_owner="lotus-advise",
        supported_callers=("lotus-advise",),
        surface_scope=("advisory-copilot-meeting-preparation",),
        default_workflow_surface="advisory-copilot-meeting-preparation",
        execution_task_id="explain.v1",
        required_payload_keys=ADVISORY_COPILOT_V1_REQUIRED_PAYLOAD_KEYS,
    ),
    WorkflowPackPhase1VersionSpec(
        pack_id="advisory_copilot_compliance_review_summary.pack",
        pack_family="advisory_copilot_compliance_review_summary",
        version="v1",
        owner_repository="lotus-advise",
        owner_service="lotus-advise",
        truth_owner_services=("lotus-advise", "lotus-core", "lotus-risk"),
        primary_use_case="advisory_copilot_compliance_review_summary",
        workflow_authority_owner="lotus-advise",
        supported_callers=("lotus-advise",),
        surface_scope=("advisory-copilot-compliance-review-summary",),
        default_workflow_surface="advisory-copilot-compliance-review-summary",
        execution_task_id="explain.v1",
        required_payload_keys=ADVISORY_COPILOT_V1_REQUIRED_PAYLOAD_KEYS,
    ),
    WorkflowPackPhase1VersionSpec(
        pack_id="advisory_copilot_operations_report_handoff.pack",
        pack_family="advisory_copilot_operations_report_handoff",
        version="v1",
        owner_repository="lotus-advise",
        owner_service="lotus-advise",
        truth_owner_services=("lotus-advise", "lotus-report", "lotus-archive"),
        primary_use_case="advisory_copilot_operations_report_handoff",
        workflow_authority_owner="lotus-advise",
        supported_callers=("lotus-advise",),
        surface_scope=("advisory-copilot-operations-report-handoff",),
        default_workflow_surface="advisory-copilot-operations-report-handoff",
        execution_task_id="explain.v1",
        required_payload_keys=ADVISORY_COPILOT_V1_REQUIRED_PAYLOAD_KEYS,
    ),
    WorkflowPackPhase1VersionSpec(
        pack_id="advisory_copilot_client_follow_up_draft.pack",
        pack_family="advisory_copilot_client_follow_up_draft",
        version="v1",
        owner_repository="lotus-advise",
        owner_service="lotus-advise",
        truth_owner_services=("lotus-advise", "lotus-core", "lotus-risk"),
        primary_use_case="advisory_copilot_client_follow_up_draft",
        workflow_authority_owner="lotus-advise",
        supported_callers=("lotus-advise",),
        surface_scope=("advisory-copilot-client-follow-up-draft",),
        default_workflow_surface="advisory-copilot-client-follow-up-draft",
        execution_task_id="explain.v1",
        required_payload_keys=ADVISORY_COPILOT_V1_REQUIRED_PAYLOAD_KEYS,
    ),
)


TWR_INSPECTION_SUPPORT_BRIEF_V1_SPEC = WorkflowPackPhase1VersionSpec(
    pack_id="twr_inspection_support_brief.pack",
    pack_family="twr_inspection_support_brief",
    version="v1",
    owner_repository="lotus-performance",
    owner_service="lotus-performance",
    truth_owner_services=("lotus-performance", "lotus-core"),
    primary_use_case="twr_inspection_support_brief",
    workflow_authority_owner="lotus-performance",
    supported_callers=("lotus-performance",),
    surface_scope=("twr-supportability-inspection",),
    default_workflow_surface="twr-supportability-inspection",
    execution_task_id="explain.v1",
    required_payload_keys=frozenset(
        {"inspection", "findings", "owner_summary", "evidence_summary", "check_coverage"}
    ),
)


PROOF_PACK_PM_MEMO_V1_SPEC = WorkflowPackPhase1VersionSpec(
    pack_id="dpm_pm_memo.pack",
    pack_family="dpm_pm_memo",
    version="v1",
    owner_repository="lotus-manage",
    owner_service="lotus-manage",
    truth_owner_services=("lotus-manage", "lotus-core", "lotus-risk", "lotus-performance"),
    primary_use_case="dpm_proof_pack_pm_memo",
    workflow_authority_owner="lotus-manage",
    supported_callers=("lotus-manage", "lotus-gateway"),
    surface_scope=("dpm-proof-pack-ai-evidence",),
    default_workflow_surface="dpm-proof-pack-ai-evidence",
    execution_task_id="explain.v1",
    required_payload_keys=frozenset({"ai_evidence_input", "memo_request", "supportability"}),
)


OUTCOME_REVIEW_NARRATIVE_V1_SPEC = WorkflowPackPhase1VersionSpec(
    pack_id="outcome_review_narrative.pack",
    pack_family="outcome_review_narrative",
    version="v1",
    owner_repository="lotus-manage",
    owner_service="lotus-manage",
    truth_owner_services=("lotus-manage", "lotus-core", "lotus-risk", "lotus-performance"),
    primary_use_case="dpm_outcome_review_ai_narrative",
    workflow_authority_owner="lotus-manage",
    supported_callers=("lotus-manage", "lotus-gateway"),
    surface_scope=("dpm-outcome-review-ai-evidence",),
    default_workflow_surface="dpm-outcome-review-ai-evidence",
    execution_task_id="explain.v1",
    required_payload_keys=frozenset({"ai_evidence_input", "narrative_request", "supportability"}),
)


DPM_WAVE_PM_MEMO_V1_SPEC = WorkflowPackPhase1VersionSpec(
    pack_id="dpm_wave_pm_memo.pack",
    pack_family="dpm_wave_pm_memo",
    version="v1",
    owner_repository="lotus-manage",
    owner_service="lotus-manage",
    truth_owner_services=("lotus-manage", "lotus-core", "lotus-risk", "lotus-performance"),
    primary_use_case="dpm_rebalance_wave_pm_memo",
    workflow_authority_owner="lotus-manage",
    supported_callers=("lotus-manage", "lotus-gateway"),
    surface_scope=("dpm-wave-ai-evidence",),
    default_workflow_surface="dpm-wave-ai-evidence",
    execution_task_id="explain.v1",
    required_payload_keys=frozenset({"wave_report_input", "memo_request", "supportability"}),
)


IDEA_EXPLANATION_V1_SPEC = WorkflowPackPhase1VersionSpec(
    pack_id="idea_explanation.pack",
    pack_family="idea_explanation",
    version="v1",
    owner_repository="lotus-idea",
    owner_service="lotus-idea",
    truth_owner_services=(
        "lotus-idea",
        "lotus-core",
        "lotus-performance",
        "lotus-risk",
        "lotus-advise",
        "lotus-manage",
        "lotus-report",
    ),
    primary_use_case="governed_idea_explanation",
    workflow_authority_owner="lotus-idea",
    supported_callers=("lotus-idea", "lotus-gateway"),
    surface_scope=("idea-explanation-evidence",),
    default_workflow_surface="idea-explanation-evidence",
    execution_task_id="explain.v1",
    required_payload_keys=frozenset(
        {"redacted_evidence_packet", "explanation_request", "supportability"}
    ),
)


DPM_OPERATIONS_HANDOFF_SUMMARY_V1_SPEC = WorkflowPackPhase1VersionSpec(
    pack_id="dpm_operations_handoff_summary.pack",
    pack_family="dpm_operations_handoff_summary",
    version="v1",
    owner_repository="lotus-manage",
    owner_service="lotus-manage",
    truth_owner_services=("lotus-manage", "lotus-core", "lotus-risk", "lotus-performance"),
    primary_use_case="dpm_operations_handoff_summary",
    workflow_authority_owner="lotus-manage",
    supported_callers=("lotus-manage", "lotus-gateway"),
    surface_scope=("dpm-operations-handoff-ai-evidence",),
    default_workflow_surface="dpm-operations-handoff-ai-evidence",
    execution_task_id="explain.v1",
    required_payload_keys=frozenset(
        {"wave_report_input", "handoff_summary_request", "supportability"}
    ),
)


DPM_EXCEPTION_SUMMARY_V1_SPEC = WorkflowPackPhase1VersionSpec(
    pack_id="dpm_exception_summary.pack",
    pack_family="dpm_exception_summary",
    version="v1",
    owner_repository="lotus-manage",
    owner_service="lotus-manage",
    truth_owner_services=("lotus-manage", "lotus-core", "lotus-risk", "lotus-performance"),
    primary_use_case="dpm_exception_summary",
    workflow_authority_owner="lotus-manage",
    supported_callers=("lotus-manage", "lotus-gateway"),
    surface_scope=("dpm-exception-summary-ai-evidence",),
    default_workflow_surface="dpm-exception-summary-ai-evidence",
    execution_task_id="explain.v1",
    required_payload_keys=frozenset(
        {"exception_summary_input", "exception_summary_request", "supportability"}
    ),
)


PM_QUALITY_SUMMARY_V1_SPEC = WorkflowPackPhase1VersionSpec(
    pack_id="pm_quality_summary.pack",
    pack_family="pm_quality_summary",
    version="v1",
    owner_repository="lotus-manage",
    owner_service="lotus-manage",
    truth_owner_services=("lotus-manage", "lotus-core", "lotus-risk", "lotus-performance"),
    primary_use_case="dpm_pm_operating_quality_summary",
    workflow_authority_owner="lotus-manage",
    supported_callers=("lotus-manage", "lotus-gateway"),
    surface_scope=("dpm-pm-quality-ai-evidence",),
    default_workflow_surface="dpm-pm-quality-ai-evidence",
    execution_task_id="explain.v1",
    required_payload_keys=frozenset({"score_run", "summary_request", "supportability"}),
)
