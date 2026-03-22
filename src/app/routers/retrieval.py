from __future__ import annotations

from fastapi import APIRouter

from app.contracts.retrieval import (
    RetrievalActivationReadinessResponse,
    RetrievalChunkCatalogResponse,
    RetrievalDocumentCatalogResponse,
    RetrievalDocumentGovernanceResponse,
    RetrievalEvidenceReadinessResponse,
    RetrievalIndexJobCatalogResponse,
    RetrievalIndexJobDetailResponse,
    RetrievalIndexStatusResponse,
    RetrievalIndexingPolicyResponse,
    RetrievalExecutionStatusResponse,
    RetrievalGovernanceStatusResponse,
    RetrievalRuntimeStatusResponse,
    RetrievalRunbookReadinessResponse,
    RetrievalSearchRequest,
    RetrievalSearchResponse,
    RetrievalSourceCatalogResponse,
    RetrievalSourceGovernanceResponse,
)
from app.retrieval.source_registry import list_retrieval_sources
from app.services.retrieval_catalog_service import (
    get_chunks_for_document,
    get_retrieval_indexing_policy,
    get_retrieval_runtime_status,
    get_retrieval_job_detail_or_raise,
    get_retrieval_job_catalog,
    get_documents_for_source,
    get_retrieval_document_governance,
    get_retrieval_index_status,
    get_retrieval_source_governance,
)
from app.services.retrieval_activation_readiness import build_retrieval_activation_readiness
from app.services.retrieval_evidence_readiness import build_retrieval_evidence_readiness
from app.services.retrieval_execution_status import build_retrieval_execution_status
from app.services.retrieval_governance_status import build_retrieval_governance_status
from app.services.retrieval_runbook_readiness import build_retrieval_runbook_readiness
from app.services.retrieval_service import search_sources

router = APIRouter(prefix="/platform/retrieval", tags=["retrieval"])


