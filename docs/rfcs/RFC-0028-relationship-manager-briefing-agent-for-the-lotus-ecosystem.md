# RFC-0028: Relationship Manager Briefing Agent for the Lotus Ecosystem

- Status: Draft
- Date: 2026-04-13
- Owners: lotus-ai, lotus-gateway, lotus-workbench
- Requires Approval From: lotus-ai maintainers, lotus-gateway maintainers, lotus-workbench maintainers, lotus-core maintainers, lotus-performance maintainers, lotus-risk maintainers, lotus-manage maintainers, lotus-advise maintainers, lotus-report maintainers

## Summary

`lotus-ai` now has:

1. a governed shared AI platform backbone,
2. bounded provider, retrieval, prompt, safety, evaluation, and async runtime posture,
3. app-level rollout governance through capability packs,
4. draft product-facing RFCs for strong but still single-domain copilots.

What it still does not have is a clearly differentiated, cross-domain agentic workflow that proves
why Lotus should have a shared AI service at the operating layer, not only at the infrastructure
layer.

This RFC defines that next step:

1. a `Relationship Manager Briefing Agent`,
2. designed to prepare bankers and relationship managers for client-facing action,
3. grounded in real portfolio, performance, risk, workflow, proposal, and reporting evidence from
   Lotus source systems,
4. implemented as governed domain-tool orchestration rather than a generic chatbot.

This is not "chat with the platform."

It is a bounded, auditable, evidence-backed briefing and next-best-action capability over:

1. portfolio and mandate context from `lotus-core`,
2. return and attribution context from `lotus-performance`,
3. concentration, exposure, and breach context from `lotus-risk`,
4. management-side workflow context from `lotus-manage`,
5. proposal and opportunity context from `lotus-advise`,
6. reporting readiness and evidence context from `lotus-report`.

## Why This RFC Exists

The Lotus ecosystem is now mature enough that front-office preparation is increasingly an
interpretation, prioritization, and orchestration problem rather than a missing-data problem.

Relationship managers and bankers often need to know, in one concise operating view:

1. what changed in the client book,
2. which portfolios need attention,
3. whether any risk, mandate, liquidity, or review obligation now matters,
4. whether a proposal, report, or workflow gap exists,
5. what the best next action is and why.

The platform already contains most of the required truth, but it is spread across multiple products
and workflows.

Without a governed agentic layer:

1. users still inspect multiple product surfaces manually,
2. action prioritization depends too much on individual operator effort,
3. material changes are detected inconsistently,
4. AI remains a passive explanation utility rather than a workflow accelerator,
5. the business value of `lotus-ai` remains narrower than it should be.

This RFC exists because the next high-value AI feature should:

1. cut across multiple domain systems,
2. save real banker time,
3. produce reviewable workflow value,
4. preserve clear source-of-truth ownership,
5. establish a reusable pattern for later cross-domain AI features.

## Relationship to Existing RFCs

This RFC should build on existing `lotus-ai` and Lotus-platform governance rather than starting a
parallel architecture.

Most importantly:

1. RFC-0021 in `lotus-ai` established the domain AI capability-pack direction,
2. RFC-0023 established downstream app-capability rollout governance,
3. RFC-0024 and RFC-0025 established the pattern of high-value, bounded, domain-shaped copilots,
4. platform RFC-0069 established that `lotus-ai` is a shared AI capability service and not the
   owner of domain business truth,
5. platform RFC-0081 slices 9 and 10 established that AI-facing product surfaces need explicit
   provenance, review-state, audit, and assistive-action controls.

That has direct consequences for this RFC:

1. do build on the capability-pack model,
2. do build on rollout governance and runtime-backed audit posture,
3. do build on existing prompt, retrieval, safety, eval, and async seams,
4. do not let `lotus-ai` become a monolithic owner of business semantics,
5. do not reduce the feature to a generic UI chatbot or free-prompt overlay.

## Problem Statement

Today, Lotus can surface a large amount of useful client, portfolio, analytics, and workflow truth,
but front-office users still have to assemble too much meaning manually.

Typical preparation pain includes:

1. inspecting portfolio posture in one place and performance drivers in another,
2. checking risk or concentration changes separately from management workflows,
3. noticing stale proposals or stale reviews too late,
4. translating raw system state into banker-ready briefing language,
5. deciding which follow-up action matters most when several signals compete for attention.

