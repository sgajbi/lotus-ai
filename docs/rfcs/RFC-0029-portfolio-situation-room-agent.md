# RFC-0029: Portfolio Situation Room Agent

- Status: Draft
- Date: 2026-04-13
- Owners: lotus-ai, lotus-gateway, lotus-workbench
- Requires Approval From: lotus-ai maintainers, lotus-gateway maintainers, lotus-workbench maintainers, lotus-core maintainers, lotus-performance maintainers, lotus-risk maintainers, lotus-manage maintainers, lotus-advise maintainers, lotus-report maintainers

## Summary

`lotus-ai` already has the platform primitives needed for bounded AI execution:

1. governed prompts,
2. governed retrieval,
3. runtime safety controls,
4. durable async execution,
5. evaluation and approval-gate evidence,
6. app-capability rollout governance.

What it does not yet have is a serious multi-step, multi-domain operating workflow that treats a
material portfolio event as a managed case rather than as a static dashboard state or one-shot AI
output.

This RFC defines that next step:

1. a `Portfolio Situation Room Agent`,
2. designed to open, maintain, and resolve a governed case around a material portfolio situation,
3. grounded in authoritative evidence from Lotus domain services,
4. implemented as bounded specialist-agent orchestration with a coordinator layer,
5. explicitly reviewable, auditable, and subordinate to human workflow authority.

This is not a chat assistant.

It is a persistent case workflow for:

1. understanding what happened,
2. understanding why it matters,
3. coordinating the right evidence and specialist views,
4. recommending the next safe action plan,
5. tracking the case until resolution.

## Why This RFC Exists

In real portfolio-management and client-servicing work, the highest-friction moments are not steady
states.

They are situations:

1. a drawdown appears and it is unclear whether it is noise or a client-facing concern,
2. a concentration threshold is crossed while a proposal is stale,
3. a reporting pack is not ready for a client conversation after a material performance move,
4. an unresolved management-side action blocks a relationship review,
5. several cross-domain signals appear at once and no single product surface explains the whole
   picture.

Lotus already has much of the underlying truth:

1. `lotus-core` owns portfolio, holdings, mandate, cash, and lifecycle state,
2. `lotus-performance` owns returns, attribution, and benchmark-relative context,
3. `lotus-risk` owns breaches, concentration, exposure, and drawdown posture,
4. `lotus-manage` owns management-side workflow state,
5. `lotus-advise` owns proposal and follow-up opportunity state,
6. `lotus-report` owns report and evidence readiness,
7. `lotus-gateway` and `lotus-workbench` own the operating product surface.

But the platform does not yet give users a governed way to say:

1. "this portfolio is in an important situation,"
2. "assemble the right evidence now,"
3. "show me the specialist perspectives,"
4. "help me drive this to resolution safely."

Without this RFC:

1. users continue to synthesize material situations manually,
2. AI remains a static explanation utility rather than a managed operating capability,
3. the platform misses an opportunity to turn domain truth into a persistent high-value workflow,
4. meaningful cross-domain situations remain operationally fragmented.

## Relationship to Existing RFCs

This RFC should build on existing `lotus-ai` and platform governance rather than inventing a new
AI model from scratch.

Most importantly:

1. RFC-0021 in `lotus-ai` established domain capability-pack direction,
2. RFC-0023 established downstream app-capability rollout governance,
3. RFC-0028 established the first cross-domain agentic front-office pattern through the
   Relationship Manager Briefing Agent,
4. platform RFC-0069 established that `lotus-ai` is a shared AI capability service and not the
   owner of domain business truth,
5. platform RFC-0081 slices 9 and 10 established the required UX posture for AI-bearing product
   surfaces, including provenance, review-state, and assistive-action controls.

This RFC should therefore:

1. extend the cross-domain orchestration direction beyond a one-shot briefing,
2. keep the domain-tool model from RFC-0028,
3. add persistent case state, specialist-agent outputs, and case-lifecycle discipline,
4. avoid autonomous execution or hidden workflow mutation.

## Problem Statement

Current Lotus users can inspect important signals, but they do not yet have a governed operating
model for handling a material portfolio situation end to end.

Current pain includes:

1. no persistent case object for a portfolio situation,
2. no shared cross-domain evidence view with clear specialist perspectives,
3. no governed way to keep a material situation open until resolved,
4. no structured distinction between detected event, investigated hypothesis, recommended action,
   and closed outcome,
5. no bounded agent coordination layer that can continue helping as the situation evolves.

Current AI limitation:

1. `lotus-ai` can already summarize or explain bounded evidence,
2. but it does not yet manage a stateful situation lifecycle,
3. it does not yet coordinate multiple specialist perspectives under one explicit case model,
4. it does not yet provide the "ongoing case until closure" behavior that makes a workflow
   genuinely more agentic than a static summary.

