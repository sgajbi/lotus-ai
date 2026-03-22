from __future__ import annotations

from app.config import settings
from app.contracts.providers import ProviderActivationReadinessResponse


def build_provider_activation_readiness() -> ProviderActivationReadinessResponse:
    blocking_findings = [
        "Live model execution remains disabled in the current foundation phase.",
        "Configured provider modes are limited to disabled and stub execution paths.",
        "No governed allowlisted live provider integration has been approved for text generation.",
        "Embedding provider activation remains blocked until retrieval execution and indexing controls are live.",
    ]
    activation_path = [
        "Approve a governed live-provider rollout with explicit allowlisted provider integrations and contracts.",
        "Complete provider-specific safety, audit, and operational controls for live execution.",
        "Enable live provider modes through a reviewed rollout slice with evaluation evidence and supportability gates.",
        "Validate end-to-end live-provider behavior before activation in shared or enterprise environments.",
    ]
    return ProviderActivationReadinessResponse(
        service=settings.service_name,
        version=settings.service_version,
        provider_mode=settings.provider_mode,
        embedding_provider_mode=settings.embedding_provider_mode,
        activation_ready=False,
        blocking_findings=blocking_findings,
        activation_path=activation_path,
    )