Current AI limitation:

1. `lotus-ai` can already explain or summarize bounded inputs,
2. but it does not yet own a multi-tool, cross-domain, action-oriented briefing workflow,
3. it does not yet turn platform signals into one RM-ready operating artifact,
4. it does not yet define a reusable "domain APIs as agent tools" feature pattern for this class of
   workflow.

Without this RFC:

1. `lotus-ai` remains strong as platform infrastructure but less differentiated as a product driver,
2. downstream teams may improvise narrow AI summarizers with weaker governance,
3. front-office preparation remains slower and less consistent than it should be,
4. the strongest agentic product opportunity in the current Lotus estate remains unrealized.

## Business Value

This feature is high-value because it directly improves banker readiness and client-servicing
quality.

Expected value areas:

1. faster daily preparation for RM books and priority client reviews,
2. earlier visibility into material portfolio, risk, and workflow changes,
3. more consistent follow-up on stale reviews, stale proposals, and unresolved actions,
4. stronger reuse of Lotus as one operating platform instead of disconnected modules,
5. better banker-facing narrative quality without moving business truth away from domain services.

This is more valuable than a generic assistant because it is tied to:

1. actual portfolio and client-servicing workflows,
2. explicit next-best-action generation,
3. real downstream workflow handoff opportunities,
4. measurable operator time savings and follow-up quality.

## Primary Use Cases

### 1. Daily RM briefing

Each morning, the banker requests or receives a ranked book-level briefing that summarizes:

1. clients or portfolios that need attention,
2. what changed since the previous review,
3. why the change matters,
4. which next actions are recommended,
5. what evidence supports those recommendations.

### 2. Pre-meeting client briefing

Before a client or portfolio review meeting, the banker requests an on-demand briefing for one
client or portfolio scope.

The feature assembles:

1. current portfolio context,
2. recent performance and benchmark-relative changes,
3. active risk or mandate issues,
4. open operational or management-side actions,
5. stale or relevant proposal opportunities,
6. reporting readiness and evidence availability.

### 3. Exception-driven briefing

When a material change or breach is detected, the feature can prepare a bounded briefing that
explains:

1. what triggered attention,
2. what cross-system evidence is relevant,
3. what the likely client-service implication is,
4. which next checks or actions should be reviewed.

### 4. Stale-action recovery

The feature identifies:

1. overdue reviews,
2. stale proposals,
3. unresolved management workflows,
4. missing reporting readiness,
5. portfolios with unresolved but competing attention signals.

It then turns those into a prioritized review list rather than leaving them buried in separate
systems.

## Why This Is Agentic

This feature is agentic because it is not limited to one prompt over one fixed payload.

It is a bounded goal-seeking workflow that:

1. starts from an objective such as "prepare today’s RM briefing",
2. determines which governed tools are needed,
3. gathers additional evidence only where needed,
4. ranks and groups signals from multiple systems,
5. synthesizes a briefing and recommendation package,
6. records run state, evidence usage, and feedback,
7. can run on schedule or on demand.

It is not agentic because it can execute final business authority.

The correct Lotus boundary is:

1. autonomous evidence gathering,
2. autonomous prioritization,
3. autonomous briefing and recommendation drafting,
4. human-controlled action approval and business execution.

## Goals

1. Deliver one genuinely high-value agentic workflow for the Lotus front-office operating layer.
2. Turn cross-domain signals into one evidence-backed RM briefing artifact.
3. Establish the technical pattern of using governed domain capabilities as agent tools.
4. Keep domain truth, approval truth, and execution authority outside `lotus-ai`.
5. Make the output reviewable, auditable, and workflow-safe.
6. Create a reusable pattern for later cross-domain Lotus agentic workflows.

## Non-Goals

1. Direct trade or booking execution by AI.
2. AI-established approval, suitability, or client-consent truth.
3. Unbounded raw access from `lotus-ai` to arbitrary internal APIs.
4. A generic shell-wide chatbot as the primary feature model.
5. Replacing `lotus-gateway` as the experience-composition layer.
6. Recomputing deterministic analytics or portfolio truth inside `lotus-ai`.

## Decision

`lotus-ai` will add a new `Relationship Manager Briefing Agent` capability for the Lotus ecosystem.

This capability will:

