from __future__ import annotations

from dataclasses import dataclass

from app.config import settings
from app.services.embedding_live_execution_state import build_embedding_live_execution_state
from app.services.provider_policy import _resolve_selected_embedding_provider


@dataclass(frozen=True)
class RetrievalEmbeddingRuntimeDescriptor:
    embedding_provider_mode: str
    embedding_execution_enabled: bool
    embedding_provider_id: str
    embedding_model_id: str | None
    embedding_strategy: str
    findings: list[str]


def build_retrieval_embedding_runtime() -> RetrievalEmbeddingRuntimeDescriptor:
    live_execution_state = build_embedding_live_execution_state()
    embedding_provider_id, _ = _resolve_selected_embedding_provider()
    if live_execution_state.live_execution_enabled:
        embedding_strategy = "provider-live-openai"
        findings = [
            "Retrieval indexing can use the bounded live embedding provider path for governed corpus growth."
        ]
    elif settings.embedding_provider_mode == "stub":
        embedding_strategy = "provider-stub"
        findings = [
            "Retrieval indexing remains on the stub embedding path until live embedding rollout is enabled."
        ]
    else:
        embedding_strategy = "provider-disabled"
        findings = [
            "Retrieval indexing falls back to the stub embedding path because live embedding execution is not enabled."
        ]
        if live_execution_state.blocking_reason is not None:
            findings.append(live_execution_state.blocking_reason)
    return RetrievalEmbeddingRuntimeDescriptor(
        embedding_provider_mode=settings.embedding_provider_mode,
        embedding_execution_enabled=live_execution_state.live_execution_enabled,
        embedding_provider_id=embedding_provider_id,
        embedding_model_id=live_execution_state.configured_model_id,
        embedding_strategy=embedding_strategy,
        findings=findings,
    )
