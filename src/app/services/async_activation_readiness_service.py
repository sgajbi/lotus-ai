from __future__ import annotations

from app.config import settings
from app.contracts.async_runtime import AsyncActivationReadinessResponse
from app.services.async_runtime_status import build_async_runtime_status


def build_async_activation_readiness() -> AsyncActivationReadinessResponse:
    runtime = build_async_runtime_status()
    blocking_findings = [
        "Dedicated queue-backed worker execution remains disabled; the current durable in-process worker posture is reviewable but not yet horizontally isolated.",
        "Only a narrow allowlist of async job types is runtime-backed today; broader async surfaces such as evaluation execution remain staged.",
    ]
    activation_path = [
        "Activate an isolated queue-backed worker execution strategy on top of the durable submission, claim, lease, and recovery model.",
        "Enable broader async job types through reviewed rollout slices with observability, safety, replay, and supportability gates.",
    ]
    return AsyncActivationReadinessResponse(
        service=settings.service_name,
        version=settings.service_version,
        delivery_phase=settings.delivery_phase,
        activation_ready=False,
        queue_backend=runtime.queue_backend,
        worker_execution=runtime.active_worker_execution,
        queue_mode=runtime.queue_mode,
        worker_mode=runtime.worker_mode,
        supported_job_type_count=len(runtime.supported_job_types),
        blocking_findings=blocking_findings,
        activation_path=activation_path,
    )
