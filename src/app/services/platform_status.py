from __future__ import annotations

from types import SimpleNamespace

from app.config import settings
from app.contracts.platform import PlatformRuntimeStatusResponse
from app.retrieval.policy import VECTOR_STORE_STRATEGY
from app.services.capability_catalog import build_capability_catalog
from app.services.prompt_registry import list_registered_prompts
from app.services.runtime_readiness import (
    get_audit_store_runtime_status,
    get_retrieval_store_runtime_status,
)
from app.services.safety_status import build_safety_runtime_status


def build_platform_runtime_status(app_state: object | None = None) -> PlatformRuntimeStatusResponse:
    capabilities = build_capability_catalog()
    prompts = list_registered_prompts()
    audit_store = get_audit_store_runtime_status()
    retrieval_store = get_retrieval_store_runtime_status()
    safety_runtime = build_safety_runtime_status()
    state = app_state if app_state is not None else SimpleNamespace()
    return PlatformRuntimeStatusResponse(
        service=settings.service_name,
        version=settings.service_version,
        delivery_phase=settings.delivery_phase,
        startup_readiness_policy=settings.startup_readiness_policy,
        readiness_probe_policy=settings.readiness_probe_policy,
        provider_mode=settings.provider_mode,
        retrieval_mode=settings.retrieval_mode,
        embedding_provider_mode=settings.embedding_provider_mode,
        safety_mode=settings.safety_mode,
        prompt_store_mode=settings.prompt_store_mode,
        safety_runtime=safety_runtime,
        audit_store=audit_store,
        retrieval_store=retrieval_store,
        database_configured=audit_store.database_configured or retrieval_store.database_configured,
        prompt_count=len(prompts),
        capability_count=len(capabilities.tasks),
        vector_store=VECTOR_STORE_STRATEGY,
        migration_contract_enforced=True,
        startup_readiness_blocking=bool(getattr(state, "startup_readiness_blocking", False)),
        startup_readiness_warnings=list(getattr(state, "startup_readiness_findings", [])),
    )
