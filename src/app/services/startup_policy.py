from __future__ import annotations

import logging
from dataclasses import dataclass

from app.config import settings
from app.services.runtime_readiness import (
    get_audit_store_runtime_status,
    get_retrieval_store_runtime_status,
    get_workflow_pack_registry_store_runtime_status,
    get_workflow_pack_queue_event_store_runtime_status,
    get_workflow_pack_run_store_runtime_status,
    get_workflow_pack_task_flow_store_runtime_status,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StartupReadinessEvaluation:
    blocking: bool
    findings: list[str]


def evaluate_startup_readiness() -> StartupReadinessEvaluation:
    findings: list[str] = []
    blocking = False

    audit_status = get_audit_store_runtime_status()
    retrieval_status = get_retrieval_store_runtime_status()
    workflow_pack_registry_status = get_workflow_pack_registry_store_runtime_status()
    workflow_pack_run_status = get_workflow_pack_run_store_runtime_status()
    workflow_pack_task_flow_status = get_workflow_pack_task_flow_store_runtime_status()
    workflow_pack_queue_event_status = get_workflow_pack_queue_event_store_runtime_status()

    if audit_status.status != "READY":
        findings.append(f"audit store: {audit_status.detail}")
    if retrieval_status.status != "READY":
        findings.append(f"retrieval store: {retrieval_status.detail}")
    if workflow_pack_registry_status.status != "READY":
        findings.append(f"workflow-pack registry store: {workflow_pack_registry_status.detail}")
    if workflow_pack_run_status.status != "READY":
        findings.append(f"workflow-pack run store: {workflow_pack_run_status.detail}")
    if workflow_pack_task_flow_status.status != "READY":
        findings.append(f"workflow-pack task-flow store: {workflow_pack_task_flow_status.detail}")
    if workflow_pack_queue_event_status.status != "READY":
        findings.append(
            f"workflow-pack queue-event store: {workflow_pack_queue_event_status.detail}"
        )

    findings.extend(_provider_protection_findings())

    if settings.startup_readiness_policy == "enforce" and findings:
        blocking = True

    return StartupReadinessEvaluation(blocking=blocking, findings=findings)


def apply_startup_readiness_policy() -> StartupReadinessEvaluation:
    evaluation = evaluate_startup_readiness()
    if evaluation.findings:
        for finding in evaluation.findings:
            logger.warning("startup readiness finding: %s", finding)
    if evaluation.blocking:
        raise RuntimeError(
            "lotus-ai startup readiness policy blocked startup: " + "; ".join(evaluation.findings)
        )
    return evaluation


def _provider_protection_findings() -> list[str]:
    """Promoted live mode must not run unprotected (issue #153 S2).

    The profile enables the enforcement flags but never invents economic
    limits - a promoted deployment with live provider mode and missing
    limits, disabled protections, or per-process state is a finding, and
    the promoted startup policy (enforce) makes findings blocking.
    """

    if settings.runtime_profile != "promoted":
        return []
    findings: list[str] = []
    if settings.workflow_pack_admission_store_mode != "sqlalchemy":
        findings.append(
            "workflow-pack admission store: per-process memory leases cannot bound "
            "queue admission across replicas in the promoted profile"
        )
    if settings.provider_mode not in {"openai", "local_openai_compatible"}:
        return findings
    if not settings.live_text_quota_enforced:
        findings.append("provider quota: enforcement is disabled in promoted live mode")
    elif not any(
        (
            settings.live_text_default_quota_limit is not None,
            settings.live_text_task_quota_limits.strip(),
            settings.live_text_caller_quota_limits.strip(),
            settings.live_text_tenant_quota_limits.strip(),
        )
    ):
        findings.append("provider quota: enforcement is enabled but no quota limits are configured")
    if not settings.live_text_budget_enforced:
        findings.append("provider budget: enforcement is disabled in promoted live mode")
    elif settings.live_text_hard_budget_usd is None:
        findings.append(
            "provider budget: enforcement is enabled but no hard budget limit is configured"
        )
    if not settings.live_text_degradation_enforced:
        findings.append(
            "provider degradation: breaker enforcement is disabled in promoted live mode"
        )
    if settings.provider_operations_store_mode != "sqlalchemy":
        findings.append(
            "provider operations store: per-process memory state cannot bound quota, "
            "budget, or breaker behaviour across replicas in promoted live mode"
        )
    return findings
