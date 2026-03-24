# RFC-0021: Domain AI Capability Packs and Product Maturity

- Status: Implemented
- Date: 2026-03-25
- Owners: lotus-ai
- Requires Approval From: lotus-ai maintainers

## Summary

`lotus-ai` now has a substantial governed platform backbone:

1. bounded task execution,
2. prompt governance,
3. retrieval,
4. runtime safety,
5. evaluation and approval gates,
6. async execution,
7. caller identity and access control,
8. observability and incident evidence,
9. artifact storage,
10. deployment, resilience, embeddings, and ingestion foundations.

That backbone is now real, but it is still more mature as a platform than as an AI product layer.

This RFC introduces the next major phase:

1. domain AI capability packs for real Lotus workflows,
2. richer app-facing contracts and outcome models,
3. stronger quality expectations for explanation and commentary behavior,
4. reusable product-grade integration patterns beyond the first use case.

The goal is to make `lotus-ai` not just governable and operationally sound, but also meaningfully useful as a shared AI product layer across the Lotus estate.

## Why This Is Next

The current state of `lotus-ai` is now clear:

1. the infrastructure and governance stack is materially implemented,
2. the first bounded downstream use case exists,
3. live-provider and Docker paths have been proven technically,
4. the remaining biggest gap is no longer "can the platform govern AI safely?" but "does the platform now offer enough app-facing capability depth to matter broadly?"

The missing layer is product maturity.

Today, `lotus-ai` is strongest as:

1. a control plane,
2. a runtime backbone,
3. a governance surface.

It is less mature as:

1. a catalog of domain-ready AI capabilities,
2. a reusable product layer for multiple Lotus applications,
3. a place where downstream teams can adopt high-value AI features without reconstructing domain shaping themselves each time.

That is the gap this RFC addresses.

This RFC is intentionally first in the next post-foundation sequence:

1. `RFC-0021` defines reusable app-facing capability packs,
2. `RFC-0022` defines final production go-live approval for those capabilities,
3. `RFC-0023` defines how those approved capabilities scale across multiple Lotus applications.

That ordering matters because:

1. multi-app rollout should scale reusable capabilities rather than one-off task wrappers,
2. production approval should govern real product capabilities rather than generic task seams alone,
3. broader adoption should happen only after both capability shape and go-live posture are explicit.

## Problem Statement

`lotus-ai` currently supports bounded task families such as:

1. `explain.v1`,
2. `summarize.v1`,
3. `generate_structured.v1`,
4. `knowledge_search.v1`,
5. `knowledge_answer.v1`.

Those are useful platform primitives, but they are still too generic to represent mature Lotus product capabilities by themselves.

Current limitations:

1. downstream apps still need to do too much capability shaping on their own,
2. the first-use-case path proves one narrow integration, but not yet a reusable family of app-facing AI product modules,
3. explanation and commentary behavior remain task-oriented rather than explicitly organized around recurring Lotus business use cases,
4. quality can be governed technically, but product expectations for completeness, grounding, tone, and domain-fit are not yet modeled as first-class capability packs,
5. the platform lacks an explicit maturity model for when a generic task becomes a reusable Lotus capability.

Without this RFC:

1. app integrations risk becoming one-off wrappers around generic tasks,
2. product behavior may fragment by downstream app,
3. platform reuse stays lower than it should be,
4. the service remains stronger operationally than it is functionally.

## Goals

1. Define a product-maturity layer above the generic task foundation.
2. Introduce domain AI capability packs for recurring Lotus workflow categories.
3. Keep the product layer bounded, typed, and governance-friendly.
4. Improve explanation and commentary quality standards without turning `lotus-ai` into an unbounded agent system.
5. Make future multi-app onboarding easier by giving downstream apps ready-to-adopt capability shapes rather than only generic task primitives.
6. Establish a maturity model for capability packs, from experimental to reusable to approved.

## Non-Goals

1. Building open-ended autonomous agents.
2. Letting `lotus-ai` take over domain-authoritative decisions.
3. Replacing deterministic logic in Lotus domain systems.
4. Introducing free-form tool use without bounded contracts.
5. Expanding into a consumer-style chatbot product.
6. Solving every downstream app use case in one RFC.
7. Defining final production go-live approval for those packs across the platform.
8. Governing multi-app rollout records and estate-wide adoption posture.

## Decision

`lotus-ai` will add a formal product-maturity layer through domain AI capability packs.

A capability pack is:

1. a bounded, named, reusable AI feature shape,
2. built on the existing task, prompt, retrieval, safety, and evaluation backbone,
3. specialized for one recurring Lotus workflow pattern,
4. governed as a reusable product capability rather than just a raw task invocation.

