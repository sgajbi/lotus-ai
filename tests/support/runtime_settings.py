from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from app.config import settings
from app.services.audit_store import reset_audit_store_cache
from app.services.artifact_store import reset_artifact_store_cache
from app.services.caller_policy_store import reset_caller_policy_store_cache
from app.services.kill_switch_store import reset_kill_switch_store_cache
from app.services.model_catalogue_store import reset_model_catalogue_store_cache
from app.services.prompt_store import reset_prompt_store_cache
from app.services.retrieval_store import reset_retrieval_repository
from app.services.workflow_pack_registry import reset_workflow_pack_registry_state
from app.services.workflow_pack_queue_event_store import reset_workflow_pack_queue_event_store_cache
from app.services.workflow_pack_run_store import reset_workflow_pack_run_store_cache
from app.services.workflow_pack_task_flow_store import reset_workflow_pack_task_flow_store_cache


@contextmanager
def override_runtime_settings(**overrides: object) -> Iterator[None]:
    original_values = {key: getattr(settings, key) for key in overrides}
    try:
        for key, value in overrides.items():
            setattr(settings, key, value)
        reset_audit_store_cache()
        reset_artifact_store_cache()
        reset_caller_policy_store_cache()
        reset_kill_switch_store_cache()
        reset_model_catalogue_store_cache()
        reset_prompt_store_cache()
        reset_retrieval_repository()
        reset_workflow_pack_registry_state()
        reset_workflow_pack_queue_event_store_cache()
        reset_workflow_pack_run_store_cache()
        reset_workflow_pack_task_flow_store_cache()
        yield
    finally:
        for key, value in original_values.items():
            setattr(settings, key, value)
        reset_audit_store_cache()
        reset_artifact_store_cache()
        reset_caller_policy_store_cache()
        reset_kill_switch_store_cache()
        reset_model_catalogue_store_cache()
        reset_prompt_store_cache()
        reset_retrieval_repository()
        reset_workflow_pack_registry_state()
        reset_workflow_pack_queue_event_store_cache()
        reset_workflow_pack_run_store_cache()
        reset_workflow_pack_task_flow_store_cache()
