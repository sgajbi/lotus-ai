from __future__ import annotations

from app.config import settings
from app.contracts.async_runtime import AsyncCutoverState
from app.contracts.async_runtime import AsyncActivationReadinessResponse
from app.services.async_operational_state import build_async_operational_state
from app.services.async_runtime_status import build_async_runtime_status


def build_async_activation_readiness() -> AsyncActivationReadinessResponse:
    runtime = build_async_runtime_status()
    operational_state = build_async_operational_state()
    if runtime.cutover_state == AsyncCutoverState.DEDICATED_WORKERS_ACTIVE:
        blocking_findings = [
            *operational_state.degraded_findings,
            "Only a narrow allowlist of async job types is runtime-backed today; retrieval indexing and evaluation execution are active, but broader async surfaces remain staged or documented-only.",
        ]
        activation_path = [
            "Confirm queue backlog, duplicate/redelivery, drain mode, and active worker identity surfaces remain healthy under the dedicated worker cutover.",
            "Keep dedicated workers primary for the allowlisted job types while expanding reviewed async coverage through later rollout slices.",
        ]
    elif runtime.cutover_state == AsyncCutoverState.DEGRADED_FALLBACK:
        blocking_findings = [
            *operational_state.degraded_findings,
            "Dedicated queue-backed worker execution is currently degraded; operator review must resolve the degraded fallback before activation can be considered stable.",
            "Only a narrow allowlist of async job types is runtime-backed today; retrieval indexing and evaluation execution are active, but broader async surfaces remain staged or documented-only.",
        ]
        activation_path = [
            "Restore the Redis-backed managed queue and dedicated worker fleet as the primary path without changing the durable async state model.",
            "Enable broader async job types through reviewed rollout slices with observability, safety, replay, and supportability gates.",
        ]
    elif runtime.cutover_state == AsyncCutoverState.QUEUE_DELIVERY_SHADOW:
        blocking_findings = [
            "Managed queue delivery is wired in shadow mode, but dedicated workers are not yet the active primary execution path.",
            "Only a narrow allowlist of async job types is runtime-backed today; retrieval indexing and evaluation execution are active, but broader async surfaces remain staged or documented-only.",
        ]
        activation_path = [
            "Promote the Redis-backed managed queue from shadow delivery to dedicated primary execution only after worker startup, drain, replay, and queue-outage procedures are reviewed.",
            "Keep the service database as authoritative async truth while moving the allowlisted job types off API-primary execution.",
        ]
    else:
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
