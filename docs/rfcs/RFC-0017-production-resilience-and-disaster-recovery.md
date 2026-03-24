# RFC-0017: Production Resilience and Disaster Recovery

- Status: Draft
- Date: 2026-03-23
- Owners: lotus-ai
- Requires Approval From: lotus-ai maintainers

## Summary

`lotus-ai` should implement an explicit production resilience and disaster-recovery model so the platform can support real use cases without relying on implicit restart behavior, best-effort recovery, or architecture assumptions that are not yet governed.

This RFC is bounded to platform-owned continuity truth:

1. authoritative stores and critical dependencies,
2. backup and restore posture descriptions,
3. degraded versus restored runtime semantics,
4. operator-visible recovery inventory, ordering, and evidence.

It does not promise full infrastructure automation in one pass.

The platform now has:

1. durable provider operations state,
2. durable async and evaluation execution state,
3. growing runtime observability and incident-evidence expectations,
4. planned worker, artifact, and deployment-split evolution,
5. a first-use-case onboarding path that makes continuity a real operational requirement.

The next high-value step is to make resilience, backup, restore, and failover posture explicit and testable.

## Why This Is Next

The current platform already documents many local recovery expectations:

1. provider control-plane recovery,
2. async replay and lease-expiry recovery,
3. retrieval reindex and replay procedures,
4. startup readiness and degraded readiness policy,
5. split rollback and use-case rollback expectations in the newer RFCs.

But this is still not the same as a governed disaster-recovery and production resilience model.

What is still missing:

1. explicit backup and restore posture across durable stores,
2. cross-domain recovery ordering and ownership,
3. failover semantics for queue, worker, provider, retrieval, and artifact dependencies,
4. continuity testing expectations tied to real runtime state,
5. a single resilience model that downstream use cases can rely on.

## Problem Statement

`lotus-ai` has moved far beyond a stateless stub service:

1. multiple durable stores now hold platform-critical state,
2. worker and control-plane behavior depend on persisted records,
3. observability and incident evidence are becoming first-class,
4. the first real use case will require continuity guarantees, not just feature correctness.

Without an explicit resilience RFC:

1. backup and restore behavior can remain implicit,
2. domain-level recovery procedures can drift apart,
3. operator rollback might exist without durable recovery confidence,
4. production readiness may be overstated.

## Goals

1. Define a governed resilience and disaster-recovery model for `lotus-ai`.
2. Cover durable data stores, queue/worker paths, artifact storage, and provider/retrieval dependencies.
3. Make recovery ordering, ownership, and degraded-mode posture explicit.
4. Add meaningful verification of restore and failover scenarios.
5. Support the first real use case with a credible continuity story.

## Non-Goals

1. Building a full enterprise infrastructure platform inside `lotus-ai`.
2. Replacing deployment tooling or infrastructure automation owned elsewhere.
3. Solving every cloud or data-center failure mode at once.
4. Defining business continuity for downstream domain applications.
5. Treating simple process restart as sufficient disaster recovery.

## Current State

The platform already has:

1. startup and readiness policy controls,
2. durable async, evaluation, provider-operations, audit, retrieval, and prompt-related state,
3. control-plane recovery actions for some domains,
4. runbook-readiness and governance surfaces by domain.

The missing layer is a unified continuity model.

At present:

1. restart-survival has been addressed in several places,
2. but backup, restore, and cross-domain recovery are still fragmented,
3. and no single RFC defines what “production-resilient” means for the whole platform.

## Decision

`lotus-ai` will implement a production resilience and disaster-recovery model as a platform-wide operational capability.

The first production-capable resilience posture should:

1. define critical stores and dependencies,
2. define backup, restore, and recovery ordering,
3. define degraded-mode expectations when dependencies are unavailable,
4. define failover and rollback semantics where the platform already depends on durable runtime state,
5. require verification through meaningful recovery and restore testing.

