# RFC-0022: Production Go-Live Approval and Managed Infrastructure

- Status: Draft
- Date: 2026-03-25
- Owners: lotus-ai
- Requires Approval From: lotus-ai maintainers

## Summary

`lotus-ai` now has:

1. a governed runtime backbone,
2. a first downstream use case,
3. a production-standard deployment baseline,
4. resilience, embeddings, ingestion, and split-plane foundations,
5. a new product-maturity direction through capability packs.

What it still does not have is a clean, explicit path from:

1. technically working,
2. demo-capable,
3. prod-shaped local,

to:

1. actually approved for real production go-live.

This RFC defines that missing final-mile posture.

It focuses on:

1. managed secrets and managed object storage as real production requirements,
2. explicit go-live approval criteria for live-provider traffic,
3. downstream-use-case production activation criteria,
4. production-only operator and governance truth,
5. separation between platform readiness and business approval to serve real user traffic.

## Why This RFC Exists

Recent work established two important truths:

1. the platform can run successfully in a Dockerized, live-provider-enabled path,
2. that technical success still does not mean the platform is ready for real production use.

The current docs already distinguish:

1. `LOCAL_OR_DEMO_CAPABLE`,
2. `PROD_SHAPED_LOCAL`,
3. `PRODUCTION_READY`.

That was the right baseline.

But there is still a missing layer between "infrastructure posture looks production-shaped" and "the system is actually approved to handle real downstream production traffic."

The unresolved gap is not mostly deployment shape anymore.

It is:

1. managed infrastructure enforcement,
2. go-live approval discipline,
3. downstream-use-case production signoff,
4. production-only operational truth.

This RFC is intentionally second in the next sequence:

1. `RFC-0021` first defines what reusable product capabilities are,
2. `RFC-0022` then defines when those capabilities and their infrastructure are actually approved for real production traffic,
3. `RFC-0023` then governs how those approved capabilities expand across multiple applications.

This keeps the boundary clean:

1. `RFC-0021` is about product shape,
2. `RFC-0022` is about go-live approval,
3. `RFC-0023` is about estate-wide adoption governance.

## Problem Statement

Today, `lotus-ai` can correctly report a lot of important posture:

1. runtime health,
2. provider governance,
3. retrieval governance,
4. artifact governance,
5. resilience posture,
6. first-use-case readiness and governance,
7. production-baseline posture.

That is necessary, but still not sufficient for true production activation.

Current missing or still too-implicit areas:

1. deployment-managed secrets are still described as required, but are not yet modeled as a complete production go-live approval domain,
2. governed object storage is required conceptually, but the production path still needs a stricter operational signoff model than "not filesystem fallback",
3. live-provider enablement can be technically successful before a downstream use case is production-approved,
4. downstream limited rollout and active production rollout still need clearer separation,
5. platform production posture and downstream business go-live approval are still too easy to mentally conflate.

Without this RFC:

1. teams may mistake prod-shaped infrastructure for approved production rollout,
2. live-provider success may still be over-read as a go-live signal,
3. downstream production activation may be judged too informally,
4. the final production boundary remains more cultural than system-enforced.

## Goals

1. Define the explicit production go-live approval model for `lotus-ai`.
2. Make managed secrets and managed object storage first-class production approval domains.
3. Separate platform production readiness from downstream use-case production activation.
4. Introduce explicit production-only approval and rollback posture for live-provider traffic.
5. Ensure operators can inspect whether the service is:
   1. technically healthy,
   2. infrastructure-ready,
   3. production-approved,
   4. downstream-approved for live traffic.

## Non-Goals

1. Replacing RFC-0020 deployment-baseline work.
2. Re-implementing resilience and DR from RFC-0017.
3. Rebuilding live-provider runtime mechanics from RFC-0003 through RFC-0005.
4. Expanding product capability breadth directly.
5. Onboarding many new downstream apps in this RFC.
6. Creating the reusable capability-pack model itself.
7. Governing estate-wide multi-app rollout records.

## Decision

`lotus-ai` will add a dedicated production go-live approval layer above the current deployment baseline.

This layer will govern the final transition from:

1. production-capable platform posture,
2. to production-approved platform posture,
3. to production-approved downstream use-case posture.

The go-live model must explicitly cover:

1. managed secret posture,
2. managed object-storage posture,
3. live-provider rollout approval,
4. downstream use-case production approval,
5. production rollback and freeze posture.

## Production Approval Model

This RFC establishes four distinct approval states.

### State 1: Technically Running

Characteristics:

1. services are up,
2. runtime APIs work,
3. basic traffic can be processed.

This state is not sufficient for production.

### State 2: Production-Capable

Characteristics:

1. deployment baseline satisfies prod-shaped and production-capable infrastructure expectations,
2. required durable stores and workers are active,
3. technical dependencies are present.

This still does not mean go-live is approved.

### State 3: Platform Production-Approved

Characteristics:

1. managed secret posture is approved,
2. managed object-store posture is approved,
3. provider governance is approved for the intended live path,
4. resilience and operational runbook posture are sufficient for real production traffic,
5. the platform itself is approved to host real live AI flows.

### State 4: Use-Case Production-Approved

Characteristics:

1. a named downstream use case is approved for active production traffic,
2. downstream ownership and escalation are explicit,
3. runtime-backed evidence for that use case is current,
4. rollback and freeze posture are explicit,
5. activation is no longer merely limited-rollout ready.

## Architecture Direction

### Managed Secret Approval

The platform must treat deployment-managed secret posture as a production approval domain, not only a deployment recommendation.

Required behavior:

1. local `.env` files remain valid for local-only workflows,
2. production approval is blocked until secret injection posture is explicitly managed and approved,
3. live-provider and other production-grade secret consumers are reported through one coherent production approval surface.

