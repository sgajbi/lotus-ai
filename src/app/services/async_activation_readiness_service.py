from __future__ import annotations

from app.config import settings
from app.contracts.async_runtime import AsyncActivationReadinessResponse
from app.services.async_runtime_status import build_async_runtime_status


def build_async_activation_readiness() -> AsyncActivationReadinessResponse:
    runtime = build_async_runtime_status()
    blocking_findings = [
        "Dedicated worker execution remains disabled; submitted async jobs are durable but not yet claimable.",
        "The active worker execution is 'none'; no worker lease, heartbeat, or completion runtime is active.",
        "Only a narrow allowlist of async job types is runtime-backed; the broader async surface remains staged.",
    ]
    activation_path = [
        "Activate an isolated worker execution strategy with lease, heartbeat, and recovery semantics.",
        "Enable broader async job types through reviewed rollout slices with observability, safety, and supportability gates.",
        "Validate end-to-end async behavior through governed runtime, evaluation, and deployment checks before activation.",
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
