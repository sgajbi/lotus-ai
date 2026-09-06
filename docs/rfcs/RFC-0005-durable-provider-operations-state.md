# RFC-0005: Durable Provider Operations State

- Status: Implemented
- Date: 2026-03-23
- Owners: lotus-ai
- Requires Approval From: lotus-ai maintainers

## Summary

`lotus-ai` should replace the current in-process provider operations counters with a durable, multi-instance-safe control plane.

RFC-0004 established truthful provider operations contracts and enforcement for:

1. quota posture,
2. budget posture,
3. degradation and circuit-breaker posture,
4. operator-facing operations summaries,
5. eval and runbook readiness for provider operations.

Those controls are now meaningful, but their underlying state is still process-local. That is the next high-value implementation gap.

## Why This Is Next

The platform now has:

1. real retrieval,
2. a controlled live provider backbone,
3. provider operations hardening contracts,
4. operator-facing runtime and governance summaries,
5. strong validation and CI discipline.

The biggest remaining gap between the current provider posture and enterprise-grade operation is that the provider control state is not durable:

1. quota counters reset with process restarts,
2. spend posture is tracked in-memory,
3. degradation and circuit state are instance-local,
4. multi-instance deployment would not share the same operational truth.

That makes the current control plane good for contract hardening, but not yet good enough for bank-grade production behavior.

## Problem Statement

Today provider operations state is held in process-local globals:

