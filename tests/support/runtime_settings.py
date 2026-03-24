from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from app.config import settings
from app.services.audit_store import reset_audit_store_cache
from app.services.artifact_store import reset_artifact_store_cache
from app.services.caller_policy_store import reset_caller_policy_store_cache
from app.services.prompt_store import reset_prompt_store_cache
from app.services.retrieval_store import reset_retrieval_repository


@contextmanager
def override_runtime_settings(**overrides: object) -> Iterator[None]:
    original_values = {key: getattr(settings, key) for key in overrides}
    try:
        for key, value in overrides.items():
            setattr(settings, key, value)
        reset_audit_store_cache()
        reset_artifact_store_cache()
        reset_caller_policy_store_cache()
        reset_prompt_store_cache()
        reset_retrieval_repository()
        yield
    finally:
        for key, value in original_values.items():
            setattr(settings, key, value)
        reset_audit_store_cache()
        reset_artifact_store_cache()
        reset_caller_policy_store_cache()
        reset_prompt_store_cache()
        reset_retrieval_repository()
