from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

from app.config import settings
from app.contracts.platform import PlatformRuntimeStatusResponse
from app.retrieval.policy import VECTOR_STORE_STRATEGY
from app.services.async_governance_status_service import build_async_governance_status
from app.services.async_runtime_status import build_async_runtime_status
from app.services.capability_catalog import build_capability_catalog
from app.services.eval_status import build_evaluation_runtime_status
from app.services.prompt_governance_status import build_prompt_governance_status_summary
from app.services.prompt_registry import list_registered_prompts
from app.services.prompt_status import build_prompt_runtime_status
from app.services.provider_governance_status import build_provider_governance_status
from app.services.retrieval_governance_status import build_retrieval_governance_status
from app.services.runtime_readiness import (
    get_audit_store_runtime_status,
    get_retrieval_store_runtime_status,
)
from app.services.safety_status import build_safety_runtime_status


@dataclass(frozen=True)
class StartupReadinessState:
    blocking: bool
    warnings: list[str]


def _resolve_startup_readiness_state(app_state: object | None) -> StartupReadinessState:
    state = app_state if app_state is not None else SimpleNamespace()
    return StartupReadinessState(
        blocking=bool(getattr(state, "startup_readiness_blocking", False)),
        warnings=list(getattr(state, "startup_readiness_findings", [])),
    )


def build_platform_runtime_status(app_state: object | None = None) -> PlatformRuntimeStatusResponse:
    capabilities = build_capability_catalog()
    prompts = list_registered_prompts()
    async_runtime = build_async_runtime_status()
    async_governance = build_async_governance_status()
    provider_governance = build_provider_governance_status()
    retrieval_governance = build_retrieval_governance_status()
    prompt_governance = build_prompt_governance_status_summary()
    evaluation_runtime = build_evaluation_runtime_status()
    prompt_runtime = build_prompt_runtime_status()
    audit_store = get_audit_store_runtime_status()
    retrieval_store = get_retrieval_store_runtime_status()
    safety_runtime = build_safety_runtime_status()
    startup_state = _resolve_startup_readiness_state(app_state)
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
        async_runtime=async_runtime,
        async_governance=async_governance,
        provider_governance=provider_governance,
        retrieval_governance=retrieval_governance,
        prompt_governance=prompt_governance,
        evaluation_runtime=evaluation_runtime,
        prompt_runtime=prompt_runtime,
        safety_runtime=safety_runtime,
        audit_store=audit_store,
        retrieval_store=retrieval_store,
        database_configured=audit_store.database_configured or retrieval_store.database_configured,
        prompt_count=len(prompts),
        capability_count=len(capabilities.tasks),
        vector_store=VECTOR_STORE_STRATEGY,
        migration_contract_enforced=True,
        startup_readiness_blocking=startup_state.blocking,
        startup_readiness_warnings=startup_state.warnings,
    )