## Business Context and Value

The business value of a Situation Room is not novelty.

It is controlled acceleration during moments that matter most:

1. when a relationship could become exposed or under-serviced,
2. when cross-domain ambiguity could delay action,
3. when internal teams need one truth-shaped operating picture,
4. when the cost of missing an important combination of signals is higher than the cost of routine
   monitoring.

Expected value areas:

1. faster and more consistent response to material portfolio events,
2. reduced manual synthesis across products and workflows,
3. better escalation quality because evidence is grouped and ranked coherently,
4. clearer handoff between RM, PM, advisory, reporting, and management workflows,
5. stronger auditability of how an important situation was understood and resolved.

This is especially valuable in a banking-grade environment because the platform should not only
present information. It should help the firm maintain control and supportability when the operating
state becomes non-trivial.

## Core Product Concept

The `Portfolio Situation Room Agent` turns a material portfolio event into a governed case.

That case persists until:

1. the situation is understood sufficiently,
2. the recommended path is reviewed,
3. the required downstream actions are accepted, deferred, or rejected with rationale,
4. the situation is either resolved or intentionally parked with visible justification.

This moves the operating model from:

1. static dashboard inspection,
2. isolated workflow views,
3. one-shot AI summaries,

to:

1. case-oriented investigation,
2. cross-domain evidence coordination,
3. lifecycle tracking through resolution.

## Primary Use Cases

### 1. Multi-factor portfolio attention event

A portfolio experiences:

1. negative benchmark-relative movement,
2. a concentration shift,
3. an overdue review,
4. a stale proposal,
5. incomplete reporting readiness.

The Situation Room opens a case and assembles those signals into one ranked operating picture.

### 2. Risk and servicing conflict

A portfolio is still within some operating thresholds but is moving in a way that makes a near-term
client review likely necessary.

The Situation Room should identify:

1. the current risk posture,
2. the performance context,
3. the client-servicing implication,
4. the recommended next checks and actions.

### 3. Event-driven investigation before client engagement

An RM or PM sees a material move and wants a governed investigation view rather than multiple
modules.

The Situation Room should:

1. gather the relevant domain evidence,
2. present specialist perspectives,
3. distinguish confirmed facts from plausible explanations,
4. propose the next operating path.

### 4. Prolonged unresolved case

A portfolio situation is not resolved in one session.

The Situation Room should preserve:

1. prior evidence,
2. prior recommendations,
3. prior human decisions,
4. unresolved questions,
5. current case status and why it is still open.

## Why This Is Agentic

This feature is genuinely agentic because it is not merely prompt-driven output over one payload.

It is a bounded, stateful, goal-seeking case workflow that:

1. detects or accepts a situation trigger,
2. decides which specialist evidence paths to run,
3. gathers evidence iteratively,
4. maintains a persistent case record,
5. reconciles multiple specialist outputs,
6. proposes next actions,
7. updates the case as new evidence arrives,
8. remains active until closure criteria are met.

This is more agentic than a briefing because the unit of work is not "produce a summary."

The unit of work is:

1. open a case,
2. understand the case,
3. coordinate the case,
4. help close the case safely.

## Goals

1. Deliver a persistent, case-based cross-domain operating workflow for material portfolio
   situations.
2. Coordinate multiple bounded specialist perspectives under one governed case model.
3. Keep domain truth, workflow truth, approval truth, and execution authority outside `lotus-ai`.
4. Make investigation, recommendation, and closure explicit and auditable.
5. Create a reusable operating pattern for later case-style workflows across Lotus.

## Non-Goals

1. Direct autonomous execution of portfolio or workflow changes.
2. Hidden mutation of domain systems by specialist agents.
3. Replacing deterministic product surfaces with a free-form AI workspace.
4. Letting AI-generated hypotheses appear as authoritative workflow truth.
5. Building a general multi-agent sandbox without business-specific control boundaries.

## Decision

`lotus-ai` will add a `Portfolio Situation Room Agent` capability family for the Lotus ecosystem.

This capability will:

1. create and maintain a persistent case model,
2. orchestrate bounded specialist-agent contributions,
3. synthesize one coordinator output over those specialist views,
4. surface evidence, unresolved questions, recommended actions, and closure state,
5. remain read-only and assistive in its initial rollout.

The initial boundary is intentionally strict:

1. domain services remain the source of portfolio, analytics, risk, workflow, proposal, and report
   truth,
2. `lotus-gateway` remains the experience-composition owner,
3. `lotus-workbench` remains the review and case-workspace owner,
4. `lotus-ai` remains the bounded orchestration and reasoning layer,
5. humans remain responsible for action approval and final business decisions.

## Banking-Grade Control Rules

The Situation Room must obey the following non-negotiable rules:

1. no specialist or coordinator output may be treated as approval, consent, suitability, or
   execution truth,
2. every materially important claim must link to named evidence or be labeled as an inference,
3. every unresolved contradiction must remain visible until explicitly resolved or deferred,
4. a case may not be auto-closed by AI alone,
5. downstream action routing must remain explicit and reviewable,
6. partial or blocked specialist state must not be hidden behind a complete-looking coordinator
   summary.

## Specialist-Agent Model

The system should use named specialist roles with bounded responsibilities.

Illustrative specialist agents:

1. `portfolio_state_agent`
2. `performance_interpretation_agent`
3. `risk_posture_agent`
4. `workflow_readiness_agent`
5. `advisory_opportunity_agent`
6. `evidence_readiness_agent`
7. `coordinator_agent`

### Specialist rules

Each specialist must:

1. consume bounded typed evidence,
2. stay within one business concern,
3. produce explicit evidence-linked output,
4. distinguish facts from inferences,
5. avoid claiming authority outside its scope.

### Coordinator rules

The coordinator must:

1. reconcile specialist outputs,
2. identify contradictions or missing evidence,
3. rank the case severity and attention level,
4. produce the recommended next action path,
5. avoid flattening uncertainty into false confidence.

## Architecture Direction

### 1. Persistent case state is mandatory

This feature should introduce an explicit case model rather than treating each run as a transient
task execution.

At minimum, a case should carry:

1. case identity,
2. scope identity,
3. trigger reason,
4. current status,
5. specialist outputs,
6. evidence refs,
7. unresolved questions,
8. recommendation history,
9. human decision and status history.

### 2. Orchestration should remain explicit service code

The feature should use the existing `lotus-ai` technical foundation:

1. `FastAPI`,
2. `Pydantic`,
3. `SQLAlchemy`,
4. `Redis`-backed async runtime,
5. provider, prompt, retrieval, safety, eval, and audit seams already in the repo.

It should not rely on a heavyweight agent framework as the primary control layer.

### 3. Tool use remains domain-driven and typed

The specialist agents should continue the domain-tool pattern introduced in RFC-0028:

1. business-meaningful tools,
2. typed contracts,
3. bounded permissions,
4. clear owning repository,
5. audit-logged invocations.

### 4. Gateway and Workbench remain first-class owners

`lotus-gateway` should own:

1. case-view composition contracts,
2. partial-failure shaping,
3. provenance and case-state exposure to the UI.

`lotus-workbench` should own:

1. the Situation Room workspace,
2. specialist-view presentation,
3. case timeline and review controls,
4. human action acceptance, rejection, defer, and closure affordances,
5. explicit distinction between facts, AI interpretation, and workflow state.

## Operating Model

### Trigger modes

The Situation Room should support:

1. event-triggered case creation,
2. user-invoked case creation,
3. later scheduled watchlist creation once an explicit rollout slice approves that posture.

### Initial case taxonomy

The first implementation should support a deliberately small set of case types:

1. `performance_risk_attention`
2. `review_readiness_attention`
3. `multi_factor_attention`

New case types should be added only when:

1. the trigger logic is explicit,
2. the required tool set is explicit,
3. closure criteria are explicit,
4. the eval coverage for that case type exists.

### Run stages

Each case should progress through:

1. trigger registration,
2. initial evidence sweep,
3. specialist-agent analysis,
4. coordinator synthesis,
5. human review and action decisions,
6. re-check or refresh if the case remains open,
7. explicit closure or governed deferral.

### Degradation model

The Situation Room must degrade honestly when:

1. a specialist tool family is unavailable,
2. evidence is stale or contradictory,
3. one specialist cannot reach a safe conclusion,
4. AI generation is blocked or unavailable.

In those cases the system should:

1. keep the case open if needed,
2. mark the affected specialist output as partial or blocked,
3. expose unresolved questions clearly,
4. avoid producing false closure confidence.

## Initial Release Boundary

The first release should stay narrow and truthful.

Version 1 should support:

1. one seeded portfolio scope,
2. one case type with a bounded trigger family,
3. specialist views from `lotus-core`, `lotus-performance`, `lotus-risk`, and `lotus-manage`,
4. read-only recommendations and case progression,
5. explicit provenance, review-state, and case timeline support,
6. no automatic write-back into domain workflows.

Version 1 should not attempt:

1. multi-case portfolio-book management,
2. unrestricted free-form prompting,
3. autonomous case closure without human review,
4. automatic downstream execution.

## Data and Operational Requirements

1. every case must identify trigger source and scope,
2. every specialist invocation must be audit-logged,
3. every specialist output must link to named evidence,
4. every coordinator output must separate facts, inferences, and recommendations,
5. every case status change must be persisted and inspectable,
6. the feature must remain read-only in the initial rollout.