1. use governed domain-driven APIs as typed tools,
2. orchestrate those tools through explicit service logic in `lotus-ai`,
3. synthesize evidence-backed briefings and next-best-action suggestions,
4. expose clear provenance, review-state, and feedback hooks,
5. remain read-only and recommendation-oriented in its initial rollout.

The initial implementation boundary is intentionally strict:

1. domain services remain responsible for business truth,
2. `lotus-gateway` remains responsible for UI-facing contract shaping,
3. `lotus-workbench` remains responsible for AI-bearing review UX,
4. `lotus-ai` remains responsible for orchestration, prompting, retrieval, audit, evals, and async
   runtime,
5. no output from this feature is allowed to masquerade as approved workflow truth.

## Initial Release Boundary

The first release should stay narrow and truthful.

Version 1 should support:

1. one seeded portfolio or client scope,
2. read-only recommendation generation,
3. bounded tool inputs from `lotus-core`, `lotus-performance`, `lotus-risk`, and `lotus-manage`,
4. optional enrichment from `lotus-advise` and `lotus-report` only when the upstream capability is
   already trustworthy and available,
5. explicit provenance, review-state, and feedback capture,
6. no automatic downstream execution.

Version 1 should not attempt:

1. RM-book-wide autonomous action routing,
2. free-form user prompting over arbitrary client scope,
3. hidden fallback to unsupported inferred business facts,
4. automatic write-back into domain systems.

## Proposed Capability Shape

The feature should expose one bounded briefing capability family with explicit scope, evidence, and
action model.

### Initial briefing scopes

The first supported scopes should be:

1. `single_portfolio`
2. `single_client`
3. `book_priority_slice`

These should be explicit enumerations, not free-form prompts.

### Required briefing response shape

The response should be structured and typed rather than a single blob of prose.

The initial response family should include:

1. scope summary,
2. important changes,
3. risks and obligations,
4. opportunities and recommended next actions,
5. open workflow items,
6. evidence references,
7. provenance and review metadata.

### Required upstream tool categories

The briefing should be built from real Lotus domain capabilities such as:

1. portfolio and mandate context,
2. performance and benchmark-relative context,
3. risk and breach context,
4. management workflow context,
5. proposal and advisory opportunity context,
6. reporting readiness context.

## Domain APIs as Governed Agent Tools

This RFC explicitly adopts the pattern that domain capabilities should be made available to the
agent as governed typed tools.

That does not mean exposing arbitrary low-level service internals directly.

The preferred model is:

1. domain services or trusted composition layers expose curated business operations,
2. those operations have typed request and response contracts,
3. `lotus-ai` invokes those operations under audit and policy,
4. prompt logic consumes the resulting bounded evidence rather than inventing business semantics.

### Tool design rules

Every tool must be:

1. business-meaningful,
2. typed,
3. permission-aware,
4. auditable,
5. bounded in scope,
6. owned by one clear repository.

### Examples of tool families

Illustrative tool families include:

1. `get_portfolio_briefing_context`
2. `get_recent_performance_drivers`
3. `get_mandate_and_risk_alerts`
4. `get_pending_management_actions`
5. `get_stale_proposal_opportunities`
6. `get_reporting_readiness_summary`

The correct tool is a business-meaningful operation, not a raw "fetch everything" endpoint.

### Tool ownership model

#### `lotus-core`

Owns tools for:

1. client identity and portfolio context,
2. holdings and allocation posture,
3. mandate and lifecycle context,
4. cash and maturity posture,
5. recent transaction and supportability context when relevant.

#### `lotus-performance`

Owns tools for:

1. return summary,
2. benchmark-relative posture,
3. attribution and contribution highlights,
4. recent performance drivers.

#### `lotus-risk`

Owns tools for:

1. concentration alerts,
2. exposure changes,
3. drawdown and breach summaries,
4. risk posture deltas that matter to the briefing.

#### `lotus-manage`

Owns tools for:

1. open management-side actions,
2. unresolved workflow items,
3. pending operational follow-up,
4. supportability-impacting management state.

#### `lotus-advise`

Owns tools for:

1. proposal readiness,
2. stale proposal state,
3. advisory opportunity indicators,
4. bounded rationale or follow-up context where approved.

#### `lotus-report`

Owns tools for:

1. reporting readiness,
2. latest report-package state,
3. evidence availability or missing evidence indicators.

## Architecture Direction

### 1. Orchestration should be explicit service code

The feature should be implemented in `lotus-ai` through explicit orchestration code over the
existing stack:

1. `FastAPI`,
2. `Pydantic`,
3. `SQLAlchemy`,
4. `Redis`-backed async runtime,
5. existing provider, prompt, retrieval, safety, eval, and audit seams.

This RFC does not require a heavy third-party agent framework.

The business need is:

1. auditability,
2. typed contracts,
3. predictable control flow,
4. bounded retries and failures,
5. transparent evidence usage.

### 2. Briefing assembly should combine deterministic and AI layers

The feature should use:

1. deterministic signal extraction to identify what matters,
2. AI synthesis to explain, prioritize, and phrase what matters,
3. retrieval only where governed contextual guidance or policy support is needed,
4. explicit refusal or degradation when required evidence is incomplete.

This is important because a fully prompt-driven approach would weaken trust.

### 3. Gateway should remain the UI composition owner

`lotus-gateway` should remain responsible for:

1. shaping experience-facing briefing contracts,
2. handling partial-availability and fallback behavior for the UI,
3. exposing provenance, evidence, and review-state posture to `lotus-workbench`,
4. keeping the UI decoupled from raw service-level tool contracts.

### 4. Workbench must treat AI output as assistive, not authoritative

`lotus-workbench` should represent this feature through governed AI module patterns that clearly
distinguish:

1. source-backed workflow truth,
2. AI-generated briefing or recommendation content,
3. human review and action state,
4. accepted versus rejected or stale AI output.

This should inherit the governance direction already identified in platform RFC-0081 slices 9 and
10.

## Operating Model

### Trigger modes

The feature should support:

1. scheduled daily runs,
2. on-demand runs for a client or portfolio scope,
3. later event-driven runs when an explicit governance slice approves that posture.

### Run stages

Each run should follow this sequence:

1. identify the target scope and caller context,
2. gather deterministic signals from bounded tools,
3. rank and group the signals,
4. gather only the additional evidence needed for explanation,
5. produce structured briefing sections and recommendations,
6. apply safety, provenance, and review-state controls,
7. persist run state, evidence lineage, and feedback hooks,
8. publish the result through governed experience contracts.

### Degradation model

The feature must degrade honestly when:

1. one or more tool families are unavailable,
2. stale or contradictory evidence exists,
3. AI generation is unavailable or blocked,
4. required context is incomplete for a safe recommendation.

In those cases the system should prefer:

1. partial source-backed briefing sections,
2. explicit missing-data markers,
3. blocked recommendation areas,
4. stable audit and user feedback capture.

## Data and Operational Requirements

1. Every briefing request must identify bounded scope and caller context.
2. Every tool invocation must be audit-logged.
3. Every generated briefing must carry evidence refs or explicit inference labeling.
4. The capability must support degraded or partial behavior when one or more tool categories are
   unavailable.
5. The capability must preserve review-state and feedback linkage.
6. The capability must remain read-only in its initial rollout.

## Delivery Slices

### Slice 1: Capability and contract definition

Outcome:

1. a named briefing capability pack exists,
2. scope types and response structure are explicit,
3. the domain-tool taxonomy is documented,
4. the action boundary is clearly read-only and assistive.

Acceptance gate:

1. business value and first use cases are concrete,
2. domain ownership boundaries are preserved,
3. typed contracts exist for requests, responses, evidence references, and review-state metadata.

### Slice 2: lotus-ai orchestration foundation

Outcome:

1. `lotus-ai` exposes a briefing capability seam,
2. orchestration can invoke bounded tools,
3. prompt, safety, audit, and async runtime integration exists,
4. structured output is persisted and inspectable.

Acceptance gate:

1. no hidden free-form orchestration path exists,
2. every tool call is attributable,
3. degraded-mode behavior is explicit and testable.

### Slice 3: domain-tool adoption

Outcome:

1. upstream app capabilities needed for the briefing are exposed as governed typed tools,
2. at least one end-to-end seeded scope can produce a truthful briefing,
3. cross-service evidence lineage is explicit.

Acceptance gate:

1. tool ownership by repo is clear,
2. partial or stale upstream data is surfaced honestly,
3. no service hands off domain truth ownership to `lotus-ai`.

### Slice 4: gateway and workbench product surface

Outcome:

1. the briefing appears in a governed UI flow,
2. provenance, review-state, and feedback surfaces exist,
3. next-best-action suggestions are shown with workflow-safe handoff controls.

