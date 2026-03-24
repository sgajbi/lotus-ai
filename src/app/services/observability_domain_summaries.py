from __future__ import annotations

from dataclasses import dataclass

from app.config import settings
from app.contracts.observability import (
    DomainIncidentSummaryResponse,
    ObservabilityBreakdownSupport,
    ObservabilityDomainId,
)
from app.services.async_runtime_status import build_async_runtime_status
from app.services.eval_status import build_evaluation_runtime_status
from app.services.observability_shared import (
    build_domain_telemetry_summary,
    build_incident_evidence_item,
)
from app.services.prompt_evidence_readiness import build_prompt_evidence_readiness
from app.services.prompt_governance_status import build_prompt_governance_status_summary
from app.services.prompt_status import build_prompt_runtime_status
from app.services.provider_operations_status import build_provider_operations_status
from app.services.retrieval_activation_readiness import build_retrieval_activation_readiness
from app.services.retrieval_execution_status import build_retrieval_execution_status
from app.services.runtime_readiness import get_retrieval_store_runtime_status
from app.services.safety_evidence_readiness import build_safety_evidence_readiness
from app.services.safety_governance_status import build_safety_governance_status
from app.services.safety_status import build_safety_runtime_status


@dataclass(frozen=True)
class ObservabilityDomainBundle:
    summary: DomainIncidentSummaryResponse


def build_provider_observability_bundle() -> ObservabilityDomainBundle:
    provider_operations = build_provider_operations_status()
    degraded_findings = list(provider_operations.blocking_reasons)
    telemetry = build_domain_telemetry_summary(
        domain_id=ObservabilityDomainId.PROVIDER,
        telemetry_sources=[
            "provider_operations_status",
            "correlation_middleware",
            "prometheus",
        ],
        source_available=True,
        degraded_findings=degraded_findings,
        stale=False,
        incident_evidence_supported=True,
        breakdown_support=ObservabilityBreakdownSupport(
            caller_app_supported=True,
            tenant_supported=True,
            capability_supported=True,
        ),
        incident_signal_count=len(degraded_findings),
        summary=[
            f"Provider operations currently report `{provider_operations.operations_state.value}` posture.",
            "Provider incident summaries are grounded in runtime provider operations state rather than runbook-only prose.",
        ],
    )
    incident_items = [
        build_incident_evidence_item(
            domain_id=ObservabilityDomainId.PROVIDER,
            evidence_id="provider_operations_incident_state",
            source_available=True,
            stale=False,
            degraded_findings=degraded_findings,
            durable=settings.provider_operations_store_mode == "sqlalchemy",
            summary=(
                "Provider operations state captures rollout, quota, budget, and degradation findings for current incident review."
            ),
        )
    ]
    return ObservabilityDomainBundle(
        summary=DomainIncidentSummaryResponse(
            service=settings.service_name,
            version=settings.service_version,
            domain_id=ObservabilityDomainId.PROVIDER,
            telemetry=telemetry,
            incident_evidence_items=incident_items,
            linked_endpoints=[
                "/platform/providers/operations-status",
                "/platform/providers/governance-status",
                "/platform/providers/runbook-readiness",
            ],
            summary=[
                provider_operations.summary[0],
                (
                    provider_operations.blocking_reasons[0]
                    if provider_operations.blocking_reasons
                    else "No current provider blocking reason is active."
                ),
            ],
        )
    )


def build_retrieval_observability_bundle() -> ObservabilityDomainBundle:
    retrieval_execution = build_retrieval_execution_status()
    activation_readiness = build_retrieval_activation_readiness()
    store_status = get_retrieval_store_runtime_status()
    degraded_findings = list(activation_readiness.blocking_findings)
    telemetry = build_domain_telemetry_summary(
        domain_id=ObservabilityDomainId.RETRIEVAL,
        telemetry_sources=[
            "retrieval_execution_status",
            "retrieval_activation_readiness",
            "correlation_middleware",
            "prometheus",
        ],
        source_available=store_status.status == "READY"
        or settings.retrieval_store_mode == "memory",
        degraded_findings=degraded_findings,
        stale=False,
        incident_evidence_supported=True,
        breakdown_support=ObservabilityBreakdownSupport(
            caller_app_supported=True,
            tenant_supported=True,
            capability_supported=True,
        ),
        incident_signal_count=len(degraded_findings),
        summary=[
            retrieval_execution.message,
            "Retrieval incident summaries are grounded in searchable-corpus, evidence, and activation state.",
        ],
    )
    incident_items = [
        build_incident_evidence_item(
            domain_id=ObservabilityDomainId.RETRIEVAL,
            evidence_id="retrieval_live_search_activation_state",
            source_available=store_status.status == "READY"
            or settings.retrieval_store_mode == "memory",
            stale=False,
            degraded_findings=degraded_findings,
            durable=settings.retrieval_store_mode == "sqlalchemy"
            and store_status.status == "READY",
            summary="Retrieval activation state captures searchable corpus, reindex, rollback, and evidence blockers for current incident review.",
        )
    ]
    return ObservabilityDomainBundle(
        summary=DomainIncidentSummaryResponse(
            service=settings.service_name,
            version=settings.service_version,
            domain_id=ObservabilityDomainId.RETRIEVAL,
            telemetry=telemetry,
            incident_evidence_items=incident_items,
            linked_endpoints=[
                "/platform/retrieval/execution-status",
                "/platform/retrieval/activation-readiness",
                "/platform/retrieval/governance-status",
            ],
            summary=[
                retrieval_execution.message,
                (
                    activation_readiness.blocking_findings[0]
                    if activation_readiness.blocking_findings
                    else "Retrieval activation currently has no incident blocker."
                ),
            ],
        )
    )


