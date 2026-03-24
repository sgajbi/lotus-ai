from __future__ import annotations

from app.config import settings
from app.contracts.retrieval import (
    RetrievalExecutionStage,
    RetrievalExecutionStatusResponse,
)
from app.retrieval.document_governance import build_retrieval_document_governance
from app.retrieval.policy import VECTOR_STORE_STRATEGY
from app.services.deployment_split_routing import resolve_retrieval_search_route
from app.services.deployment_split_shared import resolve_deployment_split_posture
from app.services.retrieval_embedding_runtime import build_retrieval_embedding_runtime
from app.services.runtime_readiness import get_retrieval_store_runtime_status


def build_retrieval_execution_status() -> RetrievalExecutionStatusResponse:
    posture = resolve_deployment_split_posture()
    embedding_runtime = build_retrieval_embedding_runtime()
    route = resolve_retrieval_search_route(
        effective_stage=posture.effective_stage,
        degraded_findings=posture.retrieval_degraded_findings,
    )
    if settings.retrieval_mode != "enabled":
        return RetrievalExecutionStatusResponse(
            service=settings.service_name,
            delivery_phase=settings.delivery_phase,
            retrieval_mode=settings.retrieval_mode,
            execution_stage=RetrievalExecutionStage.SEARCH_DISABLED,
            vector_store=VECTOR_STORE_STRATEGY,
            live_search_enabled=False,
            live_indexing_enabled=True,
            embedding_execution_enabled=embedding_runtime.embedding_execution_enabled,
            embedding_provider_id=embedding_runtime.embedding_provider_id,
            embedding_model_id=embedding_runtime.embedding_model_id,
            owning_plane=route.owning_plane,
            route_mode=route.route_mode,
            rollback_target_stage=route.rollback_target_stage,
            split_route_degraded=route.degraded,
            split_route_findings=route.degraded_findings,
            message=(
                "Live retrieval search remains disabled, but runtime-backed retrieval indexing is "
                f"enabled for allowlisted async jobs. {route.detail}"
            ),
        )

    store_status = get_retrieval_store_runtime_status()
    if store_status.status != "READY":
        return RetrievalExecutionStatusResponse(
            service=settings.service_name,
            delivery_phase=settings.delivery_phase,
            retrieval_mode=settings.retrieval_mode,
            execution_stage=RetrievalExecutionStage.INDEXING_DISABLED,
            vector_store=VECTOR_STORE_STRATEGY,
            live_search_enabled=False,
            live_indexing_enabled=True,
            embedding_execution_enabled=embedding_runtime.embedding_execution_enabled,
            embedding_provider_id=embedding_runtime.embedding_provider_id,
            embedding_model_id=embedding_runtime.embedding_model_id,
            owning_plane=route.owning_plane,
            route_mode=route.route_mode,
            rollback_target_stage=route.rollback_target_stage,
            split_route_degraded=route.degraded,
            split_route_findings=route.degraded_findings,
            message=(
                "Live retrieval search is configured but unavailable because the retrieval store "
                f"is not ready: {store_status.detail} {route.detail}"
            ),
        )

    document_governance = build_retrieval_document_governance()
    searchable_document_count = document_governance.searchable_document_count
    index_pending_document_count = document_governance.index_pending_document_count
    blocked_document_count = document_governance.blocked_document_count
    if searchable_document_count > 0:
        message = (
            "Retrieval mode is enabled and retrieval requests resolve through the live indexed "
            f"search path over {searchable_document_count} searchable promoted document(s)."
        )
    elif index_pending_document_count > 0:
        message = (
            "Retrieval mode is enabled and the live indexed search path is active, but no "
            "promoted indexed documents are currently searchable because indexing is still pending "
            f"for {index_pending_document_count} document(s)."
        )
    elif blocked_document_count > 0:
        message = (
            "Retrieval mode is enabled and the live indexed search path is active, but no "
            "documents are currently searchable because promoted corpus content has been rolled "
            "back or remains blocked by source posture."
        )
    else:
        message = (
            "Retrieval mode is enabled and the live indexed search path is active, but no "
            "searchable corpus content is currently registered."
        )

    return RetrievalExecutionStatusResponse(
        service=settings.service_name,
        delivery_phase=settings.delivery_phase,
        retrieval_mode=settings.retrieval_mode,
        execution_stage=RetrievalExecutionStage.LIVE_SEARCH,
        vector_store=VECTOR_STORE_STRATEGY,
        live_search_enabled=True,
        live_indexing_enabled=True,
        embedding_execution_enabled=embedding_runtime.embedding_execution_enabled,
        embedding_provider_id=embedding_runtime.embedding_provider_id,
        embedding_model_id=embedding_runtime.embedding_model_id,
        owning_plane=route.owning_plane,
        route_mode=route.route_mode,
        rollback_target_stage=route.rollback_target_stage,
        split_route_degraded=route.degraded,
        split_route_findings=route.degraded_findings,
        message=f"{message} {route.detail}",
    )
