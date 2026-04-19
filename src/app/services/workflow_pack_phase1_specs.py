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
