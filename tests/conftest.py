from __future__ import annotations

from collections.abc import Generator

import pytest

from app.config import settings
from app.services.audit_store import reset_audit_store_cache
from app.services.prompt_store import reset_prompt_store_cache
from app.services.retrieval_store import reset_retrieval_repository


@pytest.fixture(autouse=True)
def reset_runtime_settings() -> Generator[None, None, None]:
    original_values = {
        "provider_mode": settings.provider_mode,
        "retrieval_mode": settings.retrieval_mode,
        "embedding_provider_mode": settings.embedding_provider_mode,
        "audit_store_mode": settings.audit_store_mode,
        "prompt_store_mode": settings.prompt_store_mode,
        "retrieval_store_mode": settings.retrieval_store_mode,
        "startup_readiness_policy": settings.startup_readiness_policy,
        "readiness_probe_policy": settings.readiness_probe_policy,
        "database_url": settings.database_url,
    }
    try:
        yield
    finally:
        for key, value in original_values.items():
            setattr(settings, key, value)
        reset_audit_store_cache()
        reset_prompt_store_cache()
        reset_retrieval_repository()
