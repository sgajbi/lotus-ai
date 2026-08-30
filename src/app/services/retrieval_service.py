from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import HTTPException, status

from app.services.runtime_mode_config import resolve_runtime_mode_config
from app.contracts.audit import AuditRecordResponse
from app.contracts.access_control import AuthorizationCapabilityType, AuthorizationDecision
from app.contracts.evidence import ExecutionEvidenceBundle, ExecutionEvidenceDescriptor
from app.contracts.prompts import PromptRolloutRole, PromptSelectionTraceDescriptor
from app.contracts.retrieval import (
    RetrievalExecutionResponse,
    RetrievalExecutionRequest,
    RetrievalSearchRequest,
    RetrievalSearchResponse,
)
from app.contracts.safety import (
    RedactionPosture,
    SafetyExecutionDisposition,
    SafetyExecutionOutcome,
)
from app.contracts.tasks import OutputLabel, TaskCategory, TaskExecutionStatus
from app.services.access_control_authorization import authorize_request, require_authorized
from app.services.audit_store import get_audit_store
from app.services.deployment_split_routing import resolve_retrieval_search_route
from app.services.deployment_split_shared import resolve_deployment_split_posture
from app.services.retrieval_gateway import execute_retrieval_search
from app.services.retrieval_store import get_retrieval_repository


KNOWLEDGE_SEARCH_TASK_ID = "knowledge_search.v1"
KNOWLEDGE_SEARCH_PROMPT_VERSION = "foundation.knowledge_search.v1"


def search_sources(request: RetrievalSearchRequest) -> RetrievalSearchResponse:
    posture = resolve_deployment_split_posture()
    route = resolve_retrieval_search_route(
        effective_stage=posture.effective_stage,
        degraded_findings=posture.retrieval_degraded_findings,
    )
    authorization = require_authorized(
        authorize_request(
            caller_app=request.caller_app,
            capability_type=AuthorizationCapabilityType.RETRIEVAL_EXECUTION,
            tenant_id=request.tenant_id,
            source_ids=request.source_ids,
        )
    )
    effective_source_ids = authorization.effective_source_ids
    enabled_source_ids = {
        source.source_id for source in get_retrieval_repository().list_sources() if source.enabled
    }
    if effective_source_ids and not set(effective_source_ids).issubset(enabled_source_ids):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Requested source_ids include one or more sources that are not enabled.",
        )

    execution = execute_retrieval_search(
        RetrievalExecutionRequest(
            query=request.query,
            caller_app=request.caller_app,
            correlation_id=request.correlation_id,
            source_ids=effective_source_ids,
            limit=request.limit,
        )
    )
    _record_direct_search_audit(
        request=request,
        execution=execution,
        authorization=authorization,
    )
    if execution.status.value == "REJECTED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=execution.message,
        )

    return RetrievalSearchResponse(
        status=execution.status,
        query=request.query,
        execution_stage=execution.execution_stage,
        vector_store=execution.vector_store,
        hits=execution.hits,
        message=f"{execution.message} {route.detail}",
    )


def _record_direct_search_audit(
    *,
    request: RetrievalSearchRequest,
    execution: RetrievalExecutionResponse,
    authorization: AuthorizationDecision,
) -> None:
    hit_refs = [
        {
            "source_id": hit.source_id,
            "document_id": hit.document_id,
            "chunk_id": hit.chunk_id,
            "active_version_id": hit.active_version_id,
            "citation_ref": hit.citation_ref,
        }
        for hit in execution.hits
    ]
    citation_refs = [hit.citation_ref for hit in execution.hits if hit.citation_ref is not None]
    execution_status = (
        TaskExecutionStatus.COMPLETED
        if execution.status.value == "READY"
        else TaskExecutionStatus.REJECTED
    )
    generated_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    get_audit_store().save(
        AuditRecordResponse(
            request_id=f"retrieval_search_{uuid4().hex}",
            execution_status=execution_status,
            task_id=KNOWLEDGE_SEARCH_TASK_ID,
            category=TaskCategory.KNOWLEDGE_SEARCH,
            output_label=OutputLabel.RETRIEVAL_ANSWER,
            caller_app=request.caller_app,
            correlation_id=request.correlation_id,
            requested_by=None,
            tenant_id=request.tenant_id,
            prompt_version=KNOWLEDGE_SEARCH_PROMPT_VERSION,
            prompt_selection=PromptSelectionTraceDescriptor(
                task_id=KNOWLEDGE_SEARCH_TASK_ID,
                prompt_version=KNOWLEDGE_SEARCH_PROMPT_VERSION,
                rollout_role=PromptRolloutRole.ACTIVE,
                selection_reason=(
                    "Direct retrieval search records bounded citation evidence without "
                    "provider prompt execution."
                ),
                active_prompt_version=KNOWLEDGE_SEARCH_PROMPT_VERSION,
            ),
            provider_mode="retrieval",
            provider_id="retrieval-store",
            adapter_kind=None,
            model_id=None,
            safety_mode=resolve_runtime_mode_config().safety_mode,
            redaction_posture=RedactionPosture.MINIMIZATION_REQUIRED,
            enforced_safety_controls=[
                "correlation_and_audit",
                "retrieval_citation_lineage",
                "no_raw_retrieval_payload_audit",
            ],
            safety_outcome=SafetyExecutionOutcome(
                safety_mode=resolve_runtime_mode_config().safety_mode,
                output_label=OutputLabel.RETRIEVAL_ANSWER.value,
                redaction_posture=RedactionPosture.MINIMIZATION_REQUIRED,
                disposition=SafetyExecutionDisposition.ENFORCED_PASSTHROUGH,
                runtime_redaction_active=False,
                enforced_controls=[
                    "correlation_and_audit",
                    "retrieval_citation_lineage",
                    "no_raw_retrieval_payload_audit",
                ],
                control_results=[],
                decision_summary=(
                    "Direct retrieval search audit stores request posture and citation identifiers "
                    "without raw query text or retrieved snippets."
                ),
            ),
            authorization=authorization,
            generated_at=generated_at,
            stubbed=False,
            context_summary=(
                "Direct retrieval search request; raw query and retrieved snippets are omitted "
                "from audit evidence."
            ),
            context_keys=[
                "authorized_source_ids",
                "correlation_id",
                "limit",
                "query_length",
                "requested_source_ids",
            ],
            source_refs=citation_refs,
            result_preview=(
                f"Retrieval search {execution.status.value.lower()} with {len(execution.hits)} "
                f"bounded hit(s) over {len(authorization.effective_source_ids)} authorized source(s)."
            ),
            structured_output={
                "execution_stage": execution.execution_stage.value,
                "retrieval_status": execution.status.value,
                "query_length": len(request.query),
                "requested_source_ids": request.source_ids,
                "authorized_source_ids": authorization.effective_source_ids,
                "limit": request.limit,
                "hit_count": len(execution.hits),
                "hit_refs": hit_refs,
                "raw_query_recorded": False,
                "raw_snippets_recorded": False,
            },
            evidence=ExecutionEvidenceBundle(
                descriptors=[
                    ExecutionEvidenceDescriptor(
                        evidence_type="retrieval_search_request",
                        summary=(
                            "Direct retrieval search request was audited with bounded caller, "
                            "authorization, execution-stage, and citation evidence."
                        ),
                        attributes={
                            "execution_stage": execution.execution_stage.value,
                            "hit_count": len(execution.hits),
                            "raw_query_recorded": False,
                            "raw_snippets_recorded": False,
                        },
                    )
                ]
            ),
        )
    )
