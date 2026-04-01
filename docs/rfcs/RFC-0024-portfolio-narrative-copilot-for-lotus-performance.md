# RFC-0024: Portfolio Narrative Copilot for lotus-performance

- Status: Draft
- Date: 2026-03-25
- Owners: lotus-ai, lotus-performance
- Requires Approval From: lotus-ai maintainers, lotus-performance maintainers

## Summary

`lotus-ai` now has:

1. a governed platform backbone,
2. a reusable capability-pack layer,
3. production go-live approval posture,
4. multi-app rollout governance,
5. one bounded first-use-case anchor through `lotus-performance` commentary.

What it still does not have is a truly high-value, product-defining AI feature that investment and
client-facing teams would actively change behavior to use.

This RFC defines that next step:

1. a `Portfolio Narrative Copilot` built specifically for `lotus-performance`,
2. grounded in `lotus-performance`'s actual analytics seams rather than generic summarization,
3. designed to convert structured analytics truth into decision-useful and audience-aware
   narratives,
4. while preserving strict ownership boundaries so `lotus-performance` remains the source of
   financial truth.

This is not "chat over performance data."

It is a bounded AI feature over:

1. TWR and benchmark-relative performance,
2. contribution and detractor/leader analysis,
3. attribution and benchmark context,
4. returns-series and period comparisons,
5. diagnostics and materiality facts already owned by `lotus-performance`.

## Why This RFC Exists

The current first real downstream use case is valuable, but deliberately narrow.

RFC-0016 proved that:

1. `lotus-performance` can send structured analytics facts to `lotus-ai`,
2. `lotus-ai` can return explanation-only commentary under governance,
3. bounded rollout, audit, evidence, and support posture can be reviewed truthfully.

That was the right first step.

But RFC-0016 is still too narrow to become the flagship product capability for portfolio users.

It is centered on:

1. one explanation-oriented contract,
2. one narrow commentary task shape,
3. one first-use-case onboarding and rollout template.

The next high-value feature must go further without abandoning those controls.

`lotus-performance` is the strongest current candidate because it already owns:

1. `POST /performance/twr`,
2. `POST /performance/benchmark`,
3. `POST /performance/mwr`,
4. `POST /performance/contribution`,
5. `POST /performance/attribution`,
6. `POST /integration/returns/series`,
7. durable execution state, async execution polling, and lineage capture.

It also already surfaces:

1. benchmark context,
2. diagnostics and reset behavior,
3. contribution and attribution evidence,
4. canonical period-based analytics over structured inputs,
5. reproducibility and execution lineage.

That means the app now has enough real analytical depth for an AI layer to do something
meaningfully useful:

1. explain what happened,
2. explain why it happened,
3. prioritize what matters,
4. tailor the explanation to a PM, reviewer, or client-facing audience,
5. do all of that without inventing portfolio truth.

## Relationship to RFC-0016

RFC-0016 should be kept and explicitly evolved, not deprecated.

Reason:

1. RFC-0016 remains the correct first bounded governance anchor,
2. its explanation-only contract is still the safest seed path,
3. its readiness, runbook, and governance surfaces remain the right rollout gate for the first
   `lotus-performance` integration,
4. its onboarding template remains the correct reference path for later integrations.

What changes now:

1. RFC-0016 becomes the narrow seed and limited-rollout anchor,
2. RFC-0024 expands that seed into a richer, reusable `lotus-performance` product capability,
3. the current `analytics_commentary.pack.v1` should be enhanced rather than replaced,
4. the existing RFC-0016 contract fields such as `analysis_scope`, `period_window`,
   `metric_deltas`, and `material_findings` should be treated as the minimum bounded subset of the
   broader narrative contract, not as the final product shape.

So the correct posture is:

1. keep RFC-0016,
2. preserve its rollout discipline,
3. extend its pack and contract model,
4. do not fork a second disconnected commentary path.

## Problem Statement

Today, `lotus-performance` can compute high-value analytics truth, but users still have to perform
too much manual interpretation and narrative assembly.

Current workflow pain:

1. users must inspect TWR, benchmark-relative, contribution, attribution, and returns-series
   outputs separately,
2. users must decide which facts are materially important,
3. users must translate those facts into PM-ready, client-ready, or reviewer-ready narratives,
4. users must manually reconcile diagnostics and benchmark context into the story,
5. commentary often becomes repetitive, inconsistent, or dependent on individual analyst effort.

Current `lotus-ai` limitation:

1. the first-use-case commentary path can explain a bounded set of material changes,
2. but it does not yet model a full portfolio narrative workflow,
3. it does not yet express audience mode explicitly,
4. it does not yet organize multiple analytics lenses into one governed explanation product,
5. it does not yet treat explanation completeness and material prioritization as first-class product
   quality requirements.

