from __future__ import annotations

from app.config import settings
from app.contracts.artifacts import ArtifactActivationReadinessResponse
from app.contracts.runtime_readiness import RuntimeReadinessStatus
from app.services.artifact_runtime import build_artifact_runtime_status

ACTIVE_CUTOVER_DOMAINS = ["evaluation", "async", "observability"]


def build_artifact_activation_readiness() -> ArtifactActivationReadinessResponse:
    runtime_status = build_artifact_runtime_status()
    blocking_findings: list[str] = []

    if runtime_status.metadata_store.status is not RuntimeReadinessStatus.READY:
        blocking_findings.append(
            "Artifact metadata store is not ready for stronger governed rollout posture."
        )
    if runtime_status.object_store.status is not RuntimeReadinessStatus.READY:
        blocking_findings.append(
            "Artifact object-store backend is not ready for stronger governed rollout posture."
        )
    if not runtime_status.object_store.durable:
        blocking_findings.append(
            "Artifact object-store durability is still in-memory and not restart-safe."
        )
    if len(ACTIVE_CUTOVER_DOMAINS) < 3:
        # A tripwire on the declared cutover set, not dead code: it cannot fire
        # while the constant lists three domains, and it fires the moment a
        # future edit narrows it. Its test monkeypatches the constant to prove
        # the wire is live (issue #154 review).
        blocking_findings.append(
            "Artifact consumer cutover is still too narrow for stronger governed rollout posture."
        )
    if settings.artifact_object_store_mode == "filesystem":
        blocking_findings.append(
            "Filesystem artifact payload storage remains a clearly labeled local or development fallback, not a production object-store posture."
        )

    return ArtifactActivationReadinessResponse(
        service=settings.service_name,
        version=settings.service_version,
        activation_ready=not blocking_findings,
        cutover_domain_count=len(ACTIVE_CUTOVER_DOMAINS),
        lifecycle_controls_ready=True,
        blocking_findings=blocking_findings,
        activation_path=[
            "Keep artifact metadata relationally authoritative while payload bytes stay behind the governed object-store seam.",
            "Use durable metadata and object-store modes before treating artifact-backed outputs as restart-safe platform posture.",
            "Expand runtime consumer cutover one governed domain at a time instead of adding ad hoc payload paths.",
        ],
    )
