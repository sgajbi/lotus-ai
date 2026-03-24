# RFC-0015: Controlled Deployment Split Into Runtime, Retrieval, and Evals

- Status: Draft
- Date: 2026-03-24
- Owners: lotus-ai
- Requires Approval From: lotus-ai maintainers

## Summary

`lotus-ai` should introduce a governed deployment split into three internal planes only when the now-implemented single-service production baseline is stable enough to support that move without fragmenting contracts or governance:

1. `lotus-ai-runtime`
2. `lotus-ai-retrieval`
3. `lotus-ai-evals`

This RFC is not about breaking the product into loosely related microservices. It is about taking the deployable seams already anticipated by the architecture and turning them into one explicit, reversible, evidence-gated rollout path.

## Why This RFC Exists

The architecture has long identified runtime, retrieval, and evals as the first likely split path, but that idea now needs stricter governance.

That is true because the repo has moved materially since the early architecture notes:

1. async runtime is durable and worker-backed,
2. retrieval has its own runtime, governance, and evidence posture,
3. evals have their own durable runtime, approval-gate evidence, and artifact flows,
4. observability and artifact storage now expose domain-oriented operational truth,
5. RFC-0020 established the production-standard single-service baseline that later split work must build on.

The platform therefore no longer needs a vague future note. It needs one RFC that says:

1. what can split,
2. what must remain shared,
3. what state remains authoritative,
4. how routing and rollback work,
5. what evidence justifies each cutover stage.

## Relationship To Other RFCs

This RFC depends on other work already completed or still upcoming.

### Already Implemented

The split must build on these completed foundations:

1. `RFC-0011` dedicated workers and managed queue
2. `RFC-0012` caller identity and tenant-aware authorization
3. `RFC-0013` observability and incident-evidence surfaces
4. `RFC-0014` governed artifact and object-storage backbone
5. `RFC-0016` first downstream production use case onboarding
6. `RFC-0020` production-standard deployment baseline

### Still Separate

This RFC must stay distinct from:

1. `RFC-0017`, which is about resilience, restore, and disaster-recovery posture,
2. `RFC-0018`, which expands providers and embeddings,
3. `RFC-0019`, which expands governed document ingestion and corpus refresh.

Those RFCs may increase the value of a split, but they should not be folded into this one.

## Problem Statement

`lotus-ai` is no longer only a small foundation service. It now contains multiple durable and increasingly independent operational domains:

1. runtime request orchestration and live-provider control,
2. retrieval search, indexing, and corpus governance,
3. evaluation execution and approval evidence,
4. prompt, safety, authorization, audit, and observability control planes.

Keeping all of that in one deployable forever would eventually create:

1. noisy-neighbor interference between synchronous runtime traffic and domain-heavy retrieval or eval workloads,
2. uneven scaling pressure across unrelated concerns,
3. broader operational blast radius during deploys or incidents,
4. slower rollout of domain-specific runtime improvements.

But splitting too early or too loosely would create different problems:

1. fragmented external contracts,
2. duplicated policy and governance logic,
3. split-brain runtime truth,
4. harder rollback,
5. more infrastructure without meaningful operational gain.

The problem this RFC solves is not "how do we make more services." It is:

how do we evolve from one production-standard deployable into a controlled multi-plane topology without losing the coherent platform behavior already built into `lotus-ai`.

## Goals

1. Define one explicit and reversible deployment-split path into runtime, retrieval, and eval planes.
2. Preserve one coherent external `lotus-ai` contract surface for downstream Lotus apps.
3. Keep audit, authorization, safety, prompt, and observability semantics coherent across all planes.
4. Make routing, state ownership, cutover, and rollback observable and reviewable.
5. Ensure split activation happens only when there is clear operational evidence and a meaningful scaling reason.

## Non-Goals

1. Immediate repository breakup.
2. External API fragmentation into separate client-facing services.
3. Splitting every control-plane domain into its own deployable.
4. Replacing the RFC-0020 single-service production baseline before that baseline has proven stable.
5. Treating deployment split as a substitute for resilience, provider expansion, or ingestion work.

## Current Reality

The current platform is more split-ready than it used to be, but still intentionally unified.

### What Is Already True

1. the architecture explicitly anticipates later deployment split without external contract rewrite,
2. major domains already have durable stores, runtime surfaces, governance surfaces, and runbooks,
3. async, retrieval, eval, artifact, access-control, and observability seams are now explicit enough to reason about plane boundaries,
4. the production-baseline control plane now distinguishes:
   1. `LOCAL_OR_DEMO_CAPABLE`
   2. `PROD_SHAPED_LOCAL`
   3. `PRODUCTION_READY`

