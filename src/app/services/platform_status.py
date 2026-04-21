from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

from app.config import settings
from app.contracts.platform import PlatformRuntimeStatusResponse
from app.services.app_capability_rollout_catalog import (
    build_app_capability_rollout_catalog,
    build_app_capability_rollout_catalog_governance_status,
)
from app.services.app_capability_rollout_lifecycle import (
    build_app_capability_rollout_catalog_lifecycle_status,
)
from app.services.app_capability_rollout_observability import (
    build_app_capability_rollout_observability_summary,
)
from app.services.artifact_runtime import build_artifact_runtime_status
from app.services.artifact_governance import build_artifact_governance_status
from app.services.access_control_governance import build_access_control_governance_status
from app.services.access_control_runtime import build_access_control_runtime_status
from app.retrieval.policy import VECTOR_STORE_STRATEGY
from app.services.async_governance_status_service import build_async_governance_status
from app.services.async_runtime_status import build_async_runtime_status
from app.services.capability_catalog import build_capability_catalog
from app.services.capability_pack_catalog import build_capability_pack_catalog
from app.services.capability_pack_governance import (
    build_capability_pack_catalog_governance_status,
)
from app.services.eval_status import build_evaluation_runtime_status
from app.services.first_use_case_governance import build_first_use_case_governance_status
from app.services.first_use_case_status import build_first_use_case_runtime_status
from app.services.deployment_split_governance import build_deployment_split_governance_status
from app.services.deployment_split_runtime import build_deployment_split_runtime_status
from app.services.observability_governance import build_observability_governance_status
from app.services.observability_runtime import build_observability_runtime_status
from app.services.production_baseline_governance import (
    build_production_baseline_governance_status,
)
from app.services.prompt_governance_status import build_prompt_governance_status_summary
from app.services.prompt_registry import list_registered_prompts
from app.services.prompt_status import build_prompt_runtime_status
from app.services.production_baseline_runtime import build_production_baseline_runtime_status
from app.services.production_go_live_governance import build_production_go_live_governance_status
from app.services.production_go_live_runtime import build_production_go_live_runtime_status
from app.services.provider_governance_status import build_provider_governance_status
from app.services.provider_operations_status import build_provider_operations_status
from app.services.resilience_governance import build_resilience_governance_status
from app.services.resilience_runtime import build_resilience_runtime_status
from app.services.retrieval_governance_status import build_retrieval_governance_status
from app.services.runtime_readiness import (
    get_artifact_store_runtime_status,
    get_audit_store_runtime_status,
    get_retrieval_store_runtime_status,
    get_workflow_pack_registry_store_runtime_status,
    get_workflow_pack_run_store_runtime_status,
)
from app.services.safety_governance_status import build_safety_governance_status
from app.services.safety_status import build_safety_runtime_status
from app.services.task_runtime_status import build_task_runtime_status
from app.services.workflow_pack_runtime_status import build_workflow_pack_runtime_status_summary


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
    capability_packs = build_capability_pack_catalog()
    capability_pack_governance = build_capability_pack_catalog_governance_status()
    app_capability_rollouts = build_app_capability_rollout_catalog(app_state)
    app_capability_rollout_governance = build_app_capability_rollout_catalog_governance_status(
        app_state
    )
    app_capability_rollout_lifecycle = build_app_capability_rollout_catalog_lifecycle_status(
        app_state
    )
    app_capability_rollout_observability = build_app_capability_rollout_observability_summary(
        app_state
    )
    prompts = list_registered_prompts()
    access_control_runtime = build_access_control_runtime_status()
    access_control_governance = build_access_control_governance_status()
    artifact_runtime = build_artifact_runtime_status()
    artifact_governance = build_artifact_governance_status()
    observability_runtime = build_observability_runtime_status()
    observability_governance = build_observability_governance_status()
    async_runtime = build_async_runtime_status()
    async_governance = build_async_governance_status()
    provider_governance = build_provider_governance_status()
    provider_operations = build_provider_operations_status()
    retrieval_governance = build_retrieval_governance_status()
    prompt_governance = build_prompt_governance_status_summary()
    evaluation_runtime = build_evaluation_runtime_status()
    prompt_runtime = build_prompt_runtime_status()
    task_runtime = build_task_runtime_status()
    first_use_case = build_first_use_case_runtime_status()
    first_use_case_governance = build_first_use_case_governance_status()
    resilience_runtime = build_resilience_runtime_status()
    resilience_governance = build_resilience_governance_status()
    production_baseline = build_production_baseline_runtime_status(app_state)
    production_go_live = build_production_go_live_runtime_status(app_state)
    production_go_live_governance = build_production_go_live_governance_status(app_state)
    deployment_split = build_deployment_split_runtime_status(app_state)
    deployment_split_governance = build_deployment_split_governance_status(app_state)
    production_baseline_governance = build_production_baseline_governance_status(app_state)
    audit_store = get_audit_store_runtime_status()
    artifact_store = get_artifact_store_runtime_status()
    retrieval_store = get_retrieval_store_runtime_status()
    workflow_pack_registry_store = get_workflow_pack_registry_store_runtime_status()
    workflow_pack_run_store = get_workflow_pack_run_store_runtime_status()
    workflow_pack_runtime = build_workflow_pack_runtime_status_summary()
    safety_runtime = build_safety_runtime_status()
    safety_governance = build_safety_governance_status()
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
        access_control_store_mode=settings.access_control_store_mode,
        workflow_pack_registry_store_mode=settings.workflow_pack_registry_store_mode,
        workflow_pack_run_store_mode=settings.workflow_pack_run_store_mode,
        artifact_store_mode=settings.artifact_store_mode,
        artifact_object_store_mode=settings.artifact_object_store_mode,
        access_control_runtime=access_control_runtime,
        access_control_governance=access_control_governance,
        artifact_runtime=artifact_runtime,
        artifact_governance=artifact_governance,
        observability_runtime=observability_runtime,
        observability_governance=observability_governance,
        async_runtime=async_runtime,
        async_governance=async_governance,
        provider_governance=provider_governance,
        provider_operations=provider_operations,
        retrieval_governance=retrieval_governance,
        prompt_governance=prompt_governance,
        evaluation_runtime=evaluation_runtime,
        prompt_runtime=prompt_runtime,
        task_runtime=task_runtime,
        first_use_case=first_use_case,
        capability_pack_catalog=capability_packs,
        capability_pack_governance=capability_pack_governance,
        app_capability_rollout_catalog=app_capability_rollouts,
        app_capability_rollout_governance=app_capability_rollout_governance,
        app_capability_rollout_observability=app_capability_rollout_observability,
        app_capability_rollout_lifecycle=app_capability_rollout_lifecycle,
        first_use_case_governance=first_use_case_governance,
        safety_runtime=safety_runtime,
        safety_governance=safety_governance,
        resilience_runtime=resilience_runtime,
        resilience_governance=resilience_governance,
        production_baseline=production_baseline,
        production_go_live=production_go_live,
        production_go_live_governance=production_go_live_governance,
        deployment_split=deployment_split,
        deployment_split_governance=deployment_split_governance,
        production_baseline_governance=production_baseline_governance,
        audit_store=audit_store,
        retrieval_store=retrieval_store,
        workflow_pack_registry_store=workflow_pack_registry_store,
        workflow_pack_run_store=workflow_pack_run_store,
        workflow_pack_runtime=workflow_pack_runtime,
        database_configured=(
            audit_store.database_configured
            or retrieval_store.database_configured
            or workflow_pack_registry_store.database_configured
            or workflow_pack_run_store.database_configured
            or artifact_store.database_configured
        ),
        prompt_count=len(prompts),
        capability_count=len(capabilities.tasks),
        capability_pack_count=capability_packs.pack_count,
        app_capability_rollout_count=app_capability_rollouts.pairing_count,
        app_capability_rollout_ready_count=app_capability_rollout_governance.ready_pairing_count,
        app_capability_rollout_observed_count=app_capability_rollout_observability.observed_pairing_count,
        app_capability_rollout_lifecycle_ready_count=app_capability_rollout_lifecycle.ready_pairing_count,
        vector_store=VECTOR_STORE_STRATEGY,
        migration_contract_enforced=True,
        startup_readiness_blocking=startup_state.blocking,
        startup_readiness_warnings=startup_state.warnings,
    )