The rollout posture for this RFC is intentionally staged:

1. `INVENTORIED_ONLY`
2. `ORDERED_RECOVERY_READY`
3. `DRILL_VERIFIED`

Slice 1 delivers the first posture only. It must not imply ordered restore or drill-backed readiness yet.

Slice 2 delivers the second posture. It must define restore ordering and validation criteria, but it still must not imply drill-backed readiness yet.

Slice 4 delivers the third posture. It adds drill-evidence, activation-readiness, runbook-readiness, and governance surfaces, but it still must not be mistaken for backup automation or full disaster-recovery orchestration.

## State Model and Invariants

This RFC establishes the following invariants:

1. durable runtime state must not depend on undocumented restart behavior,
2. backup and restore posture must be explicit for every authoritative store,
3. recovery ordering must preserve coherent platform truth across domains,
4. degraded readiness must not be mistaken for restored correctness,
5. rollback of application behavior must remain distinguishable from restore of durable state,
6. resilience posture must be reviewable through runtime, governance, and runbook surfaces.

## Architecture Direction

### Durable Store Recovery Model

Define recovery posture for each authoritative store.

Required behavior:

1. identify which stores are authoritative for audit, async, evaluation, provider ops, retrieval, prompt, and artifact state,
2. define backup and restore expectations per store,
3. define how cross-store consistency is validated after restore,
4. distinguish metadata restore from larger artifact/object restore where applicable.

Authoritative stores in scope for the first pass are:

1. audit
2. prompt rollout
3. retrieval metadata
4. caller policy
5. provider operations
6. async runtime
7. evaluation runtime
8. artifact metadata
9. artifact payload storage

### Queue, Worker, and Runtime Recovery

The async and worker model needs continuity beyond local replay semantics.

Required behavior:

1. queue and worker outage posture is explicit,
2. lease, replay, retry, and in-flight job recovery rules are defined after restore or failover,
3. dedicated worker and split-plane evolution inherit the same resilience rules,
4. stale or partial worker recovery is surfaced explicitly.

### Provider and Retrieval Dependency Resilience

External dependencies must have a resilience model too.

Required behavior:

1. provider degraded-upstream and circuit behavior ties into broader incident recovery,
2. retrieval indexing/search degradation and reindex posture are part of continuity planning,
3. rollback from degraded or unsafe runtime states is operationally clear,
4. recovery is not treated as a silent return to “healthy.”

### Runbook and Verification Convergence

Resilience only matters if it is testable and operable.

Required behavior:

1. domain runbooks roll up into one resilience model,
2. restore and failover drills are part of readiness evidence,
3. observability and incident evidence support recovery review,
4. the first real use case can depend on this continuity posture.

## Data and Operational Requirements

1. Every authoritative store must have an explicit recovery posture.
2. Restore ordering must be documented and reviewable.
3. Recovery success must be validated, not assumed.
4. Degraded-mode operation must be explicit where continuity is partial.
5. SQL-backed and storage-backed tests should prove meaningful restore semantics where feasible.
6. Runbooks must define incident ownership, restore procedures, and rollback boundaries.
7. Platform readiness and governance views must not overstate resilience.

## Delivery Slices

### Slice 1: Resilience Inventory and Recovery Contracts

Outcome:

1. authoritative stores and dependency recovery contracts are explicit,
2. resilience posture is modeled as a platform concern,
3. no major runtime behavior change yet.

Acceptance gate:

1. inventory is complete and bounded,
2. store and dependency ownership are explicit,
3. runtime/readiness surfaces stay truthful,
4. no hidden continuity assumptions remain undocumented.

Delivered interfaces for this slice:

1. `/platform/resilience/runtime-status`
2. embedded `resilience_runtime` block in `/platform/runtime-status`

Explicit non-goals for this slice:

1. no backup orchestration,
2. no restore-plan endpoint yet,
3. no drill evidence or resilience governance surface yet.

