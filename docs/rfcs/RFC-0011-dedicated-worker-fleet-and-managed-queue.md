# RFC-0011: Dedicated Worker Fleet and Managed Queue Execution

- Status: Draft
- Date: 2026-03-23
- Owners: lotus-ai
- Requires Approval From: lotus-ai maintainers

## Summary

`lotus-ai` should move from the current durable in-process async worker runtime to a dedicated worker fleet backed by a managed queue, so long-running platform work can scale independently from API-serving replicas.

RFC-0006 established the durable async execution backbone.
RFC-0007 made evaluation execution runtime-backed.
RFC-0008, RFC-0009, and RFC-0010 define the next runtime-critical domains that will rely on async execution more heavily.

The next infrastructure step after those control-plane RFCs is to complete the deployment shape already documented in the architecture.

## Why This Is Next

The platform now has:

1. durable async job submission,
2. durable job, attempt, lease, and control-event state,
3. runtime-backed retrieval indexing and evaluation execution,
4. explicit worker claim, heartbeat, recovery, replay, and abandon semantics,
5. a documented scalability target that expects a worker layer and queue coordination.

But the active runtime still uses an in-process worker path:

1. [async_worker_execution_service.py](C:/Users/Sandeep/projects/lotus-ai/src/app/services/async_worker_execution_service.py#L1) marks `in_process_stub` as the active worker execution,
2. [async_queue_backend_service.py](C:/Users/Sandeep/projects/lotus-ai/src/app/services/async_queue_backend_service.py#L1) marks `service_database` as the active queue backend and keeps `redis_queue` disabled,
3. [scalability-and-deployment-model.md](C:/Users/Sandeep/projects/lotus-ai/docs/architecture/scalability-and-deployment-model.md#L1) already states that API-serving and worker concerns should scale independently.

That means the async control plane is durable, but the operational deployment model is not yet complete.

## Problem Statement

The current async runtime is strong for correctness and reviewability, but limited for bank-grade operations:

1. worker execution still shares process/runtime boundaries with the API tier,
2. queue semantics still depend on the service database as the live coordination backend,
3. horizontal worker scaling is still documented as a future option rather than an active capability,
4. noisy-neighbor isolation for heavy retrieval, evaluation, and future ingestion workloads is still incomplete.

This becomes more important as the platform activates:

1. live retrieval search and indexing operations,
2. runtime safety enforcement,
3. governed prompt activation with rollback evidence,
4. future ingestion or artifact-heavy workloads.

## Goals

1. Introduce a dedicated worker fleet as the active async execution path.
2. Introduce a managed queue backend suitable for independent worker scaling.
3. Preserve the existing durable async contracts, control actions, and job detail semantics.
4. Keep operator/runtime/governance surfaces truthful during and after cutover.
5. Improve queue isolation and noisy-neighbor control for expensive async workloads.

## Non-Goals

1. Rewriting the external async API contracts.
2. Replacing the durable async repository model with opaque vendor-specific queue state.
3. Building a generalized event platform beyond the bounded Lotus async workloads.
4. Broad microservice decomposition beyond the worker/API separation needed here.
5. Removing the service database as the durable source of async job truth.

## Current State

The async runtime already supports:

1. durable job submission,
2. durable attempts and leases,
3. durable control events,
4. worker lifecycle semantics,
5. runtime-backed retrieval and evaluation execution.

The missing piece is operational scaling:

1. worker execution is still in-process,
2. queue coordination is still coupled to the service database runtime,
3. the architecture’s “API layer plus worker layer plus Redis coordination” target is still only partially realized.

## Decision

`lotus-ai` will introduce a dedicated worker fleet and managed queue backend while preserving the existing durable async repository as the authoritative state model.

The first production-capable worker rollout should:

1. use a managed queue backend for delivery and claim coordination,
2. keep the service database as the source of durable async truth,
3. allow API replicas to submit work without also being the primary worker runtime,
4. expose clear runtime status about whether the system is using in-process or dedicated workers,
5. preserve replay, requeue, abandon, and lease-recovery semantics through the same operator contracts.

## State Model and Invariants

This RFC establishes the following invariants:

1. the service database remains the durable source of async job truth,
2. managed queue delivery must not create a second authoritative job-state model,
3. API-serving replicas must not need to own private worker state for correctness,
4. worker claim, heartbeat, retry, replay, and abandon semantics must remain reviewable through the same public async surfaces,
5. runtime status must distinguish in-process fallback from dedicated worker fleet activation truthfully,
6. queue or worker degradation must fail conservatively and visibly rather than silently falling back to misleading execution posture.

## Architecture Direction

### Managed Queue Backend

Introduce a managed queue backend for delivery and coordination while preserving durable state in the service database.

Required behavior:

1. queue messages reference durable job ids rather than carrying authoritative job state,
2. queue delivery is idempotent against the existing async runtime repository,
3. queue and database truth remain aligned,
4. degraded queue behavior is visible through operator surfaces.

### Dedicated Worker Fleet

Introduce a separate worker runtime that processes allowlisted job types outside API-serving replicas.

Required behavior:

1. worker replicas can scale independently,
2. retrieval and evaluation consumers keep using the same durable async control model,
3. worker identity and lease behavior remain explicit,
4. no hidden behavior depends on one API replica also acting as a worker.

### Runtime and Governance Convergence

Async runtime, activation readiness, governance, and runbooks must converge on the dedicated worker truth model.

Required behavior:

1. queue-backend status reflects the active managed queue truthfully,
2. worker-execution status reflects the active dedicated fleet truthfully,
3. activation and runbook readiness differentiate in-process fallback from dedicated worker activation,
4. governance status blocks rollout if queue or worker readiness is incomplete.

### Domain Consumer Convergence

Retrieval indexing and evaluation execution must remain first-class consumers through cutover.

Required behavior:

1. retrieval async execution works unchanged at the external contract layer,
2. evaluation async execution works unchanged at the external contract layer,
3. control actions and replay semantics remain intact,
4. future domains can onboard through the same backbone rather than inventing separate worker paths.

## Data and Operational Requirements

1. Async job truth must survive restart independently of queue message durability.
2. Worker fleet execution must scale independently of API replicas.
3. Queue or worker outage must surface as explicit degraded posture.
4. Duplicate delivery must be safe against the durable state model.
5. SQL-backed and queue-backed integration tests must prove correctness.
6. Runbooks must define queue outage, worker outage, replay, drain, and cutover procedures.
7. Platform runtime status must summarize queue and worker posture honestly.

## Delivery Slices

### Slice 1: Managed Queue Backend Seam and State Model Convergence

Outcome:

1. queue backend integration exists behind the current async seam,
2. durable async repository remains authoritative,
3. no active dedicated worker cutover yet.

Acceptance gate:

1. queue integration is explicit and testable,
2. duplicate delivery is safe,
3. runtime status remains truthful,
4. service-database truth is preserved.

### Slice 2: Dedicated Worker Runtime Activation

Outcome:

1. dedicated worker execution becomes available for allowlisted job types,
2. API replicas no longer act as the primary worker runtime,
3. worker identity and lease semantics remain inspectable.

Acceptance gate:

1. retrieval and evaluation jobs execute through dedicated workers,
2. worker scaling no longer depends on API scaling,
3. control actions still work,
4. integration tests cover real worker-path behavior.

### Slice 3: Queue and Worker Operational Hardening

Outcome:

1. degraded queue and worker states are explicit,
2. retry, drain, and recovery behavior are bounded and documented,
3. noisy-neighbor controls improve for heavy async workloads.

Acceptance gate:

1. degraded posture is surfaced truthfully,
2. failure recovery is testable and documented,
3. queue isolation is reviewable,
4. platform status materially improves for async operations.

### Slice 4: Governance and Runbook Convergence

Outcome:

1. async activation, runbook, and governance surfaces describe the dedicated worker model,
2. rollout review can distinguish in-process fallback from dedicated fleet readiness,
3. evaluation and retrieval async consumers remain aligned with that operational truth.

Acceptance gate:

1. runbooks match implementation reality,
2. governance blocks incomplete worker rollout,
3. runtime-backed evidence remains current,
4. the deployment model is materially closer to the documented target architecture.

## Risks

1. introducing queue delivery without strong idempotency could create duplicate work,
2. weak queue/database convergence could create split-brain job truth,
3. operational cutover from in-process to dedicated workers could confuse status surfaces if not handled cleanly,
4. infrastructure complexity could outpace actual workload demand if rollout is not bounded.

## Alternatives Considered

### Alternative 1: Keep the In-Process Worker Runtime Longer

Rejected as the next async-infrastructure step.

Reason:

1. the architecture already calls for a worker layer and managed coordination,
2. growing retrieval, evaluation, safety, and prompt-control workloads will put more pressure on true worker isolation.

### Alternative 2: Move Fully to Queue-Owned State

Rejected.

Reason:

1. it would break the durable async truth model already established in RFC-0006,
2. the service database should remain the authoritative state store.

### Alternative 3: Split Into Multiple Services Before Worker Fleet Activation

Rejected.

Reason:

1. deployment separation should happen after the async worker model is complete,
2. changing service boundaries now would widen scope without solving the immediate scaling/control problem.

## Acceptance Criteria

This RFC is complete when:

1. dedicated workers can execute allowlisted async workloads independently of API replicas,
2. a managed queue backend is active without replacing the durable async truth model,
3. retrieval and evaluation async consumers continue to work through the same public contracts,
4. runtime, readiness, governance, and runbook surfaces describe the new operational model honestly,
5. the platform is materially closer to the documented bank-grade deployment shape.

## Approval Requested

Approve this RFC if the team agrees that:

1. dedicated workers and managed queue coordination are the next highest-value async infrastructure step,
2. the durable async repository must remain authoritative,
3. rollout should preserve current async contracts while changing the operational backend,
4. delivery should proceed in the slices defined above.