### What Is Still Missing

1. cross-plane governance and runbook hardening now exist through dedicated deployment-split activation, runbook, and governance surfaces,
2. retrieval-and-evals split remains an internal topology change while the runtime plane stays the only external front door,
3. unified rollback remains the only supported rollback target,
4. retrieval and eval split stages can both surface degraded posture, and operator guidance now converges on explicit rollback-to-`UNIFIED` rather than hidden fallback,
5. resilience and DR work remain explicitly separate under RFC-0017.

## Decision

`lotus-ai` will keep one external contract surface and introduce split deployment only as an internal topology change governed by explicit readiness, runtime truth, and rollback capability.

The first and only split path in scope for this RFC is:

1. runtime plane
2. retrieval plane
3. evaluation plane

This split must proceed through staged activation, not one big cutover.

## Deployment Stages

This RFC defines four deployment stages.

### Stage 0: Unified

Current posture.

1. one externally coherent API deployment,
2. one dedicated worker topology,
3. retrieval and eval execution remain internal domains of the same deployable shape,
4. plane ownership may be documented, but traffic is not yet split.

### Stage 1: Split-Ready

1. plane ownership, routing contracts, and runtime posture are modeled explicitly,
2. all required routing and rollback seams exist,
3. the platform can report whether each plane is unified or split-eligible,
4. no live plane cutover yet.

### Stage 2: Retrieval-Split Active

1. retrieval traffic and retrieval async work can be routed to a distinct retrieval plane,
2. the runtime plane remains the external front door,
3. unified rollback remains available.

### Stage 3: Retrieval-and-Evals-Split Active

1. retrieval and eval planes can run independently,
2. runtime remains the front-door plane,
3. audit, evidence, authorization, and observability remain coherent,
4. rollback to a more unified stage remains explicit.

## Plane Ownership Model

### Runtime Plane

The runtime plane owns:

1. external HTTP contract surface,
2. synchronous task execution orchestration,
3. provider orchestration and live-provider controls,
4. prompt selection and prompt control actions,
5. safety enforcement,
6. caller identity and authorization controls,
7. top-level routing and correlation,
8. the unified platform status surface.

### Retrieval Plane

The retrieval plane owns:

1. retrieval indexing execution,
2. retrieval search execution,
3. retrieval corpus and source governance,
4. retrieval-specific async paths,
5. retrieval-specific observability and incident-evidence production.

### Evaluation Plane

The evaluation plane owns:

1. evaluation execution,
2. evaluation approval evidence generation,
3. evaluation-specific artifact flows,
4. evaluation runtime and operator evidence surfaces.

### Shared Control-Plane Responsibilities

These must not be fragmented into conflicting sources of truth:

1. audit semantics,
2. caller identity and authorization semantics,
3. prompt governance semantics,
4. safety policy semantics,
5. artifact metadata lineage,
6. top-level observability and production-baseline truth.

## State Ownership Invariants

The split is valid only if these invariants remain true.

1. downstream Lotus apps still see one coherent external `lotus-ai` surface,
2. one authoritative store remains defined for each durable state domain,
3. no plane invents a private version of caller, tenant, audit, or policy truth,
4. cross-plane artifact references remain traceable and descriptor-first,
5. routing decisions are observable,
6. rollback from split mode does not require rewriting external contracts,
7. split activation must not silently weaken incident diagnosis or operator evidence.

## Routing Invariants

1. external clients continue to call the runtime plane,
2. split-aware routing is internal and explicit,
3. async routing remains bounded by job type and domain,
4. retrieval routing and eval routing must be independently observable,
5. a failed split plane must surface as explicit degraded posture rather than invisible in-process fallback.

## Readiness Preconditions

This RFC must not be implemented as the next step after a demo. It must be built only on a stable baseline.

Minimum preconditions:

1. RFC-0020 production-baseline surfaces remain truthful and stable,
2. the current single-service production baseline is the accepted default posture,
3. retrieval and eval control planes have enough runtime and observability truth to support split diagnosis,
4. there is actual scale, isolation, latency, or operational evidence that justifies split activation,
5. runbooks can explain unified and split rollback paths clearly.

## Data and Operational Requirements

1. shared durable state remains authoritative and reviewable,
2. cross-plane routing is observable,
3. split rollout is reversible,
4. retrieval and evaluation scaling improve materially when their planes are activated,
5. authorization, safety, prompt, and audit semantics remain intact,
6. runbooks define cutover, rollback, degradation, and incident ownership across planes,
7. tests prove contract stability and routing truth under unified and split-aware modes.

