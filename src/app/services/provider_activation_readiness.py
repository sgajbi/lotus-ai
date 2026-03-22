from __future__ import annotations

from app.config import settings
from app.contracts.providers import ProviderActivationReadinessResponse
from app.contracts.providers import ProviderCredentialStatus, ProviderRolloutState
from app.services.provider_configuration_status import (
    build_text_generation_configuration_status,
)
from app.services.provider_rollout_posture import build_provider_rollout_posture


def build_provider_activation_readiness() -> ProviderActivationReadinessResponse:
    configuration = build_text_generation_configuration_status()
    rollout_posture = build_provider_rollout_posture()
    blocking_findings = [
        "Live model execution remains disabled in the current foundation phase.",
        "Configured provider modes are limited to disabled and stub execution paths.",
        "No governed allowlisted live provider integration has been approved for text generation.",
        "Embedding provider activation remains blocked until retrieval execution and indexing controls are live.",
    ]
    if configuration.rollout_state == ProviderRolloutState.ALLOWLISTED_DISABLED:
        blocking_findings.append(
            "Live-provider rollout is allowlisted but still intentionally disabled pending later activation slices."
        )
    if not configuration.configuration_valid:
        blocking_findings.extend(configuration.findings)
    elif configuration.credential_status == ProviderCredentialStatus.NOT_CONFIGURED:
        blocking_findings.append(
            "No live-provider credentials are configured for any future allowlisted text-generation path."
        )
    blocking_findings.append(rollout_posture.notes)
    activation_path = [
        "Review `/platform/providers` and `/platform/providers/policy` to confirm the provider catalog, adapter kind, runtime mode, and selected execution path match the intended rollout posture.",
        "Verify allowlisted rollout configuration and credential posture through `/platform/providers/activation-readiness` before any live mode is considered.",
        "Confirm provider evaluation and failure-mode evidence through `/platform/providers/evidence-readiness`.",
        "Confirm on-call, quota-handling, rollback, and observability readiness through `/platform/providers/runbook-readiness`.",
        "Approve activation only when `/platform/providers/governance-status` and the embedded `provider_governance` block in `/platform/runtime-status` both show the same ready-to-activate posture.",
    ]
    return ProviderActivationReadinessResponse(
        service=settings.service_name,
        version=settings.service_version,
        provider_mode=settings.provider_mode,
        embedding_provider_mode=settings.embedding_provider_mode,
        text_generation_configuration=configuration,
        activation_ready=False,
        blocking_findings=blocking_findings,
        activation_path=activation_path,
    )
