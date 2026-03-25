# RFC-0023: Multi-App Adoption and Capability Rollout Governance

- Status: Implemented
- Date: 2026-03-25
- Owners: lotus-ai
- Requires Approval From: lotus-ai maintainers

## Summary

After `lotus-ai` has:

1. a governed runtime and platform backbone,
2. a bounded first real use case,
3. a product-maturity layer through capability packs,
4. a clearer production go-live approval model,

the next step is controlled multi-app adoption.

This RFC defines how `lotus-ai` should expand from:

1. one proven downstream integration,

to:

1. multiple Lotus applications using reusable AI capability packs under consistent rollout, ownership, and governance rules.

The focus is not only "more integrations."

It is:

1. repeatable adoption,
2. app-specific capability activation discipline,
3. shared ownership boundaries,
4. staged rollout governance across the Lotus estate.

## Why This RFC Exists

The platform has been built carefully to avoid premature sprawl.

That was the right strategy.

But once:

1. capability packs exist,
2. production approval becomes explicit,
3. the first use case is proven,

the main risk changes.

The next risk is fragmentation during adoption:

1. different Lotus apps shaping integrations differently,
2. capability packs rolling out inconsistently,
3. ownership and escalation becoming unclear,
4. app-by-app exceptions weakening the platform model.

This RFC exists to ensure that broad adoption increases leverage rather than entropy.

This RFC is intentionally third in the sequence:

1. `RFC-0021` defines reusable capability packs,
2. `RFC-0022` defines production approval for those capabilities and their managed infrastructure,
3. `RFC-0023` defines how approved capabilities roll out across the Lotus estate.

This RFC should not be started before the first two are sufficiently mature, because otherwise it would scale:

1. generic task wrappers instead of real capability packs,
2. technical success instead of production-approved posture.

## Problem Statement

Without a dedicated multi-app adoption RFC, `lotus-ai` risks scaling in the wrong way.

Possible failure modes:

1. each Lotus app creates its own bespoke wrapper around the same underlying capability,
2. rollout criteria differ by app in undocumented ways,
3. incident and support boundaries become ambiguous across downstream teams,
4. capability-pack maturity becomes disconnected from actual estate-wide adoption posture,
5. platform governance remains strong centrally while downstream usage becomes inconsistent.

The platform therefore needs:

1. a formal app-adoption model,
2. a capability rollout matrix by application,
3. clear ownership and escalation structure,
4. shared onboarding and retirement discipline.

## Goals

1. Define how `lotus-ai` capabilities should roll out across multiple Lotus apps.
2. Make capability-pack adoption app-aware and explicitly governed.
3. Standardize onboarding, rollout, pause, rollback, and retirement posture per app and per capability.
4. Preserve clear ownership boundaries between:
   1. `lotus-ai`,
   2. downstream application teams,
   3. shared operational responders.
5. Create a reusable adoption model so adding the third and fourth downstream app is cleaner than the first.

## Non-Goals

1. Creating one giant cross-app AI control plane that owns domain decisions.
2. Forcing every Lotus app onto `lotus-ai` immediately.
3. Eliminating app-specific shaping where it is truly necessary.
4. Replacing production-approval logic from RFC-0022.
5. Expanding into open-ended agentic multi-app workflows in this RFC.
6. Defining the reusable capability-pack model itself.
7. Acting as the final production go-live approval RFC.

## Decision

`lotus-ai` will introduce a formal multi-app adoption and capability rollout governance model.

This model will govern:

1. which applications may use which capability packs,
2. which maturity stage each app-capability pairing is in,
3. who owns rollout and incident decisions,
4. how adoption expands, pauses, rolls back, and retires over time.

The platform should no longer think only in terms of:

1. "is capability X implemented?"

It must also answer:

1. "which apps are allowed to use capability X?"
2. "what rollout stage is each app on?"
3. "who owns that usage?"
4. "what evidence and readiness posture supports that rollout?"

## Adoption Model

This RFC establishes the concept of an app-capability rollout record.

An app-capability rollout record represents:

1. one downstream Lotus application,
2. one named capability pack,
3. one rollout stage,
4. one ownership model,
5. one governance state.

### Rollout Stages

Each app-capability pairing should have one explicit stage.

### Stage 1: Not Onboarded

Characteristics:

1. capability pack exists or may exist,
2. the app is not yet approved to use it.