def build_async_observability_bundle() -> ObservabilityDomainBundle:
    async_runtime = build_async_runtime_status()
    degraded_findings = list(async_runtime.degraded_findings)
    telemetry = build_domain_telemetry_summary(
        domain_id=ObservabilityDomainId.ASYNC,
        telemetry_sources=["async_runtime_status", "async_delivery_queue", "prometheus"],
        source_available=True,
        degraded_findings=degraded_findings,
        stale=False,
        incident_evidence_supported=True,
        breakdown_support=ObservabilityBreakdownSupport(
            caller_app_supported=True,
            tenant_supported=False,
            capability_supported=True,
        ),
        incident_signal_count=len(degraded_findings),
        summary=[
            async_runtime.message,
            "Async incident summaries are grounded in queue backlog, worker identity, and degraded-fallback state.",
        ],
    )
    incident_items = [
        build_incident_evidence_item(
            domain_id=ObservabilityDomainId.ASYNC,
            evidence_id="async_worker_fleet_state",
            source_available=True,
            stale=False,
            degraded_findings=degraded_findings,
            durable=settings.async_runtime_store_mode == "sqlalchemy",
            summary="Async worker-fleet state captures queue backlog, worker visibility, drain mode, and explicit degraded fallback.",
        )
    ]
    return ObservabilityDomainBundle(
        summary=DomainIncidentSummaryResponse(
            service=settings.service_name,
            version=settings.service_version,
            domain_id=ObservabilityDomainId.ASYNC,
            telemetry=telemetry,
            incident_evidence_items=incident_items,
            linked_endpoints=[
                "/platform/async/runtime-status",
                "/platform/async/activation-readiness",
                "/platform/async/governance-status",
            ],
            summary=[
                async_runtime.message,
                (
                    async_runtime.degraded_findings[0]
                    if async_runtime.degraded_findings
                    else "Async runtime currently exposes no active degraded finding."
                ),
            ],
        )
    )


def build_evaluation_observability_bundle() -> ObservabilityDomainBundle:
    evaluation_runtime = build_evaluation_runtime_status()
    degraded_findings = [
        gate.notes[0]
        for gate in evaluation_runtime.approval_gates
        if not gate.approval_ready and gate.notes
    ]
    telemetry = build_domain_telemetry_summary(
        domain_id=ObservabilityDomainId.EVALUATION,
        telemetry_sources=["evaluation_runtime_status", "evaluation_runtime_store"],
        source_available=True,
        degraded_findings=degraded_findings,
        stale=any(
            gate.evidence_state == "RUNTIME_STALE" for gate in evaluation_runtime.approval_gates
        ),
        incident_evidence_supported=True,
        breakdown_support=ObservabilityBreakdownSupport(
            caller_app_supported=True,
            tenant_supported=False,
            capability_supported=True,
        ),
        incident_signal_count=len(degraded_findings),
        summary=[
            evaluation_runtime.message,
            "Evaluation incident summaries are grounded in runtime-backed approval-gate and run history.",
        ],
    )
    incident_items = [
        build_incident_evidence_item(
            domain_id=ObservabilityDomainId.EVALUATION,
            evidence_id="evaluation_approval_gate_state",
            source_available=True,
            stale=any(
                gate.evidence_state == "RUNTIME_STALE" for gate in evaluation_runtime.approval_gates
            ),
            degraded_findings=degraded_findings,
            durable=True,
            summary="Evaluation runtime status captures approval-gate freshness, partial evidence, and failing runtime verdict posture.",
        )
    ]
    return ObservabilityDomainBundle(
        summary=DomainIncidentSummaryResponse(
            service=settings.service_name,
            version=settings.service_version,
            domain_id=ObservabilityDomainId.EVALUATION,
            telemetry=telemetry,
            incident_evidence_items=incident_items,
            linked_endpoints=[
                "/platform/evals/runtime-status",
                "/platform/evals/runs",
                "/platform/evals/catalog",
            ],
            summary=[
                evaluation_runtime.message,
                degraded_findings[0]
                if degraded_findings
                else "Evaluation approval posture currently exposes no active incident finding.",
            ],
        )
    )