The Slice 1 contract boundary for this RFC is intentionally narrow:

1. add typed capability-pack descriptors,
2. expose a dedicated pack catalog separate from the generic task catalog,
3. anchor the first experimental pack to the existing `lotus-performance` commentary path,
4. do not yet claim reusable multi-app commentary families.

The first implementation phase should focus on commentary and explanation packs because they are:

1. already aligned with the current first-use-case posture,
2. safer than broader generative drafting,
3. highly reusable across multiple Lotus apps,
4. a strong fit for the existing `EXPLANATION_ONLY` and retrieval-backed foundations.

## Proposed Capability-Pack Model

Each capability pack should define:

1. a stable pack identifier,
2. one bounded outcome type,
3. one typed input contract family,
4. allowed upstream task and prompt composition,
5. safety and output-label expectations,
6. evaluation expectations,
7. rollout and governance expectations,
8. downstream ownership boundaries.

### Capability Pack Examples

Initial target categories should be:

1. analytics commentary packs,
2. decision-explanation packs,
3. evidence-backed knowledge packs,
4. structured review-summary packs.

Illustrative examples:

1. performance attribution commentary,
2. rebalance blocker explanation,
3. risk change explanation,
4. proposal review summary,
5. support anomaly summary.

These remain bounded product capabilities, not general-purpose free prompting.

## Product-Maturity Stages

This RFC establishes three capability maturity stages.

### Stage 1: Experimental

Characteristics:

1. bounded contract exists,
2. task and prompt wiring exist,
3. evaluation coverage is partial,
4. rollout is not yet reusable across multiple apps.

### Stage 2: Reusable

Characteristics:

1. capability contract is stable,
2. runtime-backed evaluation exists,
3. safety and observability posture are explicit,
4. downstream integration guidance exists,
5. the capability is usable by more than one Lotus app pattern with minimal reshaping.

### Stage 3: Approved

Characteristics:

1. governance, runbook, and evaluation posture are complete,
2. the capability is supportable operationally,
3. downstream ownership boundaries are explicit,
4. the capability can be onboarded without bespoke re-interpretation of the platform each time.

## Architecture Direction

### Capability Catalog

`lotus-ai` should expose a dedicated capability-pack catalog.

Required behavior:

1. generic task families remain available as platform primitives,
2. capability packs are described separately as app-facing product modules,
3. the catalog explains pack maturity, allowed use, expected output label, and required governance posture,
4. downstream teams can discover reusable product capabilities without reading multiple RFCs and runbooks.

### Pack-to-Task Composition

Capability packs should compose existing internals rather than invent a parallel runtime.

Required behavior:

1. packs resolve onto existing task contracts,
2. packs may select prompts, retrieval posture, and safety expectations through the existing governance layers,
3. packs do not bypass audit, evaluation, or access control,
4. pack-specific shaping lives at a clean service seam rather than being copied into app integrations.

### Product Quality Model

This RFC requires stronger quality expectations than "valid contract output."

Capability packs should define:

1. what grounded output means for that pack,
2. what conservative refusal means for that pack,
3. what unsupported or incomplete input means for that pack,
4. what constitutes acceptable commentary completeness,
5. which quality failures are product failures rather than mere style variance.

### Downstream Integration Model

Capability packs should make downstream integration easier, not looser.

Required behavior:

1. downstream apps still own domain facts and business meaning,
2. `lotus-ai` owns the bounded capability runtime and governance,
3. the integration layer becomes more reusable because apps adopt named packs rather than hand-assembling raw task behavior,
4. the first-use-case pattern from `lotus-performance` becomes the seed for broader pack-based adoption.

## Data and Operational Requirements

1. Every capability pack must remain grounded in caller-supplied or retrieval-governed inputs.
2. Every pack must declare its expected output label and safety posture.
3. Every pack must have runtime-backed evaluation requirements before it is considered reusable or approved.
4. Every pack must preserve audit and evidence traceability through the existing runtime backbone.
5. Every pack must define degraded behavior for incomplete, unsupported, or conflicting inputs.
6. Every approved pack must have clear downstream ownership and support boundaries.

## Delivery Slices

### Slice 1: Capability-Pack Contract and Catalog Foundation

Outcome:

1. capability-pack contracts exist,
2. a catalog surface exists,
3. maturity-stage modeling exists,
4. the platform can distinguish generic tasks from app-facing capability packs.

Acceptance gate:

1. typed capability-pack descriptors exist,
2. at least one operator-facing or integration-facing catalog surface exists,
3. pack maturity is explicit,
4. no duplicate runtime path is introduced,
5. the first experimental pack is anchored to the implemented first-use-case path without overstating reuse.