### Stage 2: Integration In Progress

Characteristics:

1. contracts and ownership are being established,
2. runtime and evaluation wiring may be underway,
3. the capability is not available for normal app traffic.

### Stage 3: Limited Rollout

Characteristics:

1. the app-capability path is active in a bounded production-like or small-scope mode,
2. support and incident posture are explicit,
3. wider app usage is still controlled.

### Stage 4: Active Production

Characteristics:

1. the app is approved for normal production use of the capability,
2. ownership and rollback posture are fully established,
3. evidence and observability are current.

### Stage 5: Paused or Rolled Back

Characteristics:

1. the capability remains known to the system,
2. the app is currently paused, frozen, or rolled back from active use,
3. the reason is explicit and inspectable.

### Stage 6: Retired

Characteristics:

1. the app-capability relationship is no longer active,
2. historical evidence and governance remain inspectable,
3. retirement rationale is preserved.

## Architecture Direction

### App-Capability Catalog

The platform should expose a rollout-aware app-capability catalog.

Required behavior:

1. capability packs are listed globally,
2. app-specific rollout state is inspectable,
3. not every app must use every capability,
4. operator and integration views can distinguish global pack maturity from app-specific rollout maturity.

### Ownership and Escalation Model

Every app-capability pairing should define:

1. platform ownership,
2. downstream app ownership,
3. shared support boundary,
4. escalation posture.

Required behavior:

1. incidents do not become ambiguous between central and downstream teams,
2. rollout ownership is explicit,
3. capability retirement and pause decisions are reviewable.

### Pack Reuse Without App Drift

Capability packs should remain reusable, but not force false uniformity.

Required behavior:

1. core pack behavior remains centralized,
2. bounded app-specific integration metadata can exist,
3. apps do not fork core pack behavior casually,
4. any app-specific divergence is visible and reviewable.

### Governance by Pairing, Not Only Globally

A capability may be globally mature while still blocked for a specific app.

Required behavior:

1. app-capability rollout truth is evaluated at the pairing level,
2. global capability approval does not imply all apps are approved,
3. downstream production approval remains app-specific even when the underlying pack is approved.

## Data and Operational Requirements

1. The system must be able to represent app-capability rollout records durably.
2. Each record must include rollout stage, ownership posture, and governance state.
3. Limited rollout, active production, pause, rollback, and retirement must be distinguishable.
4. The adoption model must integrate cleanly with existing capability, provider, resilience, and first-use-case governance.
5. Historical rollout state must remain inspectable for audit and support.

## Delivery Slices

### Slice 1: App-Capability Rollout Contracts and Catalog

Outcome:

1. app-capability rollout contracts exist,
2. a catalog view exists,
3. rollout stages are explicit.

Boundaries:

1. Slice 1 is status-only and catalog-first,
2. it must not yet add ownership, escalation, pause, rollback, or retirement controls,
3. it must keep global capability-pack maturity separate from app-specific rollout stage.

Acceptance gate:

1. the platform can represent app-capability pairings durably in contract form,
2. global pack maturity and app-specific rollout stage are not conflated,
3. at least one rollout catalog surface exists for operators or integrators,
4. the currently implemented `lotus-performance` pairing is represented truthfully without overstating limited-rollout or active-production posture.

### Slice 2: Ownership and Rollout Governance

Outcome:

1. each app-capability pairing has explicit ownership and escalation posture,
2. rollout, pause, rollback, and retirement state are modeled,
3. governance surfaces become pairing-aware.

Boundaries:

1. Slice 2 must stay pairing-level and must not yet expand into reusable onboarding workflow or estate-wide observability,
2. pause, rollback, and retirement may be modeled as explicit lifecycle transitions even when current pairings are not actively using those states,
3. global capability-pack maturity must remain separate from app-specific rollout governance.

Acceptance gate:

1. support boundaries are explicit,
2. pause and rollback are first-class states,
3. governance truth is inspectable per pairing.

### Slice 3: Multi-App Onboarding Workflow

Outcome:

1. onboarding a new app becomes a governed, reusable workflow,
2. downstream app teams can follow a standard path,
3. one-off bespoke onboarding logic is reduced materially.

Boundaries:

1. Slice 3 should compose existing pack and reference-use-case templates instead of inventing a second onboarding framework,
2. approval criteria must stay pairing-aware and must not imply estate-wide activation,
3. estate-wide rollout visibility remains out of scope for this slice.

Acceptance gate:

1. onboarding guidance is standardized,
2. multiple app targets can be modeled without custom governance logic,
3. rollout readiness is reusable and not rebuilt from scratch per app.

### Slice 4: Observability and Estate-Wide Rollout Visibility

Outcome:

1. observability can summarize adoption across apps,
2. operators can see where capabilities are active, blocked, paused, or retired,
3. estate-wide rollout posture becomes inspectable.

Boundaries:

1. Slice 4 should derive estate visibility from the existing rollout-record, governance, and bounded audit or async surfaces instead of creating a second adoption registry,
2. it may expose linked incident-review and rollout-review endpoints per pairing, but it must not yet add retirement-policy enforcement or lifecycle cleanup actions,
3. estate-wide visibility must keep app-capability pairing truth explicit instead of collapsing back into global pack-only maturity.

Acceptance gate:

1. app-capability rollout visibility is available,
2. incident review can be scoped by app and capability together,
3. platform-wide adoption posture is understandable without reading multiple disconnected endpoints.

### Slice 5: Retirement and Lifecycle Discipline

Outcome:

1. capabilities can be retired per app or globally in a governed way,
2. stale pairings do not linger indefinitely,
3. lifecycle management becomes part of the adoption model rather than an afterthought.

Boundaries:

1. Slice 5 should reuse the existing rollout detail, governance, and observability seams instead of creating a separate retirement registry,
2. it may add lifecycle-discipline review surfaces and make retirement transitions explicit for stale pairings, but it must not yet introduce destructive control-plane actions,
3. historical traceability must remain reviewable through linked rollout, onboarding, and observability surfaces instead of implicit operator knowledge.
4. retirement should state whether it is pairing-only or whether broader capability-pack follow-on review is required.

Acceptance gate:

1. retirement posture is modeled,
2. historical traceability remains intact,
3. app-capability sprawl can be cleaned up safely.

## Risks

1. over-centralizing app rollout could make downstream teams feel constrained in unhelpful ways,
2. under-centralizing it would recreate inconsistent one-off integrations,
3. too much metadata without strong runtime truth would produce paperwork rather than control,
4. lifecycle sprawl could still happen if retirement and rollback are not first-class.

## Alternatives Considered

### Alternative 1: Let Multi-App Adoption Happen Informally

Rejected.

Reason:

1. that would scale inconsistency,
2. it would weaken the shared-platform model right when adoption grows.

### Alternative 2: Treat Capability Approval as Global Only

Rejected.

Reason:

1. a capability can be mature globally while still inappropriate or unready for a specific app,
2. app-level rollout truth matters.

### Alternative 3: Put All Adoption Logic Into Each Downstream App

Rejected.

Reason:

1. that would duplicate governance patterns,
2. it would make `lotus-ai` less reusable over time.

## Initial Implementation Focus

The first implementation pass should stay tight:

1. app-capability rollout contracts,
2. catalog and rollout-stage surfaces,
3. ownership and governance posture,
4. observability over adoption state,
5. reusable onboarding and retirement workflow.

Initial target downstream apps after `lotus-performance` should likely include:

1. `lotus-manage`,
2. `lotus-risk`,
3. `lotus-advise`.

But this RFC should implement the adoption model first, not force all three onboardings immediately.

The intended pattern is:

1. one or more capability packs become reusable through `RFC-0021`,
2. those packs gain production approval discipline through `RFC-0022`,
3. this RFC then rolls them out across multiple apps with explicit pairing-level governance.

## Acceptance Criteria

This RFC is complete when:

1. `lotus-ai` has a formal multi-app adoption and rollout-governance model,
2. app-capability pairings are explicit and inspectable,
3. onboarding, limited rollout, active production, pause, rollback, and retirement are all modeled,
4. ownership and escalation are clear,
5. the platform is ready to scale beyond one downstream app without devolving into bespoke integrations.

## Approval Requested

Approve this RFC if the team agrees that:

1. multi-app adoption should be treated as a governed platform capability, not just a series of ad hoc integrations,
2. app-capability rollout records are the right abstraction,
3. ownership, rollout stage, and lifecycle posture must be explicit per app-capability pairing,
4. implementation should proceed through the slices above.