## Delivery Slices

### Slice 1: Case model and capability definition

Outcome:

1. a named Situation Room capability exists,
2. case status, trigger, evidence, and recommendation models are explicit,
3. specialist roles are documented and bounded.

Acceptance gate:

1. case lifecycle is explicit,
2. role boundaries are clear,
3. typed case contracts exist,
4. case open, defer, and close semantics are explicitly modeled.

### Slice 2: Specialist-agent orchestration foundation

Outcome:

1. `lotus-ai` can create, persist, and refresh a case,
2. bounded specialist-agent runs exist,
3. coordinator synthesis exists,
4. audit and async runtime integration exist.

Acceptance gate:

1. specialist and coordinator paths are inspectable,
2. failure and partial-status handling are explicit,
3. case persistence is truthful and durable,
4. the coordinator cannot suppress blocked or contradictory specialist findings.

### Slice 3: Domain-tool adoption

Outcome:

1. upstream bounded tools needed by the specialist agents are available,
2. at least one seeded case type can execute end to end,
3. cross-domain evidence lineage is explicit.

Acceptance gate:

1. upstream ownership is clear,
2. no business truth migrates into `lotus-ai`,
3. partial data is surfaced honestly,
4. at least one seeded case can trace every major recommendation back to named evidence.

### Slice 4: Gateway and Workbench Situation Room surface

Outcome:

1. the case is visible in a governed workspace,
2. specialist outputs and coordinator output are reviewable,
3. case timeline and human decision controls exist.

Acceptance gate:

1. AI output is distinct from workflow truth,
2. degraded specialist states are visible,
3. human action status is explicit,
4. case timeline and closure rationale are visible in the UI contract.

### Slice 5: Quality, rollout, and maturity

Outcome:

1. pack-specific evals and rollout gates exist,
2. broader case types can be added incrementally,
3. the Situation Room becomes a reusable case-management capability family.

Acceptance gate:

1. quality is measured on evidence usage, prioritization, and closure usefulness,
2. rollout remains bounded and inspectable,
3. the feature is materially stronger than a static summary workflow,
4. at least one case type has explicit evals for contradiction handling and insufficient-evidence
   handling.

### Slice 6: Documentation, Agent Context, and Branch Hygiene

Outcome:

1. documentation and context impact is reviewed explicitly,
2. any durable guidance changes are committed alongside implementation truth,
3. branch and PR hygiene are treated as part of the program, not cleanup.

Required review areas:

1. `lotus-ai/REPOSITORY-ENGINEERING-CONTEXT.md`
2. `lotus-ai/docs/architecture/system-overview.md`
3. `lotus-ai/docs/architecture/feature-status-and-roadmap.md`
4. relevant `lotus-platform/context/*` documents if the case-based agent workflow becomes platform
   truth,
5. relevant Lotus skills if specialist-agent delivery becomes a durable work pattern.

Current assessment for this RFC draft:

1. no immediate context or skill change is required before implementation begins,
2. implementation should revisit whether Lotus guidance needs stronger support for persistent
   case-based agent workflows,
3. if no durable guidance change is needed later, that should still be recorded explicitly in the
   final slice.

Acceptance gate:

1. documentation and context review is completed explicitly,
2. any durable guidance updates are committed truthfully,
3. branch hygiene is closed with real evidence,
4. a deliberate "no change required" outcome is allowed but must be stated explicitly with
   rationale.

## Risks

1. If the case model is weak, the feature will degrade into another summary tool.
2. If specialist boundaries are unclear, the system will become hard to audit and hard to trust.
3. If the coordinator overstates confidence, unresolved ambiguity will be hidden rather than
   managed.
4. If v1 tries to solve every situation type, the feature will lose operational clarity.

## Alternatives Considered

### 1. A one-shot situation summary only

Rejected.

Reason:

1. it does not preserve case continuity,
2. it cannot track unresolved questions and closure,
3. it does not materially change the operating model.

### 2. A generic multi-agent sandbox

Rejected.

Reason:

1. weak business boundaries,
2. high governance risk,
3. poor auditability relative to a named case workflow.

### 3. Embedding this workflow entirely in one domain app

Rejected.

Reason:

1. situations are inherently cross-domain,
2. the workflow would fragment by product surface,
3. the shared `lotus-ai` platform would be underused.

## Success Criteria

This RFC is successful when:

1. Lotus has a persistent, case-based operating workflow for material portfolio situations,
2. the feature can coordinate specialist cross-domain views under one governed case,
3. the platform can keep a situation open until meaningfully resolved or deliberately deferred,
4. the feature remains audit-safe, evidence-backed, and subordinate to human workflow authority,
5. the first release proves a materially better operating path than static dashboards plus one-shot
   AI summaries.