### Managed Object-Storage Approval

The platform must treat managed object storage as a production approval domain, not merely a fallback classification.

Required behavior:

1. filesystem and memory backends remain non-production,
2. production approval requires a real governed object-store path,
3. artifact consumers that rely on production evidence must reflect that truth in approval posture.

### Live-Provider Go-Live Approval

The platform must distinguish:

1. provider technically enabled,
2. provider governance approved,
3. provider approved for real production traffic.

Required behavior:

1. live-provider activation cannot be interpreted only from runtime success,
2. production approval depends on governance, budget, quota, degradation, and managed infrastructure posture together,
3. rollback or freeze of provider traffic is a first-class operator action.

### Downstream Use-Case Production Approval

The platform must distinguish:

1. first-use-case limited rollout,
2. first-use-case production approval.

Required behavior:

1. a downstream use case cannot be considered active-production-ready only because the platform is technically production-capable,
2. use-case production approval requires explicit evidence, governance, runbook, and ownership posture,
3. limited rollout and active production must be reported separately and truthfully.

### Production Freeze and Rollback

The platform should support a bounded production freeze model.

Required behavior:

1. production activation can be blocked without tearing down the platform,
2. provider and use-case production posture can be rolled back independently when needed,
3. operators can see whether the platform is:
   1. approved,
   2. frozen,
   3. rolled back,
   4. blocked pending review.

## Data and Operational Requirements

1. Production approval must be inspectable through dedicated runtime and governance surfaces.
2. Managed secrets and object storage must be represented as first-class approval domains.
3. Live-provider production approval must remain separate from technical live execution support.
4. Downstream use-case production approval must remain separate from limited-rollout readiness.
5. Rollback and freeze posture must be explicit and reviewable.
6. Production-facing runbooks must match runtime truth.

## Delivery Slices

### Slice 1: Production Approval Contract and Status Surface

Outcome:

1. explicit production approval contracts exist,
2. the platform can report technically running vs production-capable vs production-approved,
3. managed secret and object-storage posture are represented directly.

Acceptance gate:

1. one production-approval runtime surface exists,
2. secret and object-storage posture are explicit,
3. platform and downstream approval states are not conflated.

### Slice 2: Managed Secret and Object-Storage Enforcement

Outcome:

1. production approval blocks correctly on unmanaged secrets and non-production object storage,
2. artifact-backed evidence and provider usage reflect that truth,
3. operator docs match runtime behavior.

Acceptance gate:

1. unmanaged secret posture is blocking,
2. fallback object-store posture is blocking,
3. related governance and runbook surfaces converge on the same truth.

### Slice 3: Live-Provider Production Approval and Freeze Controls

Outcome:

1. live-provider technical enablement is cleanly separated from production approval,
2. freeze and rollback semantics exist for provider go-live posture,
3. production traffic approval is reviewable and reversible.

Acceptance gate:

1. live-provider success cannot overstate production approval,
2. freeze and rollback posture are explicit,
3. provider operations and governance align on production truth.

### Slice 4: Downstream Use-Case Production Approval

Outcome:

1. downstream limited rollout and active production posture are clearly separated,
2. named use-case production approval exists,
3. shared ownership and rollback posture are explicit.

Acceptance gate:

1. a downstream use case can be production-blocked while the platform remains production-capable,
2. active-production approval is inspectable,
3. runbook, governance, and evidence posture converge.

This slice is intentionally about approval of named use cases, not broad multi-app rollout governance.

That later expansion belongs to `RFC-0023`.

### Slice 5: Production Go-Live Runbook and Closure

Outcome:

1. the platform has a real go-live checklist and rollback discipline,
2. operators can reason about production activation without reading multiple disconnected surfaces,
3. the repo has a clear final-mile production standard beyond baseline infrastructure posture.

Acceptance gate:

1. runbook and governance surfaces are complete,
2. production approval is no longer ambiguous,
3. docs and runtime surfaces say the same thing.

## Risks

1. overlapping too much with RFC-0020 would blur ownership,
2. building too much business-specific approval into the platform would overreach,
3. leaving approval too manual would undermine the value of the control plane,
4. making approval too rigid too early could slow valuable real adoption.

## Alternatives Considered

### Alternative 1: Treat RFC-0020 as the Final Production RFC

Rejected.

Reason:

1. RFC-0020 correctly establishes the deployment baseline,
2. it does not fully solve final production go-live approval.

### Alternative 2: Fold This Into a Future Downstream Adoption RFC

Rejected.

Reason:

1. platform go-live approval should exist before broad multi-app scaling,
2. downstream adoption should inherit a clear production truth rather than invent it.

### Alternative 3: Rely on Runbooks Only

Rejected.

Reason:

1. production approval must be inspectable through the service itself,
2. prose alone is too weak for a boundary this important.

## Initial Implementation Focus

The first implementation pass should stay narrow and disciplined.

Priority order:

1. production-approval contracts and runtime surface,
2. managed secret and object-storage approval enforcement,
3. provider production approval and freeze posture,
4. first-use-case production approval separation,
5. go-live runbook convergence.

## Acceptance Criteria

This RFC is complete when:

1. `lotus-ai` can distinguish production-capable from production-approved cleanly,
2. managed secrets and managed object storage are first-class approval domains,
3. live-provider technical success cannot be mistaken for production approval,
4. downstream limited rollout and active production approval are clearly separated,
5. operators can inspect production activation, freeze, rollback, and blocking posture truthfully.

## Approval Requested

Approve this RFC if the team agrees that:

1. the next step after product maturity work should be final-mile production go-live discipline,
2. deployment baseline alone is not enough,
3. managed secrets, managed object storage, provider approval, and downstream production approval must become explicit control-plane concepts,
4. implementation should proceed through the slices above.
