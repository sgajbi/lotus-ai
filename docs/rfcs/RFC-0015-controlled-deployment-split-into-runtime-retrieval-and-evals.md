# RFC-0015: Controlled Deployment Split Into Runtime, Retrieval, and Evals

- Status: Draft
- Date: 2026-03-23
- Owners: lotus-ai
- Requires Approval From: lotus-ai maintainers

## Summary

`lotus-ai` should define and execute a controlled deployment split into runtime, retrieval, and evaluation service planes when scale and operational pressure justify it, while preserving the existing external platform contracts.

The architecture already documents this as the likely first split path:

1. `lotus-ai-runtime`
2. `lotus-ai-retrieval`
3. `lotus-ai-evals`

The platform is approaching the point where that path should be governed as an explicit RFC rather than remain only a future note in the architecture.

## Why This Is Next

The platform now has multiple increasingly real subdomains:

1. provider execution and operations controls,
2. retrieval indexing and planned live retrieval activation,
3. runtime-backed async and evaluation execution,
4. prompt, safety, and authorization control planes,
5. growing observability and artifact-storage requirements.

The codebase has already been shaped to keep those domains separable, but deployment is still unified.

That is fine while volume is moderate, but the documented architecture already expects later separation:

1. [scalability-and-deployment-model.md](C:/Users/Sandeep/projects/lotus-ai/docs/architecture/scalability-and-deployment-model.md#L1) says internal seams must stay clean enough for later deployable splits,
2. the same document names `lotus-ai-runtime`, `lotus-ai-retrieval`, and `lotus-ai-evals` as the likely first split path,
3. the existing contracts and repository seams are increasingly ready for that move.

## Problem Statement

`lotus-ai` is intentionally being built as one service first, but it is no longer just a lightweight foundation:

1. retrieval and evaluation now have their own durable runtimes,
2. provider operations have their own control plane,
3. async execution is durable and moving toward dedicated workers,
4. observability and artifact storage will increase domain-specific operational pressure further.

If all of that remains in a single deployable indefinitely, the platform will eventually pay a price in:

1. noisy-neighbor interference,
2. uneven scaling,
3. operational blast radius,
4. slower rollout of domain-specific runtime capabilities.

At the same time, splitting too early or without strict governance would create:

1. broken external contracts,
2. duplicate policy logic,
3. split-brain operational truth,
4. accidental re-introduction of service boundaries that the current repo already keeps coherent.

## Goals

1. Define a governed deployment split path before ad hoc decomposition pressure appears.
2. Preserve the current external contract surface while allowing internal deployable separation.
3. Keep runtime, retrieval, and evaluation ownership boundaries explicit.
4. Minimize split-brain risks around durable state, observability, and control planes.
5. Ensure the split is operationally justified and reversible.

## Non-Goals

1. Immediate codebase or repository breakup.
2. External API rewrites for downstream Lotus apps.
3. Broad microservice decomposition beyond the three named planes.
4. Splitting ownership of core policy, audit, or identity semantics across unrelated stacks.
5. Treating deployment decomposition as a substitute for fixing runtime/control-plane weaknesses first.

## Current State

The platform already has the necessary architectural precursors:

1. explicit repository seams and service seams by domain,
2. durable runtime state for async, evaluation, retrieval metadata, provider operations, and audit,
3. explicit runtime-status, readiness, governance, and runbook surfaces by domain,
4. a documented target worker/API split and future service split path,
5. bounded contracts that can remain stable while internal deployment changes.

The missing piece is an explicit split-control plan:

1. what moves first,
2. what remains shared,
3. how routing and ownership work,
4. how rollback works,
5. what evidence justifies each split stage.

## Decision

`lotus-ai` will define a controlled deployment split path into runtime, retrieval, and evaluation planes, but only through a governed staged rollout that preserves one external contract surface.

The first implementation of this RFC should:

1. formalize shared versus split responsibilities,
2. define the routing and state-ownership model,
3. keep audit, identity, safety, and contract governance coherent across the split,
4. treat deployment split as an operational change rather than a product-contract rewrite,
5. require rollback and observability readiness before any live cutover.

## State Model and Invariants

This RFC establishes the following invariants:

1. downstream Lotus apps continue to see one coherent external `lotus-ai` contract surface,
2. deployment split must not create duplicate sources of truth for runtime state,
3. audit, safety, identity, and authorization boundaries remain explicit across all split planes,
4. retrieval and evaluation domain services may scale independently, but shared governance semantics must remain coherent,
5. deployment routing and rollback state must be reviewable,
6. split rollout must not silently weaken observability or incident response.

## Architecture Direction

### Shared Front Door and Contract Preservation

The external API surface should remain unified even if internal deployment planes split.

Required behavior:

1. one coherent front-door contract remains for Lotus apps,
2. routing to retrieval or evaluation planes is internal,
3. external OpenAPI contracts do not fragment unnecessarily,
4. API versioning and vocabulary remain stable.

### Domain Plane Ownership

Define explicit ownership boundaries for each plane.

Required behavior:

1. runtime plane owns synchronous task execution, provider orchestration, prompt/safety/identity controls, and top-level orchestration,
2. retrieval plane owns retrieval indexing, retrieval search execution, retrieval corpus governance, and related worker/runtime paths,
3. evaluation plane owns evaluation execution, approval evidence, and evaluation artifact flows,
4. shared durable stores remain authoritative where appropriate rather than being duplicated per plane without need.

### Routing and State Convergence

Internal routing must preserve coherent runtime truth.

Required behavior:

1. request and async routing are explicit and observable,
2. shared state ownership is documented and bounded,
3. cross-plane relationships such as audit, approval evidence, and artifact references stay traceable,
4. rollback to unified deployment remains possible.

### Operational and Governance Convergence

Split rollout should only happen when the platform can run it safely.

Required behavior:

1. observability and incident-evidence surfaces can explain cross-plane behavior,
2. worker, artifact, and authorization controls remain coherent,
3. domain runbooks define cross-plane escalation and rollback,
4. split rollout is governed by explicit readiness and evidence gates.

## Data and Operational Requirements

1. Shared durable state must remain authoritative and reviewable.
2. Cross-plane routing must be observable.
3. Split rollout must be reversible.
4. Retrieval and evaluation scaling must improve materially when split is activated.
5. Authorization, safety, and audit semantics must remain intact across the split.
6. Runbooks must define cutover, rollback, degradation, and incident ownership clearly.
7. Tests must prove contract stability across split-aware routing.

## Delivery Slices

### Slice 1: Split Readiness Model and Plane Ownership Contracts

Outcome:

1. explicit split-readiness contracts and ownership rules exist,
2. shared versus domain-specific responsibilities are defined clearly,
3. no deployment cutover yet.

Acceptance gate:

1. ownership boundaries are explicit,
2. routing and state responsibilities are documented and testable,
3. runtime surfaces remain truthful,
4. no accidental contract fragmentation is introduced.

### Slice 2: Internal Routing and Deployment-Mode Abstractions

Outcome:

1. internal routing seams support unified versus split deployment modes,
2. domain-specific planes can be enabled without external contract change,
3. rollback to unified deployment remains explicit.

Acceptance gate:

1. internal routing is observable and bounded,
2. rollback semantics are explicit,
3. tests cover unified and split-aware routing behavior,
4. state ownership remains coherent.

### Slice 3: Retrieval and Evaluation Plane Activation

Outcome:

1. retrieval and evaluation become the first deployable split planes,
2. runtime plane continues to front the external contract,
3. domain scaling improves without contract rewrite.

Acceptance gate:

1. retrieval and evaluation routing work under split mode,
2. audit, approval evidence, and artifact references remain coherent,
3. cross-plane observability is sufficient,
4. integration and runtime tests prove behavior under split mode.

### Slice 4: Runbook, Observability, and Governance Hardening

Outcome:

1. split-mode observability, incident evidence, and runbooks are production-capable,
2. governance can review split readiness explicitly,
3. operators can diagnose and roll back split deployment safely.

Acceptance gate:

1. runbooks match split deployment reality,
2. governance distinguishes unified versus split readiness,
3. degraded cross-plane posture is visible and actionable,
4. the platform is materially closer to the documented bank-grade deployment target.

## Risks

1. splitting too early could widen operational complexity without enough payoff,
2. weak ownership boundaries could duplicate logic and create split-brain truth,
3. routing mistakes could damage latency or incident diagnosis,
4. rollback could be harder than expected if state boundaries are not kept disciplined.

## Alternatives Considered

### Alternative 1: Keep One Deployable Indefinitely

Rejected as the long-term posture.

Reason:

1. the platform architecture already anticipates scale pressures that justify split deployment,
2. retrieval and evaluation are the clearest candidates for independent scaling.

### Alternative 2: Split Repository and External Contracts First

Rejected.

Reason:

1. that would create unnecessary downstream churn,
2. the architecture explicitly says the first split should be a deployment split, not a contract rewrite.

### Alternative 3: Split Many More Planes at Once

Rejected.

Reason:

1. it would over-fragment the platform too early,
2. runtime, retrieval, and evaluation are the bounded first split path already supported by the architecture.

## Acceptance Criteria

This RFC is complete when:

1. the platform has an explicit, testable, and reversible deployment split model,
2. runtime, retrieval, and evaluation can operate as separate deployable planes without external contract churn,
3. shared governance, audit, safety, identity, and observability semantics remain coherent,
4. split rollout has clear readiness, evidence, and rollback posture,
5. the platform is materially closer to the documented long-term deployment architecture.

## Approval Requested

Approve this RFC if the team agrees that:

1. the next architecture-level milestone after the current runtime/control-plane sequence is a governed deployment split path,
2. the first split should be runtime, retrieval, and evaluation planes only,
3. external contracts should remain unified while deployment topology evolves,
4. delivery should proceed in the slices defined above.