### Slice 2: Commentary and Explanation Pack Family

Outcome:

1. the first pack family is implemented around commentary and explanation behavior,
2. pack-specific input shaping and quality expectations exist,
3. the `lotus-performance` first-use-case path is absorbed into the broader pack model cleanly.

Acceptance gate:

1. commentary and explanation packs are named and typed,
2. the first-use-case path no longer feels one-off,
3. unsupported-input and refusal behavior are explicit,
4. downstream guidance exists for adopting those packs,
5. the current `lotus-performance` path is explicitly anchored to the commentary family instead of sitting beside it as a standalone product abstraction.

### Slice 3: Runtime-Backed Product Evaluation and Quality Gates

Outcome:

1. capability-pack evaluation families exist,
2. product-quality expectations are testable,
3. pack maturity advancement depends on runtime evidence rather than prose.

Acceptance gate:

1. each implemented pack has runtime-backed eval coverage,
2. pack quality gates distinguish product regressions from low-signal wording variance,
3. pack catalog and detail surfaces expose current quality-gate posture directly,
4. governance surfaces can report whether a pack is experimental, reusable, or approved truthfully.

### Slice 4: Pack Governance, Observability, and Operational Readiness

Outcome:

1. capability-pack runbook and governance posture exist,
2. observability can summarize pack usage and incidents,
3. downstream operators can inspect pack readiness without reconstructing it from lower-level platform surfaces.

Acceptance gate:

1. activation, runbook, and governance views exist for packs,
2. observability includes capability-pack posture and bounded usage review,
3. support and rollback expectations are explicit,
4. pack governance remains separate from generic provider, retrieval, or first-use-case surfaces.

### Slice 5: Multi-App Adoption Template

Outcome:

1. capability packs become the preferred downstream integration model,
2. later Lotus apps can onboard against packs rather than generic task families,
3. the service has a credible product-layer adoption pattern.

Acceptance gate:

1. downstream onboarding guidance is pack-oriented,
2. pack-native adoption templates exist for implemented pack families,
3. multi-app reuse is realistic,
4. pack-based adoption reduces bespoke app integration logic materially.

This slice deliberately stops short of full multi-app rollout governance.

That broader estate-wide rollout layer belongs to `RFC-0023`.

## Risks

1. making packs too generic would recreate the current ambiguity,
2. making packs too app-specific would hurt reuse,
3. treating product maturity as purely documentation would fail to improve actual quality,
4. introducing too many pack families too early would dilute the design,
5. downstream teams might still bypass packs unless the catalog and integration path are cleaner than raw task usage.

## Alternatives Considered

### Alternative 1: Keep Only Generic Task Families

Rejected.

Reason:

1. the platform already has generic tasks,
2. they are not sufficient by themselves to create broad reusable product value.

### Alternative 2: Jump Directly to Multi-App Onboarding Without a Product Layer

Rejected.

Reason:

1. that would scale one-off integrations instead of reusable product capabilities,
2. it would likely create fragmented downstream shaping logic.

### Alternative 3: Build Agentic Workflow Features First

Deferred.

Reason:

1. the highest-value next gap is product maturity for bounded capabilities,
2. agentic breadth would increase risk and complexity before this simpler product layer is fully formed.

## Initial Implementation Focus

The first implementation pass for this RFC should stay narrow.

Priority order:

1. capability-pack contracts and catalog,
2. commentary and explanation packs,
3. pack-specific runtime-backed evaluation,
4. pack governance and observability,
5. pack-oriented downstream onboarding guidance.

The first pack family should likely cover:

1. performance commentary,
2. rebalance blocker explanation,
3. risk change explanation.

That gives `lotus-ai` a coherent reusable product family before moving into broader drafting or more agentic interaction models.

## Acceptance Criteria

This RFC is complete when:

1. `lotus-ai` has a formal capability-pack layer above generic task families,
2. at least one reusable pack family exists as a product-layer capability even when runtime rollout evidence is still reviewed separately,
3. product-quality expectations are runtime-backed and governed,
4. downstream apps can adopt named packs rather than reconstructing raw task behavior,
5. the platform is meaningfully closer to broad AI product maturity rather than only runtime maturity.

## Approval Requested

Approve this RFC if the team agrees that:

1. the next major phase for `lotus-ai` should prioritize AI product maturity over more pure infrastructure by default,
2. domain AI capability packs are the right way to express that maturity,
3. commentary and explanation packs should be the first implementation family,
4. implementation should proceed through the slices above.
