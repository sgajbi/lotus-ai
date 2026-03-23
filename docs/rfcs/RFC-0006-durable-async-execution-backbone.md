# RFC-0006: Durable Async Execution Backbone

- Status: Proposed
- Date: 2026-03-23
- Owners: lotus-ai
- Requires Approval From: lotus-ai maintainers

## Summary

`lotus-ai` should replace the current documentation-backed async facade with a durable, worker-safe async execution backbone.

RFC-0001 established async contracts and governance posture.
RFC-0002 began using those seams for retrieval indexing workflows.
But the async runtime is still not authoritative:

1. submission is rejected in the service layer,
2. job catalogs are loaded from governed artifact files rather than live job state,
3. there is no durable queue, claim, lease, or completion model,
4. background execution is not yet trustworthy across restart or multi-instance deployment.

That is now the next high-value platform gap.

## Why This Is Next

The platform now has:

1. governed retrieval with real indexing and refresh behavior,
2. a controlled live-provider backbone,
3. hardened provider operations controls,
4. growing task, audit, and runtime visibility,
5. strong RFC and CI discipline.

The biggest remaining runtime gap is that long-running or replayable work is still not backed by a real async control plane.

Without a durable async backbone:

1. retrieval indexing cannot mature into bank-grade background execution,
2. provider-side background work would remain coupled to synchronous request paths,
3. job inspection endpoints overstate runtime reality,
4. restart and multi-instance operation cannot preserve authoritative job truth.

This RFC should stop at the durable async backbone itself. Higher-level consumers such as runtime-backed evaluation execution should build on top of this backbone in later RFCs rather than widening this RFC into a second execution domain at the same time.

## Problem Statement

Today async behavior is still mostly a governed contract shell:

1. submissions are rejected in [async_submission_service.py](C:/Users/Sandeep/projects/lotus-ai/src/app/services/async_submission_service.py#L1),
2. job catalogs and detail views are read from static governed artifacts in [async_job_service.py](C:/Users/Sandeep/projects/lotus-ai/src/app/services/async_job_service.py#L1),
3. the current registry loader in [job_registry.py](C:/Users/Sandeep/projects/lotus-ai/src/app/async_runtime/job_registry.py#L1) validates docs, not runtime execution state.

This creates real limitations:

1. there is no authoritative persisted job lifecycle,
2. queue and worker posture cannot be trusted under restart,
3. retrieval and future provider jobs cannot safely move off synchronous control paths,
4. operator-facing async summaries are more descriptive than operationally real.

## Goals

1. Introduce durable async job persistence and lifecycle state.
2. Enable governed async submission for explicitly allowlisted job types.
3. Add worker-safe claim, lease, heartbeat, and completion semantics.
4. Make async runtime, job detail, and governance endpoints report authoritative live state.
5. Keep the first delivery simple, database-backed, and explainable.

## Non-Goals

1. External queue infrastructure as the first delivery target.
2. Generic distributed workflow orchestration beyond `lotus-ai` runtime jobs.
3. Large-scale autoscaling or throughput optimization work.
4. Broad background execution for every service action.
5. Replacing the existing async governance surfaces with a new model.

## Current State

Today `lotus-ai` already has:

1. async contracts and routers,
2. runtime-status, readiness, and governance views,
3. retrieval index-refresh behavior that is a strong async candidate,
4. documented async job artifact governance,
5. clear validation gates for async documentation artifacts.

Those surfaces should remain intact where possible. The change in this RFC is to make the underlying runtime authoritative and durable.

## Decision

`lotus-ai` will implement a durable async execution backbone using the service database as the first authoritative state store.

The first version should persist:

1. async job submission records,
2. job status transitions,
3. worker claim and lease state,
4. heartbeat and attempt metadata,
5. enough execution evidence to support job detail, runtime summaries, and incident review.

The public async contracts should remain stable wherever possible. The focus is not on widening the API. The focus is on making the existing async runtime truthful and usable.

## State Model and Invariants

This RFC establishes one authoritative rule:

1. job lifecycle truth must come from durable runtime state rather than documentation artifacts,
2. job inspection endpoints and worker decisions must derive from that same durable state,
3. process-local memory may cache reads, but it must not become an independent source of job truth,
4. no job type should be partially cut over in a way that mixes static artifact truth with live runtime truth for the same record.

The durable async model should preserve these invariants:

1. job submission must create one authoritative persisted job record,
2. worker claim must be atomic so one runnable job is not executed concurrently by multiple workers,
3. lease expiry and retry eligibility must be derived from persisted timestamps,
4. status transitions must be explainable from persisted attempts and events,
5. operator-facing summaries must be derivable without consulting process-local worker memory,
6. retry, replay, or duplicate client submission must not silently create ambiguous execution truth for the same logical work item.

### Job Lifecycle Semantics

The first durable async runtime should use an explicit and narrow lifecycle model.

Required lifecycle properties:

1. submitted, runnable, claimed, running, completed, failed, and terminally-abandoned posture must be distinguishable,
2. retryable failure must remain distinct from terminal failure,
3. lease expiry must not itself imply success, failure, or completion,
4. replay or requeue must create explicit new attempt history rather than mutating prior execution history out of existence.

The implementation should prefer a small explicit state machine over ad hoc status transitions spread across services.

## Architecture Direction

### Async Runtime Persistence

Add migration-managed tables for:

1. async jobs,
2. async job attempts or lifecycle events,
3. worker lease or heartbeat state,
4. optional job-type-specific execution metadata where needed for observability.

The persistence model should remain async-runtime-specific rather than hidden in a generic key-value or opaque blob design.

### Repository and Service Boundaries

Introduce an async runtime repository seam so:

1. submission no longer returns documentation-only rejection for allowlisted job types,
2. job catalog and detail services no longer read only from static artifacts,
3. worker claim and completion logic does not depend on process-local singleton state,
4. test coverage can verify repository and service behavior directly.

### Consistency Model

The first delivery should be conservative and explicit:

1. job submission writes synchronously to the authoritative database state,
2. worker claim, heartbeat, and completion transitions are atomic,
3. retry and lease semantics are deterministic and time-based,
4. restart behavior preserves authoritative job truth,
5. worker ownership must be explicit enough to explain who currently holds a claim,
6. the implementation should prefer simple transaction boundaries over asynchronous reconciliation.

### Runtime and Governance Surfaces

Existing endpoints should continue to expose:

1. runtime async posture,
2. job catalogs,
3. job detail views,
4. activation and governance readiness,
5. runbook and eval posture.

But those views should now report durable live state rather than only governed documentation artifacts.

### Operator Control Actions

The durable async backbone should also define a narrow, reviewable operator control path for runtime-backed jobs.

Required control semantics:

1. retry, replay, requeue, abandon, or equivalent recovery actions must be explicit durable state transitions,
2. those actions must be recorded as control-plane history rather than implied by direct table edits,
3. job-detail and runtime-summary surfaces must remain able to explain whether a job is original, replayed, retried, or manually recovered,
4. documentation-only job types must not expose runtime control actions that imply false live execution support.

### Cutover and Compatibility Semantics

The migration from documentation-backed async state to durable runtime state should avoid split-brain truth.

Required cutover rules:

1. each job type must be explicitly marked as documentation-only or runtime-backed,
2. once a job type is cut over, its job detail and catalog truth must come from the durable runtime path,
3. if compatibility views still reference governed artifacts, they must be clearly labeled as historical or staged rather than runtime truth,
4. no silent fallback from failed runtime repository access to static artifact success is allowed.

Required operational semantics:

1. lease timeout, retry window, and terminal-state rules must be explicit,
2. abandoned jobs must have deterministic recovery behavior,
3. retries must record attempt history rather than rewriting history in place,
4. replay or manual requeue actions must be governed state transitions, not table edits,
5. if idempotency keys or equivalent submission deduplication are introduced, their scope and collision behavior must be explicit and testable.

## First-Class Job Types

The first runtime-backed async job types should stay narrow and high-value:

1. retrieval index refresh,
2. evaluation run execution if already bounded enough for the current platform posture,
3. any provider-side background work only if it reuses the same authoritative async backbone rather than inventing a second mechanism.

The first implementation should resist broad job-type expansion until the backbone is proven.

## Data and Operational Requirements

1. Async job state must survive service restart.
2. Multi-instance deployment must not allow duplicate worker execution for the same claimed attempt.
3. Lease expiry and retry eligibility must be durable and testable.
4. Terminal states must remain stable across restart and worker interruption.
5. Repository unavailability must fail safely and truthfully rather than silently bypassing async controls.
6. Job state persistence must not leak credentials or raw provider payloads.
7. The database schema must be migration-managed and integration-tested.
8. Runtime summaries must be able to explain queued, running, failed, and completed posture from persisted state.
9. Artifact-based async documentation should remain governed, but it must no longer masquerade as live runtime truth after cutover.
10. Job progress or status messaging must not overstate execution progress when a worker has only claimed but not actually completed work.
11. Duplicate submission, retry, and replay semantics must be explicit enough to prevent ambiguous operator truth.
12. Manual recovery or replay actions must be durably recorded and reviewable through operator-facing state.

## Delivery Slices

### Slice 1: Durable Async Runtime Schema

Outcome:

1. migration-managed schema exists for jobs, attempts or events, and worker lease state,
2. explicit repository contracts are introduced,
3. no public API behavior changes yet.

Acceptance gate:

1. schema is migration-managed,
2. repository contracts are unit-tested,
3. no hidden runtime table creation exists,
4. state entities are explicit enough that lifecycle truth is not forced into opaque blobs.

### Slice 2: Durable Job Submission and Catalog State

Outcome:

1. allowlisted job types can be submitted into durable runtime state,
2. job catalogs and detail views can report runtime-backed records,
3. documentation-only job types remain explicitly staged rather than pretending to be live runtime jobs.

Acceptance gate:

1. persisted submission creates authoritative job records,
2. restart does not erase queued or terminal job truth,
3. integration tests cover runtime-backed catalog and detail views,
4. unsupported job types still fail truthfully,
5. duplicate or repeated submission behavior is explicit and covered by meaningful tests.

### Slice 3: Worker Claim, Lease, and Completion Semantics

Outcome:

1. workers can atomically claim runnable jobs,
2. lease and heartbeat behavior is durable,
3. completion, failure, and retry transitions are persisted explicitly.

Acceptance gate:

1. concurrent worker claim cannot double-execute the same runnable attempt,
2. abandoned or expired leases become recoverable deterministically,
3. terminal-state transitions are durable and reviewable,
4. tests cover claim, completion, lease expiry, and retry flows,
5. worker ownership and attempt history remain inspectable during failure and recovery.

### Slice 4: Runtime-Backed Retrieval Indexing Execution

Outcome:

1. retrieval index refresh can run through the durable async runtime,
2. job detail reflects real retrieval execution progress and result posture,
3. synchronous refresh paths are reduced or clearly demoted for governed fallback use only.

Acceptance gate:

1. retrieval indexing can be submitted, claimed, executed, and inspected end to end,
2. restart does not lose authoritative job truth,
3. retrieval runtime and job-detail views remain truthful under failure and retry,
4. tests cover meaningful retrieval job execution behavior rather than shallow status assertions.

### Slice 5: Runtime, Eval, Runbook, and Control-Plane Convergence

Outcome:

1. async runtime summaries reflect the durable control plane,
2. eval assets and run artifacts reflect live async behavior where appropriate,
3. runbooks describe claim, retry, recovery, and replay against the durable state model,
4. operator recovery and replay actions are exposed through a governed async control-plane surface.

Acceptance gate:

1. runtime and governance summaries stay aligned,
2. eval and runbook assets match implementation reality,
3. restart-survival and worker-recovery scenarios are covered by meaningful tests,
4. the service is materially closer to enterprise-grade background execution,
5. job status and progress wording remains conservative and truthful under claim, retry, and recovery paths,
6. documentation-backed async artifacts that remain after cutover are clearly labeled as staged or historical rather than live runtime truth,
7. duplicate runtime-backed submission semantics are explicit and surfaced through API behavior rather than remaining implicit in code.

## Risks

1. poorly designed persistence could create claim contention or worker starvation,
2. hidden fallback behavior could make operator views untruthful,
3. overly generic abstractions could obscure job-type-specific behavior,
4. incomplete retry semantics could cause duplicate or lost work.

## Alternatives Considered

### Alternative 1: Keep Async as a Documentation Surface Longer

Rejected as the next implementation phase.

Reason:

1. the contracts are already in place,
2. the highest-value remaining gap is runtime truth, not more documentation.

### Alternative 2: Introduce External Queue Infrastructure First

Rejected for the first pass.

Reason:

1. it adds infrastructure before the authoritative state model is proven,
2. the service database is the simplest reviewable first home for job truth.

### Alternative 3: Add More Synchronous Background-Like Paths Instead

Rejected for now.

Reason:

1. it would keep long-running work coupled to request paths,
2. it would delay the durable async backbone the platform now clearly needs.

## Acceptance Criteria

This RFC is complete when:

1. async job submission and lifecycle state are durable,
2. worker claim, lease, retry, and terminal-state behavior are durable and testable,
3. runtime async summaries remain truthful across restart and instance boundaries,
4. retrieval indexing can run through the authoritative async runtime,
5. no runtime-backed async job type depends on process-local mutable globals for lifecycle truth,
6. runbooks and eval assets reflect the durable async state model,
7. duplicate submission, replay, and retry semantics are explicit and reviewable,
8. governed operator recovery actions are explicit and durably reviewable,
9. the platform is materially closer to bank-grade background execution.

## Approval Requested

Approve this RFC if the team agrees that:

1. durable async execution is the next highest-value platform gap after durable provider operations state,
2. the first authoritative async state store should be the service database,
3. delivery should proceed in the slices defined above,
4. broad background feature expansion should remain secondary to durable job-lifecycle correctness.
