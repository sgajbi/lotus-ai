from __future__ import annotations

from app.config import settings
from app.contracts.production_go_live import (
    ProductionGoLiveDomainDescriptor,
    ProductionGoLiveDomainStatus,
)
from app.services.artifact_activation_readiness import build_artifact_activation_readiness
from app.services.artifact_runtime import build_artifact_runtime_status


def build_managed_secret_approval_domain() -> ProductionGoLiveDomainDescriptor:
    deployment_managed = settings.secret_source_mode == "deployment_managed"
    detail = (
        "Runtime secrets are deployment-managed, so the platform satisfies the managed-secret production approval domain."
        if deployment_managed
        else (
            "Live-provider configuration is present, but secrets still come from a local or unspecified source, so production go-live remains blocked on managed-secret posture."
            if settings.live_text_provider_api_key
            else "Secret posture is still local or unspecified, which remains acceptable for demos but blocks production go-live approval."
        )
    )
    return ProductionGoLiveDomainDescriptor(
        domain_id="managed_secret_posture",
        status=(
            ProductionGoLiveDomainStatus.APPROVED
            if deployment_managed
            else ProductionGoLiveDomainStatus.BLOCKED
        ),
        required_for_platform_approval=True,
        configured_mode=settings.secret_source_mode,
        review_surface="/platform/production-baseline/runtime-status",
        detail=detail,
    )


def build_managed_object_storage_approval_domain() -> ProductionGoLiveDomainDescriptor:
    runtime_status = build_artifact_runtime_status()
    activation_readiness = build_artifact_activation_readiness()
    object_store_ready = (
        runtime_status.object_store.status.value == "READY"
        and runtime_status.object_store.durable
        and settings.artifact_object_store_mode not in {"memory", "filesystem"}
    )
    if object_store_ready:
        detail = "Artifact payload storage is using a governed durable object-store posture suitable for production go-live approval."
    else:
        object_store_blocker = next(
            (
                finding
                for finding in activation_readiness.blocking_findings
                if "object-store" in finding.lower()
                or "payload storage" in finding.lower()
                or "filesystem" in finding.lower()
            ),
            "Artifact payload storage remains below the managed object-storage production approval boundary.",
        )
        detail = object_store_blocker
    return ProductionGoLiveDomainDescriptor(
        domain_id="managed_object_storage",
        status=(
            ProductionGoLiveDomainStatus.APPROVED
            if object_store_ready
            else ProductionGoLiveDomainStatus.BLOCKED
        ),
        required_for_platform_approval=True,
        configured_mode=settings.artifact_object_store_mode,
        review_surface="/platform/artifacts/governance-status",
        detail=detail,
    )
