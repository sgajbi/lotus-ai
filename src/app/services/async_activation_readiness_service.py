from __future__ import annotations

from app.config import settings
from app.contracts.async_runtime import AsyncActivationReadinessResponse
from app.services.async_runtime_status import build_async_runtime_status


def build_async_activation_readiness() -> AsyncActivationReadinessResponse:
    runtime = build_async_runtime_status()
    blocking_findings = [
        "Queue-backed execution remains disabled in the current foundation phase.",
        "The active queue backend is 'none'; no live durable queue has been selected.",
        (
            "The active worker execution is 'none'; no dedicated worker runtime is active."
            if runtime.active_worker_execution == "none"
            else "Only the in-process stub worker runtime is active; queue-backed worker isolation is not enabled."
        ),
        (
            "Supported async job types remain documented-only and are not enabled for live execution."
            if not any(job.enabled for job in runtime.supported_job_types)
            else "Only stubbed async job execution is enabled; live queue-backed execution remains blocked."
        ),
    ]
    activation_path = [
        "Select and approve a governed durable queue backend for lotus-ai async execution.",
        "Activate an isolated worker execution strategy with horizontal scaling and operational runbooks.",
        "Enable async job types through a reviewed rollout slice with observability, safety, and supportability gates.",
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