@router.get(
    "/sources",
    response_model=RetrievalSourceCatalogResponse,
    operation_id="listRetrievalSources",
    summary="List approved retrieval sources",
    description=(
        "Returns the approved retrieval sources known to lotus-ai, together with the current "
        "retrieval mode and planned vector-store strategy."
    ),
    responses={
        200: {"description": "Retrieval source catalog returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def list_retrieval_sources_route() -> RetrievalSourceCatalogResponse:
    return list_retrieval_sources()


@router.get(
    "/source-governance",
    response_model=RetrievalSourceGovernanceResponse,
    operation_id="getRetrievalSourceGovernance",
    summary="Get retrieval source governance",
    description=(
        "Returns the derived governance posture for each registered retrieval source, "
        "including whether the source is currently enabled for catalog-only retrieval or only staged."
    ),
    responses={
        200: {"description": "Retrieval source governance returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_retrieval_source_governance_route() -> RetrievalSourceGovernanceResponse:
    return get_retrieval_source_governance()


@router.get(
    "/document-governance",
    response_model=RetrievalDocumentGovernanceResponse,
    operation_id="getRetrievalDocumentGovernance",
    summary="Get retrieval document governance",
    description=(
        "Returns the derived governance posture for each registered retrieval document, "
        "including whether the document is currently promoted into searchable retrieval scope."
    ),
    responses={
        200: {"description": "Retrieval document governance returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_retrieval_document_governance_route() -> RetrievalDocumentGovernanceResponse:
    return get_retrieval_document_governance()


@router.get(
    "/index-status",
    response_model=RetrievalIndexStatusResponse,
    operation_id="getRetrievalIndexStatus",
    summary="Get retrieval indexing status",
    description=(
        "Returns source-level indexing status for the approved retrieval corpus currently known "
        "to lotus-ai."
    ),
    responses={
        200: {"description": "Retrieval indexing status returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_retrieval_index_status_route() -> RetrievalIndexStatusResponse:
    return get_retrieval_index_status()


@router.get(
    "/runtime-status",
    response_model=RetrievalRuntimeStatusResponse,
    operation_id="getRetrievalRuntimeStatus",
    summary="Get retrieval runtime status",
    description=(
        "Returns the active retrieval execution and persistence posture for lotus-ai, including "
        "which metadata store is currently backing the retrieval catalog."
    ),
    responses={
        200: {"description": "Retrieval runtime status returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_retrieval_runtime_status_route() -> RetrievalRuntimeStatusResponse:
    return get_retrieval_runtime_status()


@router.get(
    "/execution-status",
    response_model=RetrievalExecutionStatusResponse,
    operation_id="getRetrievalExecutionStatus",
    summary="Get retrieval execution status",
    description=(
        "Returns the staged retrieval execution posture for lotus-ai, distinguishing approved "
        "catalog contracts from live search or indexing execution."
    ),
    responses={
        200: {"description": "Retrieval execution status returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_retrieval_execution_status_route() -> RetrievalExecutionStatusResponse:
    return build_retrieval_execution_status()


@router.get(
    "/activation-readiness",
    response_model=RetrievalActivationReadinessResponse,
    operation_id="getRetrievalActivationReadiness",
    summary="Get retrieval activation readiness",
    description=(
        "Returns whether lotus-ai live retrieval execution is currently ready for activation, "
        "along with the blocking findings and governed activation path for future rollout."
    ),
    responses={
        200: {"description": "Retrieval activation readiness returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_retrieval_activation_readiness_route() -> RetrievalActivationReadinessResponse:
    return build_retrieval_activation_readiness()


@router.get(
    "/runbook-readiness",
    response_model=RetrievalRunbookReadinessResponse,
    operation_id="getRetrievalRunbookReadiness",
    summary="Get retrieval runbook readiness",
    description=(
        "Returns the operational runbook readiness required before lotus-ai live retrieval "
        "execution can be activated in a governed environment."
    ),
    responses={
        200: {"description": "Retrieval runbook readiness returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_retrieval_runbook_readiness_route() -> RetrievalRunbookReadinessResponse:
    return build_retrieval_runbook_readiness()


@router.get(
    "/evidence-readiness",
    response_model=RetrievalEvidenceReadinessResponse,
    operation_id="getRetrievalEvidenceReadiness",
    summary="Get retrieval evidence readiness",
    description=(
        "Returns whether lotus-ai retrieval rollout is currently supported by the required "
        "evaluation, citation, reindex, and rollback evidence for future live activation."
    ),
    responses={
        200: {"description": "Retrieval evidence readiness returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_retrieval_evidence_readiness_route() -> RetrievalEvidenceReadinessResponse:
    return build_retrieval_evidence_readiness()


@router.get(
    "/governance-status",
    response_model=RetrievalGovernanceStatusResponse,
    operation_id="getRetrievalGovernanceStatus",
    summary="Get retrieval governance status",
    description=(
        "Returns the combined technical and operational governance posture for lotus-ai live "
        "retrieval execution so rollout reviewers can assess activation readiness in one view."
    ),
    responses={
        200: {"description": "Retrieval governance status returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_retrieval_governance_status_route() -> RetrievalGovernanceStatusResponse:
    return build_retrieval_governance_status()


@router.get(
    "/indexing-policy",
    response_model=RetrievalIndexingPolicyResponse,
    operation_id="getRetrievalIndexingPolicy",
    summary="Get retrieval indexing policy",
    description=(
        "Returns the governed retrieval indexing posture for lotus-ai, including chunking, "
        "embedding, and vector persistence strategy labels for the current phase."
    ),
    responses={
        200: {"description": "Retrieval indexing policy returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_retrieval_indexing_policy_route() -> RetrievalIndexingPolicyResponse:
    return get_retrieval_indexing_policy()


@router.get(
    "/index-jobs",
    response_model=RetrievalIndexJobCatalogResponse,
    operation_id="listRetrievalIndexJobs",
    summary="List retrieval indexing jobs",
    description=(
        "Returns the currently known retrieval indexing jobs for the staged corpus. "
        "This gives platform visibility into indexing readiness before live vector indexing is enabled."
    ),
    responses={
        200: {"description": "Retrieval indexing jobs returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def list_retrieval_index_jobs_route() -> RetrievalIndexJobCatalogResponse:
    return get_retrieval_job_catalog()


@router.get(
    "/index-jobs/{job_id}",
    response_model=RetrievalIndexJobDetailResponse,
    operation_id="getRetrievalIndexJob",
    summary="Get retrieval indexing job detail",
    description=(
        "Returns the detailed staged execution plan for a retrieval indexing job, including the "
        "current lifecycle stage of each indexing step."
    ),
    responses={
        200: {"description": "Retrieval indexing job detail returned successfully."},
        404: {"description": "Retrieval indexing job not found."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_retrieval_index_job_route(job_id: str) -> RetrievalIndexJobDetailResponse:
    return get_retrieval_job_detail_or_raise(job_id)


@router.get(
    "/sources/{source_id}/documents",
    response_model=RetrievalDocumentCatalogResponse,
    operation_id="listRetrievalSourceDocuments",
    summary="List staged retrieval documents for a source",
    description=(
        "Returns the currently staged retrieval documents associated with a source identifier."
    ),
    responses={
        200: {"description": "Retrieval document catalog returned successfully."},
        404: {"description": "Retrieval source not found."},
        500: {"description": "Unexpected server error."},
    },
)
async def list_retrieval_documents_route(source_id: str) -> RetrievalDocumentCatalogResponse:
    return get_documents_for_source(source_id)


@router.get(
    "/documents/{document_id}/chunks",
    response_model=RetrievalChunkCatalogResponse,
    operation_id="listRetrievalDocumentChunks",
    summary="List staged retrieval chunks for a document",
    description=(
        "Returns the currently staged retrieval chunks associated with a retrieval document identifier."
    ),
    responses={
        200: {"description": "Retrieval chunk catalog returned successfully."},
        404: {"description": "Retrieval document not found."},
        500: {"description": "Unexpected server error."},
    },
)
async def list_retrieval_chunks_route(document_id: str) -> RetrievalChunkCatalogResponse:
    return get_chunks_for_document(document_id)


@router.post(
    "/search",
    response_model=RetrievalSearchResponse,
    operation_id="searchRetrievalSources",
    summary="Search approved retrieval sources",
    description=(
        "Searches approved lotus-ai retrieval sources. In the current phase, this endpoint "
        "returns a governed conflict response until live retrieval is enabled."
    ),
    responses={
        200: {"description": "Retrieval search completed successfully."},
        409: {"description": "Retrieval is not enabled or requested sources are not enabled."},
        500: {"description": "Unexpected server error."},
    },
)
async def search_retrieval_sources_route(
    request: RetrievalSearchRequest,
) -> RetrievalSearchResponse:
    return search_sources(request)