Acceptance gate:

1. AI output is visually distinct from authoritative workflow truth,
2. UI behavior degrades safely when AI is unavailable,
3. feedback capture ties back to specific outputs and runs.

### Slice 5: quality, rollout, and maturity

Outcome:

1. the feature is covered by pack-specific evals and rollout discipline,
2. broader RM-book or exception-trigger coverage can be added incrementally,
3. the feature becomes a reusable cross-domain capability family.

Acceptance gate:

1. quality is measured on grounding, prioritization, and usefulness rather than fluency alone,
2. rollout remains bounded and inspectable,
3. the feature is materially more useful than a static summary or chat wrapper.

### Slice 6: Documentation, Agent Context, and Branch Hygiene

Outcome:

1. documentation, context, and skill implications are reviewed explicitly rather than implicitly,
2. repo and platform guidance is updated where implementation reality changed,
3. branch, PR, and evidence hygiene are closed as part of the feature program rather than left to
   cleanup afterward.

Required review areas:

1. `lotus-ai/REPOSITORY-ENGINEERING-CONTEXT.md`
2. `lotus-ai/docs/architecture/system-overview.md`
3. `lotus-ai/docs/architecture/feature-status-and-roadmap.md`
4. relevant `lotus-platform/context/*` documents if the new operating pattern becomes platform
   truth,
5. relevant Lotus skills if the workflow creates a durable new delivery pattern.

Specific skill and guidance assessment required in this slice:

1. assess whether `lotus-backend-delivery-governance` should explicitly mention typed tool
   orchestration for cross-domain AI features,
2. assess whether `lotus-rfc-review-loop` should include a stronger requirement to add an explicit
   documentation/context/skill final slice for implementation-grade RFCs,
3. assess whether `lotus-ai` repo context should name governed domain-tool orchestration as a
   first-class integration pattern once implementation begins,
4. assess whether platform context should describe when "domain APIs as tools" is the preferred AI
   integration model for cross-domain workflows.

Current assessment for this RFC draft:

1. no repo or platform context document needs immediate change before implementation begins,
2. the existing skills remain usable for this work,
3. the implementation slices should revisit those documents and skills once real contracts, runtime
   seams, and workflow surfaces exist,
4. if that later review finds no truthful changes, that should still be recorded as a conscious
   decision in the final evidence slice.

Acceptance gate:

1. documentation and context review is completed explicitly,
2. any durable guidance changes are committed in the same slice as the implementation reality they
   describe,
3. branch and PR hygiene are completed with truthful evidence,
4. if no skill or context change is required, that conclusion is stated explicitly with rationale.

## Risks

1. If tools expose raw low-level APIs rather than curated operations, orchestration will become
   noisy and brittle.
2. If the feature overstates confidence without evidence, banker trust will degrade quickly.
3. If AI output becomes visually or operationally mixed with workflow truth, control risk will be
   too high.
4. If the first slice tries to automate downstream actions, governance will become unnecessarily
   risky.
5. If the scope is too broad too early, the feature will become generic instead of business-useful.

## Alternatives Considered

### 1. Generic chat assistant over Lotus data

Rejected.

Reason:

1. weaker business specificity,
2. harder to validate,
3. easier to misuse as pseudo-authoritative workflow guidance,
4. lower measurable value than a briefing workflow tied to explicit next actions.

### 2. One monolithic agent inside `lotus-ai` with broad raw service access

Rejected.

Reason:

1. domain boundaries become blurry,
2. prompt logic starts substituting for product contracts,
3. audit and entitlement posture become harder to reason about,
4. failures become harder to isolate and harden.

### 3. Separate AI summarizers built independently in each domain app

Rejected.

Reason:

1. duplicated prompt and audit logic,
2. inconsistent review-state and provenance posture,
3. no cross-domain action-oriented briefing experience,
4. weaker reuse of the shared `lotus-ai` platform.

## Success Criteria

This RFC is successful when:

1. Lotus has one clearly differentiated agentic feature for front-office preparation,
2. the feature saves real user effort by assembling a high-value briefing from multiple domain
   systems,
3. domain APIs are successfully exposed as governed agent tools without blurring ownership,
4. `lotus-ai` demonstrates bounded multi-step orchestration over typed evidence rather than generic
   chat behavior,
5. the platform can present the output safely through governed provenance, review-state, and
   feedback patterns.
