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
