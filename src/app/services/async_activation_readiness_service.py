from __future__ import annotations

from app.config import settings
from app.contracts.async_runtime import AsyncActivationReadinessResponse
from app.services.async_runtime_status import build_async_runtime_status


def build_async_activation_readiness() -> AsyncActivationReadinessResponse:
    runtime = build_async_runtime_status()
    blocking_findings = [
        "Dedicated queue-backed worker execution is not the active primary path yet; the current posture is still limited to durable in-process execution or queue-delivery shadow mode.",
        "Only a narrow allowlist of async job types is runtime-backed today; retrieval indexing and evaluation execution are active, but broader async surfaces remain staged or documented-only.",
    ]
    activation_path = [
        "Promote the Redis-backed managed queue from shadow delivery to the primary dedicated-worker path without changing the durable async state model.",
        "Enable broader async job types through reviewed rollout slices with observability, safety, replay, and supportability gates.",
    ]
    return AsyncActivationReadinessResponse(
        service=settings.service_name,
        version=settings.service_version,
        delivery_phase=settings.delivery_phase,
        cutover_state=runtime.cutover_state,
        activation_ready=False,
        queue_backend=runtime.queue_backend,
        worker_execution=runtime.active_worker_execution,
        queue_mode=runtime.queue_mode,
        worker_mode=runtime.worker_mode,
        supported_job_type_count=len(runtime.supported_job_types),
        blocking_findings=blocking_findings,
        activation_path=activation_path,
    )
