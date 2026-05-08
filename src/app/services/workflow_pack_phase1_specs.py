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
