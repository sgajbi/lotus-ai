from __future__ import annotations

from pydantic import BaseModel, Field

from app.contracts.async_runtime import AsyncGovernanceStatusResponse, AsyncRuntimeStatusResponse
from app.contracts.evals import EvaluationRuntimeStatusResponse
from app.contracts.prompts import PromptRuntimeStatusResponse
from app.contracts.providers import ProviderGovernanceStatusResponse
from app.contracts.retrieval import RetrievalGovernanceStatusResponse
from app.contracts.runtime_readiness import (
    StoreRuntimeStatusDescriptor,
)
from app.contracts.safety import SafetyRuntimeStatusResponse


class PlatformRuntimeStatusResponse(BaseModel):
    service: str = Field(description="Service name emitting the platform runtime status.")
    version: str = Field(description="Current lotus-ai service version.")
    delivery_phase: str = Field(description="Current lotus-ai delivery phase.")
    startup_readiness_policy: str = Field(description="Configured startup readiness policy mode.")
    readiness_probe_policy: str = Field(description="Configured readiness probe degradation mode.")
    provider_mode: str = Field(description="Current model provider execution mode.")
    retrieval_mode: str = Field(description="Current retrieval execution mode.")
    embedding_provider_mode: str = Field(description="Current embedding provider mode.")
    safety_mode: str = Field(description="Current safety policy mode.")
    prompt_store_mode: str = Field(description="Current prompt registry store mode.")
    async_runtime: AsyncRuntimeStatusResponse = Field(
        description="Current async execution posture for lotus-ai."
    )
    async_governance: AsyncGovernanceStatusResponse = Field(
        description="Current async governance posture for lotus-ai."
    )
    provider_governance: ProviderGovernanceStatusResponse = Field(
        description="Current provider governance posture for lotus-ai."
    )
    retrieval_governance: RetrievalGovernanceStatusResponse = Field(
        description="Current retrieval governance posture for lotus-ai."
    )
    evaluation_runtime: EvaluationRuntimeStatusResponse = Field(
        description="Current evaluation runtime posture for lotus-ai."
    )
    prompt_runtime: PromptRuntimeStatusResponse = Field(
        description="Current prompt runtime selection posture for lotus-ai."
    )
    safety_runtime: SafetyRuntimeStatusResponse = Field(
        description="Current safety runtime posture for lotus-ai."
    )
    audit_store: StoreRuntimeStatusDescriptor = Field(
        description="Current audit persistence runtime posture."
    )
    retrieval_store: StoreRuntimeStatusDescriptor = Field(
        description="Current retrieval metadata runtime posture."
    )
    database_configured: bool = Field(
        description="Whether a database URL is configured for durable runtime components."
    )
    prompt_count: int = Field(description="Number of registered prompt definitions.")
    capability_count: int = Field(description="Number of bounded capabilities exposed by lotus-ai.")
    vector_store: str = Field(description="Current or planned vector-store strategy label.")
    migration_contract_enforced: bool = Field(
        description="Whether lotus-ai requires migration-managed relational schema changes."
    )
    startup_readiness_blocking: bool = Field(
        description="Whether the latest startup readiness evaluation identified blocking issues."
    )
    startup_readiness_warnings: list[str] = Field(
        description="Human-readable startup readiness findings captured during startup evaluation."
    )