Without this RFC:

1. `lotus-ai` remains useful but not yet genuinely differentiated for portfolio teams,
2. commentary remains a narrow wrapper instead of a core workflow accelerator,
3. downstream teams may build ad hoc narrative layers outside the governed platform,
4. the strongest current product opportunity remains under-realized.

## Goals

1. Deliver one genuinely high-value AI feature for `lotus-performance`.
2. Turn multiple existing analytics surfaces into one bounded narrative capability.
3. Keep `lotus-performance` as the owner of financial facts, materiality policy, and final
   presentation semantics.
4. Support multiple audience modes without creating open-ended free prompting.
5. Make explanation quality depend on grounded completeness, prioritization, and evidence usage,
   not only output fluency.
6. Reuse and extend RFC-0016 and `analytics_commentary.pack.v1` rather than starting over.

## Non-Goals

1. Letting `lotus-ai` recompute TWR, contribution, attribution, or benchmark results.
2. Giving investment recommendations or portfolio decisions.
3. Replacing deterministic `lotus-performance` reporting surfaces.
4. Building a generic "chat with all performance data" experience.
5. Allowing raw portfolio dumps as the primary contract.
6. Making `lotus-ai` the final renderer of reports or client materials.

## Decision

`lotus-ai` will add a new `Portfolio Narrative Copilot` capability for `lotus-performance`.

This capability will:

1. be implemented as an enhancement of the existing `analytics_commentary.pack.v1` family,
2. remain explanation-oriented and evidence-backed,
3. compose bounded facts from existing `lotus-performance` analytics surfaces,
4. support explicit audience and narrative modes,
5. be governed as a named product capability rather than a free-form prompt wrapper.

The first implementation boundary is intentionally strict:

1. `lotus-performance` selects and supplies the narrative fact bundle,
2. `lotus-ai` transforms that bundle into a structured narrative response,
3. `lotus-ai` may not infer missing analytics facts that are absent from the bundle,
4. quality gates focus on materiality ordering, factual grounding, unsupported-input refusal, and
   audience fit,
5. rollout remains bounded by the existing first-use-case and capability-pack governance layers.

## Proposed Capability Shape

The copilot should produce one bounded response family with explicit audience mode.

### Audience Modes

The initial modes should be:

1. `executive_summary`
2. `pm_deep_dive`
3. `client_commentary`
4. `review_memo`

These are not arbitrary stylistic variants.

They represent different explanation constraints over the same portfolio truth.

### Required Upstream Narrative Bundle

The bundle should be assembled by `lotus-performance` from existing analytics APIs and execution
artifacts.

The initial contract should include:

1. portfolio and reporting context
2. period window and comparison basis
3. headline performance facts
4. benchmark-relative facts when available
5. contribution winners and detractors
6. attribution effects when available
7. material change findings selected by `lotus-performance`
8. diagnostics and caveat findings when relevant
9. lineage and execution references for reproducibility

Illustrative bundle sections:

1. `performance_summary`
2. `benchmark_context`
3. `contribution_highlights`
4. `attribution_highlights`
5. `returns_series_changes`
6. `diagnostic_findings`
7. `material_findings`
8. `evidence_refs`

### Actual lotus-performance Sources This RFC Builds On

The fact bundle should be derived from real `lotus-performance` surfaces, especially:

1. `POST /performance/twr`
2. `POST /performance/benchmark`
3. `POST /performance/contribution`
4. `POST /performance/attribution`
5. `POST /integration/returns/series`
6. `GET /performance/executions/{calculation_id}`
7. endpoint-specific async result retrieval paths
8. lineage and reproducibility artifacts already captured by `lotus-performance`

This keeps the AI layer grounded in shipped analytics rather than speculative future functionality.

## Architecture Direction

### 1. Narrative Assembly Must Stay in lotus-performance

`lotus-performance` should remain responsible for:

1. which analytics runs are authoritative,
2. how period comparisons are selected,
3. which changes are materially important,
4. what benchmark context applies,
5. which diagnostics or caveats must be surfaced.

`lotus-ai` should receive the narrative-ready fact bundle, not raw analytics sprawl.

### 2. Copilot Output Must Be Structured, Not Just Text

The response should include more than a single blob of prose.

The initial response family should include:

1. headline summary
2. key drivers
3. benchmark-relative interpretation
4. watch-outs or caveats
5. optional audience-tailored closing block
6. evidence and confidence metadata

This makes the feature reusable in UI, PM review, and reporting workflows.

### 3. Product Quality Must Be Pack-Specific

The quality bar should not be "text sounds good."

The capability must be evaluated on:

1. factual grounding against supplied metrics
2. materiality ordering
3. omission handling
4. unsupported-input refusal behavior
5. audience-mode correctness
6. conservative treatment of diagnostics and caveats

### 4. Diagnostics and Methodology Matter

This RFC should explicitly build on `lotus-performance`'s richer diagnostic posture, especially the
methodology and reset semantics hardening work reflected in RFC-043.

That means:

1. reset-heavy or caveated periods should not be narrated as ordinary periods,
2. benchmark context should be surfaced when it materially changes interpretation,
3. contribution and attribution statements should remain bounded by what the current runtime truly
   computes,
4. narrative mode must not flatten away methodological caveats.

### 5. This RFC Should Not Recreate the Archived lotus-core Review Pattern

The old "one giant assembled review endpoint" pattern was archived out of `lotus-core`.

This RFC should therefore avoid:

1. rebuilding a monolithic report assembly endpoint inside `lotus-ai`,
2. blurring the boundaries between canonical data, analytics, and final reports.

The right model is:

1. `lotus-performance` assembles bounded analytics facts,
2. `lotus-ai` generates governed narrative structure,
3. downstream app or report layer still owns final report packaging.

## Data and Operational Requirements

1. The narrative copilot must use only caller-supplied structured analytics facts and approved
   evidence refs.
2. The capability must preserve RFC-0016 explanation-only discipline for its initial rollout.
3. The capability must record audit, evidence, and audience mode in runtime state.
4. The capability must support degraded or blocked behavior for incomplete bundles, conflicting
   facts, or unsupported analytics mixes.
5. The capability must carry enough lineage back to the underlying `lotus-performance` executions
   to support supportability and review.
6. The capability must not silently claim analytics relationships that `lotus-performance` did not
   provide.

## Delivery Slices

### Slice 1: Contract and Pack Expansion

Outcome:

1. `analytics_commentary.pack.v1` is expanded into an explicit portfolio narrative pack,
2. audience modes are formalized,
3. the RFC-0016 commentary bundle becomes the minimum subset of the new contract.

Acceptance gate:

1. RFC-0016 compatibility is preserved,
2. the pack contract remains bounded and typed,
3. `lotus-performance` remains the owner of materiality selection and analytics truth.

### Slice 2: Narrative Fact-Bundle Integration

Outcome:

1. `lotus-performance` can assemble a richer fact bundle from TWR, contribution, attribution,
   returns-series, and benchmark context,
2. `lotus-ai` can consume that bundle through one product capability seam.

Acceptance gate:

1. no raw analytics recomputation is delegated to `lotus-ai`,
2. every narrative section traces back to actual `lotus-performance` surfaces,
3. incomplete bundle behavior is explicit and testable.

### Slice 3: Runtime-Backed Quality Gates

Outcome:

1. dedicated eval families exist for portfolio narrative quality,
2. product-quality checks cover factual grounding, materiality ordering, and audience fit.

Acceptance gate:

1. runtime-backed evidence exists,
2. unsupported-input and caveat-heavy periods are tested explicitly,
3. approval-gate posture is pack-specific rather than generic commentary-only.

### Slice 4: Governance, Runbook, and Operator Readiness

Outcome:

1. pack-specific observability, activation, runbook, and governance surfaces are complete,
2. support teams can inspect why a narrative was generated, blocked, or caveated.

Acceptance gate:

1. operator review does not depend on reading raw prompts or logs only,
2. lineage back to `lotus-performance` execution refs is inspectable,
3. rollback remains compatible with first-use-case and pack-governance posture.

### Slice 5: Product Maturity and Broader Reuse

Outcome:

1. the capability is promoted from a narrow first-use-case extension to a reusable
   `lotus-performance` feature family,
2. broader downstream consumers such as reporting or review layers can integrate through the pack.

Acceptance gate:

1. the commentary family is truthfully reusable, not only experimentally implemented,
2. RFC-0016 remains the bounded seed but no longer the only narrative shape,
3. product value is materially higher than the original first-use-case path.

## Risks

1. If the bundle is too thin, the feature becomes superficial commentary with little user value.
2. If the bundle is too broad, the feature turns into unbounded data-dump prompting.
3. If diagnostics and caveats are ignored, narratives may sound confident while hiding real
   methodology limits.
4. If audience modes are treated as pure style variants, product quality will drift.
5. If this RFC forks away from RFC-0016, rollout and governance posture will fragment.

## Success Criteria

This RFC is successful when:

1. `lotus-performance` users can request one bounded narrative capability that materially reduces
   manual commentary work,
2. the feature is clearly better than the current narrow commentary path,
3. every narrative remains grounded in shipped `lotus-performance` analytics and diagnostics,
4. RFC-0016 is enhanced into a stronger product seam rather than discarded.