### Slice 2: Backup, Restore, and Recovery Ordering

Outcome:

1. backup and restore expectations exist for core stores,
2. recovery ordering is explicit,
3. restore success criteria are defined.

Delivered interfaces for this slice:

1. `/platform/resilience/restore-plan`
2. `delivery_stage=ORDERED_RECOVERY_READY` in `/platform/resilience/runtime-status`

Acceptance gate:

1. restore procedures are domain-aware,
2. cross-store recovery ordering is documented and tested where feasible,
3. rollback versus restore semantics are explicit,
4. runbooks match the recovery model.

### Slice 3: Runtime Recovery and Degraded-Mode Hardening

Outcome:

1. queue/worker, provider, retrieval, and artifact dependencies have explicit degraded/recovery posture,
2. recovery state is visible operationally,
3. continuity behavior improves materially.

Delivered interfaces for this slice:

1. `recovery_state` plus dependency-level recovery findings in `/platform/resilience/runtime-status`
2. embedded recovery-state summary in the `resilience_runtime` block of `/platform/runtime-status`

Acceptance gate:

1. degraded versus restored posture is explicit,
2. operator review can explain recovery state,
3. tests cover meaningful failure/recovery paths,
4. the platform does not overstate health during partial recovery.

### Slice 4: Recovery Drills, Evidence, and Governance Convergence

Outcome:

1. resilience evidence becomes part of governance posture,
2. recovery drills and restore proofs are reviewable,
3. first-use-case rollout can depend on continuity evidence.

Acceptance gate:

1. resilience readiness is reflected in runbooks and governance,
2. recovery evidence is current and reviewable,
3. first-use-case onboarding can cite the resilience posture credibly,
4. the platform is materially closer to enterprise-grade operational continuity.

Delivered interfaces for this slice:

1. `/platform/resilience/drill-evidence`
2. `/platform/resilience/activation-readiness`
3. `/platform/resilience/runbook-readiness`
4. `/platform/resilience/governance-status`
5. embedded `resilience_governance` block in `/platform/runtime-status`

## Risks

1. resilience scope could become too broad if not kept bounded to platform-owned dependencies,
2. recovery documentation without real verification would create false confidence,
3. overcomplicated restore semantics could outpace actual deployment needs,
4. weak degraded-mode signaling could confuse operators during incidents.

## Alternatives Considered

### Alternative 1: Defer Disaster Recovery Until After the First Use Case

Rejected.

Reason:

1. once a real use case is onboarded, continuity becomes part of platform credibility,
2. it is better to define the resilience model before promising broader operational readiness.

### Alternative 2: Treat Existing Domain Runbooks as Sufficient

Rejected.

Reason:

1. current runbooks are strong but fragmented by domain,
2. there is still no unified resilience and disaster-recovery model.

### Alternative 3: Solve Resilience Entirely in Infrastructure Outside `lotus-ai`

Rejected as the only answer.

Reason:

1. infrastructure support is necessary, but the platform still needs domain-aware recovery and degraded-mode semantics,
2. store, queue, provider, retrieval, and artifact behavior are not fully generic infrastructure concerns.

## Acceptance Criteria

This RFC is complete when:

1. `lotus-ai` has an explicit resilience and disaster-recovery model,
2. backup, restore, recovery ordering, and degraded-mode posture are defined for authoritative stores and dependencies,
3. runbooks and governance surfaces reflect that model truthfully,
4. meaningful recovery evidence exists,
5. the platform is materially closer to enterprise-grade production continuity.

## Approval Requested

Approve this RFC if the team agrees that:

1. production resilience and disaster recovery is the next high-value platform concern after the current runtime/onboarding sequence,
2. continuity must be treated as a governed platform capability rather than an implicit operational assumption,
3. the first real downstream use case should depend on explicit recovery posture,
4. delivery should proceed in the slices defined above.