1. quota counters in [provider_quota_policy.py](../../src/app/services/provider_quota_policy.py#L1),
2. spend totals in [provider_budget_policy.py](../../src/app/services/provider_budget_policy.py#L1),
3. degradation and circuit-breaker counters in [provider_degradation_state.py](../../src/app/services/provider_degradation_state.py#L1).

That creates real limitations:

1. restart resets can understate quota, spend, and failure posture,
2. horizontal scaling would create conflicting operations truth across instances,
3. incident review cannot depend on one authoritative provider-ops state record,
4. rollout confidence remains lower than the surrounding governance surfaces imply.

## Goals

1. Introduce durable persistence for provider quota, budget, and degradation state.
2. Make provider operations summaries authoritative across restarts and instances.
3. Preserve the existing provider operations contracts while upgrading their backing state.
4. Keep writes bounded, explainable, and auditable.
5. Make reset, cooldown, and rollover semantics explicit and testable.

## Non-Goals

1. Multi-provider marketplace expansion.
2. External billing-system integration.
3. Replacing the existing provider governance surfaces.
4. Introducing an eventually consistent analytics warehouse for operator truth.
5. Broad generic rate-limiting abstractions outside provider operations.

## Current State

Today `lotus-ai` already has:

1. provider quota, budget, and operations endpoints,
2. hard-budget and quota blocking,
3. degraded-upstream and circuit-open behavior,
4. provider operations status embedded in platform runtime status,
5. eval and runbook posture covering provider operations.

Those surfaces should remain intact. The change in this RFC is the state model underneath them.

## Decision

`lotus-ai` will implement a durable provider operations state layer with explicit persistence and repository seams.

The first version should use the service database, not external infrastructure, and should persist:

1. quota counters by scope,
2. spend accumulation and budget checkpoints,
3. degradation counters and last-failure classification,
4. circuit-open cooldown state,
5. enough lifecycle metadata to explain resets and replay boundaries.

The external contracts for provider operations should remain stable wherever possible. The implementation focus is durability and correctness, not widening the public API unnecessarily.

## State Model and Invariants

This RFC establishes one authoritative rule:

1. provider quota, budget, and degradation truth must come from one durable state model,
2. runtime summaries and enforcement decisions must derive from that same durable state,
3. process-local memory may cache or assemble responses, but it must not become an independent source of operator truth,
4. no endpoint should mix durable counters with process-local fallback values once a slice is cut over.

The durable state model should preserve these invariants:

1. quota consumption must be atomic at the enforced scope,
2. budget accumulation must be monotonic unless an explicit governed reset is recorded,
3. degradation counters and circuit-open transitions must be durable across restart,
4. cooldown expiry must be derived from persisted timestamps rather than process uptime,
5. operator-visible blocking states must be explainable from persisted records and configuration.

## Architecture Direction

### Provider Operations Persistence

Add migration-managed tables for:

1. provider quota state,
2. provider budget state,
3. provider degradation state,
4. optional provider operations events if needed for incident-review clarity.

The persistence model should remain explicit and provider-ops-specific rather than hidden behind generic key-value storage.

### Repository and Service Boundaries

Introduce a provider operations repository seam so:

1. quota enforcement no longer mutates module globals,
2. budget accounting no longer relies on process memory,
3. degradation state no longer depends on singleton runtime variables,
4. test coverage can verify repository and service behavior directly.

### Consistency Model

The first delivery should be conservative and explicit:

1. writes happen synchronously in the provider control path,
2. enforcement reads from authoritative persisted state,
3. cooldown and reset semantics are deterministic,
4. restart behavior preserves provider-ops truth,
5. increments and state transitions that affect blocking behavior must be atomic,
6. the implementation should prefer simple transaction boundaries over asynchronous reconciliation.

### Runtime and Governance Surfaces

Existing endpoints should continue to expose:

1. quota posture,
2. budget posture,
3. degradation posture,
4. operations summary,
5. activation and governance readiness.

But those views should now report durable state rather than process-local snapshots.

### Cutover and Reset Semantics

The migration from process-local state to durable state should avoid split-brain truth.

Required cutover rules:

1. each slice must switch a control path fully to durable reads and writes rather than partially shadow-writing indefinitely,
2. if seed or bootstrap values are needed, they must be explicit and documented,
3. after cutover, restart behavior must demonstrate that operator state survives without hidden in-memory reconstruction,
4. any manual reset or rollover action must be represented as a governed state transition, not an undocumented table edit.

Required operational semantics:

1. quota windows must define their boundary and reset behavior explicitly,
2. budget periods must define whether they are cumulative or bounded to a named interval,
3. degradation recovery must define what clears counts, what only clears circuit-open state, and what remains as incident evidence,
4. cooldown timing must remain truthful even if the service restarts repeatedly during the cooldown window.

## Data and Operational Requirements

1. Provider operations state must survive service restart.
2. Multi-instance deployment must not create contradictory quota, budget, or degradation truth.
3. Circuit-open cooldown timing must be durable and testable.
4. Reset behavior must be explicit, bounded, and operationally reviewable.
5. State persistence must not leak credentials or raw provider payloads.
6. The database schema must be migration-managed and integration-tested.
7. Atomic write semantics must be explicit for quota consumption, spend accumulation, and degradation transitions.
8. Operator-facing summaries must be able to explain blocking state from persisted records without consulting process-local memory.
9. Repository unavailability must fail safely and truthfully rather than silently bypassing provider controls.

## Delivery Slices

### Slice 1: Durable Provider Operations Schema

Outcome:

1. migration-managed schema exists for provider quota, budget, and degradation state,
2. explicit repository contracts are introduced,
3. no public API behavior changes yet.

Acceptance gate:

1. schema is migration-managed,
2. repository contracts are unit-tested,
3. no hidden runtime table creation exists,
4. state entities and keys are specific enough that quota, budget, and degradation truth are not forced into a generic opaque blob.

### Slice 2: Durable Quota State

Outcome:

1. provider quota counters are persisted by scope,
2. quota enforcement uses the durable repository,
3. operator quota views report durable counts.

Acceptance gate:

1. restart does not reset quota truth,
2. scoped quota behavior remains truthful,
3. integration tests cover persisted enforcement,
4. concurrent quota consumption cannot undercount or silently over-admit due to non-atomic writes.

### Slice 3: Durable Budget State

Outcome:

1. spend totals and budget posture are persisted,
2. hard-budget blocking uses durable state,
3. operator budget views report authoritative spend posture.

Acceptance gate:

1. restart does not reset spend posture,
2. hard-budget blocking remains explicit,
3. tests cover persisted spend accumulation,
4. successful executions cannot double-count spend across retry or replay paths without an explicit recorded reason.

### Slice 4: Durable Degradation and Circuit State

Outcome:

1. failure counts and last-failure posture are persisted,
2. circuit-open cooldown state is durable,
3. degraded-upstream and circuit-open views survive restart.

Acceptance gate:

1. cooldown semantics are deterministic and tested,
2. incident-review summaries remain truthful,
3. invalid configuration and degraded state are still distinguished clearly,
4. repeated upstream failures across restarts still converge to the same durable circuit posture.

### Slice 5: Runtime, Eval, and Runbook Convergence

Outcome:

1. provider operations runtime summaries reflect durable state,
2. eval assets and run artifacts reflect the durable control plane,
3. runbooks describe reset and recovery procedures against the durable state model.

Acceptance gate:

1. runtime and governance summaries stay aligned,
2. eval and runbook assets match implementation reality,
3. the service is materially closer to enterprise-grade provider operations,
4. restart-survival and database-backed operator-truth scenarios are covered by meaningful tests rather than only unit-level helpers.

## Risks

1. poorly designed persistence could add write contention to the provider path,
2. overly generic abstractions could make provider operations harder to reason about,
3. hidden reset semantics could create false operator confidence,
4. persistence bugs in the control plane could block valid live execution or under-block unsafe execution.

## Alternatives Considered

### Alternative 1: Keep In-Memory State Longer

Rejected as the next implementation phase.

Reason:

1. the contract layer is already strong,
2. durability is now the highest-value correctness gap.

### Alternative 2: Push State Into External Caches First

Rejected for the first pass.

Reason:

1. it adds more infrastructure before the authoritative state model is proven,
2. the service database is the simplest reviewable first home for control-plane truth.

### Alternative 3: Broaden Provider Features Before Durability

Rejected for now.

Reason:

1. more live-provider breadth on top of process-local ops state would increase risk,
2. durability should come before broader activation.

## Acceptance Criteria

This RFC is complete when:

1. provider quota state is durable,
2. provider budget state is durable,
3. provider degradation and circuit state are durable,
4. provider operations summaries remain truthful across restart and instance boundaries,
5. runbooks and eval assets reflect the durable state model,
6. no provider-ops enforcement path depends on process-local mutable globals for operator truth,
7. reset, rollover, and cooldown semantics are explicit, durable, and reviewable,
8. the platform is materially closer to bank-grade live-provider operation.

## Implementation Notes

RFC-0005 has been implemented in five delivery slices plus a final closure-quality hardening pass:

1. Slice 1 introduced migration-managed provider-operations state tables, explicit repository contracts, and a dedicated provider-operations store seam.
2. Slice 2 moved provider quota posture onto the durable store so quota inspection and enforcement no longer depended on process-local counters.
3. Slice 3 moved provider budget posture onto the durable store so spend accumulation and hard-budget blocking remain durable across restart.
4. Slice 4 moved provider degradation and circuit-open posture onto the durable store so failure tracking and cooldown state survive restart.
5. Slice 5 aligned runtime summaries, eval assets, recorded run artifacts, and runbooks with the durable provider-operations control plane.
6. The final hardening pass moved quota, spend, and tracked degradation mutations into repository-owned atomic operations so blocking-state updates no longer depend on service-layer read-modify-write sequences.
7. The final closure work added durable provider-operations control events plus governed reset actions, so reset and recovery are now explicit, reviewable control-plane behavior instead of only a runbook aspiration.

The implemented result is:

1. quota, budget, and degradation truth now come from one durable provider-operations state model,
2. `/platform/providers/quota-policy`, `/platform/providers/budget-policy`, `/platform/providers/operations-status`, and `/platform/runtime-status` report that durable truth,
3. provider evidence, governance, and runbook surfaces now describe durable restart-survival and recovery posture honestly,
4. the provider control plane is materially closer to multi-instance-safe, bank-grade operator truth than the RFC-0004 in-memory posture it replaced.

## Approval Requested

Approve this RFC if the team agrees that:

1. durable provider operations state is the next highest-value platform gap,
2. the first authoritative state store should be the service database,
3. delivery should proceed in the slices defined above,
4. broader provider activation should remain secondary to durable control-plane correctness.