def build_prompt_observability_bundle() -> ObservabilityDomainBundle:
    prompt_runtime = build_prompt_runtime_status()
    prompt_governance = build_prompt_governance_status_summary()
    prompt_evidence = build_prompt_evidence_readiness()
    degraded_findings = list(prompt_governance.activation_readiness.blocking_findings)
    stale = prompt_evidence.approval_gate.evidence_state == "RUNTIME_STALE"
    telemetry = build_domain_telemetry_summary(
        domain_id=ObservabilityDomainId.PROMPT,
        telemetry_sources=[
            "prompt_runtime_status",
            "prompt_governance_status",
            "prompt_control_history",
        ],
        source_available=True,
        degraded_findings=degraded_findings,
        stale=stale,
        incident_evidence_supported=True,
        breakdown_support=ObservabilityBreakdownSupport(
            caller_app_supported=True,
            tenant_supported=False,
            capability_supported=True,
        ),
        incident_signal_count=(
            prompt_runtime.candidate_prompt_count + prompt_governance.blocking_area_count
        ),
        summary=[
            "Prompt observability now reuses rollout state, control history, and approval evidence posture.",
            "Prompt incident summaries are grounded in blocked activation findings and rollback-ready durable control history.",
        ],
    )
    incident_items = [
        build_incident_evidence_item(
            domain_id=ObservabilityDomainId.PROMPT,
            evidence_id="prompt_rollout_approval_state",
            source_available=True,
            stale=stale,
            degraded_findings=degraded_findings,
            durable=settings.prompt_store_mode == "sqlalchemy",
            summary="Prompt rollout incident evidence captures blocked promotions, rollback lineage, and runtime-backed approval-gate posture.",
        )
    ]
    return ObservabilityDomainBundle(
        summary=DomainIncidentSummaryResponse(
            service=settings.service_name,
            version=settings.service_version,
            domain_id=ObservabilityDomainId.PROMPT,
            telemetry=telemetry,
            incident_evidence_items=incident_items,
            linked_endpoints=[
                "/platform/prompts/runtime-status",
                "/platform/prompts/control-history",
                "/platform/prompts/governance-status",
            ],
            summary=[
                prompt_governance.governance_summary[0],
                degraded_findings[0]
                if degraded_findings
                else "Prompt rollout currently exposes no active incident blocker.",
            ],
        )
    )


def build_safety_observability_bundle() -> ObservabilityDomainBundle:
    safety_runtime = build_safety_runtime_status()
    safety_governance = build_safety_governance_status()
    safety_evidence = build_safety_evidence_readiness()
    degraded_findings = list(safety_governance.governance_summary)
    stale = safety_evidence.approval_gate.evidence_state == "RUNTIME_STALE"
    telemetry = build_domain_telemetry_summary(
        domain_id=ObservabilityDomainId.SAFETY,
        telemetry_sources=[
            "safety_runtime_status",
            "safety_governance_status",
            "audit_repository",
            "execution_evidence",
        ],
        source_available=True,
        degraded_findings=[] if safety_runtime.runtime_redaction_active else degraded_findings,
        stale=stale,
        incident_evidence_supported=True,
        breakdown_support=ObservabilityBreakdownSupport(
            caller_app_supported=True,
            tenant_supported=True,
            capability_supported=True,
        ),
        incident_signal_count=safety_governance.blocking_area_count,
        summary=[
            "Safety observability reuses runtime enforcement posture, audit-backed evidence, and governed approval readiness.",
            "Safety incident summaries are grounded in blocked, degraded, and documented-only enforcement posture rather than policy prose alone.",
        ],
    )
    incident_items = [
        build_incident_evidence_item(
            domain_id=ObservabilityDomainId.SAFETY,
            evidence_id="safety_runtime_enforcement_state",
            source_available=True,
            stale=stale,
            degraded_findings=[] if safety_runtime.runtime_redaction_active else degraded_findings,
            durable=True,
            summary="Safety incident evidence captures runtime enforcement disposition plus durable audit and execution-evidence traceability.",
        )
    ]
    return ObservabilityDomainBundle(
        summary=DomainIncidentSummaryResponse(
            service=settings.service_name,
            version=settings.service_version,
            domain_id=ObservabilityDomainId.SAFETY,
            telemetry=telemetry,
            incident_evidence_items=incident_items,
            linked_endpoints=[
                "/platform/safety/runtime-status",
                "/platform/safety/evidence-readiness",
                "/platform/safety/governance-status",
            ],
            summary=[
                safety_governance.governance_summary[0],
                safety_governance.governance_summary[2],
            ],
        )
    )


def build_current_observability_bundles() -> list[ObservabilityDomainBundle]:
    return [
        build_provider_observability_bundle(),
        build_retrieval_observability_bundle(),
        build_async_observability_bundle(),
        build_evaluation_observability_bundle(),
        build_prompt_observability_bundle(),
        build_safety_observability_bundle(),
    ]