## Delivery Slices

### Slice 1: Split Readiness Contracts and Plane Ownership

Outcome:

1. split-stage contracts exist,
2. runtime, retrieval, and eval plane ownership is defined explicitly,
3. shared versus plane-owned responsibilities are modeled,
4. no traffic cutover yet.

Acceptance gate:

1. typed split-readiness and plane-ownership contracts exist,
2. platform/runtime surfaces can describe unified versus split-ready posture truthfully,
3. ownership boundaries are explicit enough to test,
4. no external contract fragmentation is introduced.

### Slice 2: Split-Aware Routing and Deployment-Mode Abstractions

Outcome:

1. internal routing can distinguish unified versus split-aware modes,
2. runtime plane remains the external front door,
3. retrieval and eval routing seams are explicit,
4. rollback to unified remains first-class.

Acceptance gate:

1. routing is observable and bounded,
2. rollback semantics are explicit and operator-visible,
3. tests cover unified and split-aware behavior,
4. state ownership remains coherent.

### Slice 3: Retrieval Plane Activation

Outcome:

1. retrieval becomes the first split-active plane,
2. runtime still fronts the external contract,
3. retrieval indexing and retrieval search can scale independently.

Acceptance gate:

1. retrieval routing works under split mode,
2. audit, authorization, and artifact semantics remain coherent,
3. degraded retrieval-plane posture is visible,
4. integration tests prove retrieval split behavior and unified rollback.

### Slice 4: Evaluation Plane Activation

Outcome:

1. evals become the second split-active plane,
2. evaluation execution and evidence flows can scale independently,
3. runtime remains the top-level contract plane.

Acceptance gate:

1. eval routing works under split mode,
2. approval evidence and artifact lineage remain coherent,
3. degraded eval-plane posture is visible,
4. integration tests prove evaluation split behavior and unified rollback.

### Slice 5: Cross-Plane Runbook, Observability, and Governance Hardening

Outcome:

1. split-mode runtime, activation, runbook, and governance surfaces are production-capable,
2. operators can diagnose cross-plane incidents,
3. governance can distinguish unified, split-ready, retrieval-split, and retrieval-and-evals-split posture,
4. the platform is ready for resilience work on top of the split model.

Acceptance gate:

1. runbooks match actual split deployment behavior,
2. cross-plane degraded posture is visible and actionable,
3. platform status and observability surfaces remain coherent across all stages,
4. rollback guidance is explicit and tested.

## Risks

1. the split could be activated before there is enough scale evidence to justify the operational cost,
2. unclear ownership could duplicate control-plane logic,
3. routing mistakes could hide failures behind misleading "healthy" top-level status,
4. rollback could be harder than expected if plane state boundaries are under-specified.

## Alternatives Considered

### Alternative 1: Keep One Deployable Indefinitely

Rejected as the long-term posture.

Reason:

1. the architecture already anticipates independent scaling pressure,
2. retrieval and evals are the clearest early split candidates.

### Alternative 2: Split External Contracts First

Rejected.

Reason:

1. it would create unnecessary downstream churn,
2. the architecture explicitly treats the first split as deployment topology, not client-facing contract breakup.

### Alternative 3: Fold Split Work Into RFC-0020

Rejected.

Reason:

1. RFC-0020 defines the single-service production baseline,
2. this RFC should start only after that baseline exists and is understood as the default.

### Alternative 4: Split More Than Three Planes Immediately

Rejected.

Reason:

1. that would over-fragment the service too early,
2. runtime, retrieval, and evals are the bounded first split path already documented by the architecture.

## Gold-Standard Acceptance Criteria

This RFC is complete only when:

1. the platform has an explicit, testable, and reversible split model,
2. runtime, retrieval, and evals can operate as separate deployable planes without external contract churn,
3. shared governance, audit, safety, authorization, and observability semantics remain coherent,
4. split rollout has clear readiness, evidence, degraded, and rollback posture,
5. platform and operator docs describe the same topology truth,
6. `lotus-ai` is materially closer to the long-term deployment architecture without sacrificing the production baseline established by RFC-0020.

## Approval Requested

Approve this RFC if the team agrees that:

1. the next topology milestone after the production-standard single-service baseline is a governed split into runtime, retrieval, and eval planes,
2. that split should remain internal and should not fragment external contracts,
3. retrieval should activate before evals,
4. delivery should proceed only through the slices and gates defined above.
