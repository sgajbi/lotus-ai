# RFC-0030: Client Mandate Integrity and Action Orchestration

- Status: Draft
- Date: 2026-04-13
- Owners: lotus-ai, lotus-gateway, lotus-workbench
- Requires Approval From: lotus-ai maintainers, lotus-gateway maintainers, lotus-workbench maintainers, lotus-core maintainers, lotus-performance maintainers, lotus-risk maintainers, lotus-manage maintainers, lotus-advise maintainers, lotus-report maintainers

## Summary

The strongest banking-grade AI feature in the Lotus ecosystem should not merely help users read
portfolio information faster.

It should help the firm maintain relationship integrity as portfolio reality, mandate posture, risk
state, workflow readiness, and client-servicing obligations evolve.

This RFC defines that feature:

1. `Client Mandate Integrity and Action Orchestration`,
2. a governed cross-domain operating system for detecting relationship drift,
3. a case-and-action workflow that explains the drift, proposes a remediation path, and tracks it
   to closure,
4. built on authoritative domain truth and bounded AI orchestration rather than hidden AI
   decision-making.

This is not a generalized copilot.

It is a banking-grade control and servicing workflow for keeping every client relationship in a:

1. governed,
2. explainable,
3. supportable,
4. action-ready state.

## Why This RFC Exists

In a private-banking and discretionary-portfolio environment, the highest-value AI feature is not
the most conversational one.

It is the feature that helps the firm maintain alignment between:

1. client mandate and current holdings,
2. risk posture and acceptable operating state,
3. portfolio performance and the need for client engagement,
4. review obligations and actual workflow readiness,
5. advisory opportunities and current market or portfolio conditions,
6. reporting obligations and evidence readiness.

Those forms of drift are where material business risk and servicing failure appear:

1. portfolios move,
2. benchmarks diverge,
3. concentration changes,
4. reviews become overdue,
5. proposals become stale,
6. action pipelines remain unresolved,
7. evidence packages lag behind the relationship reality.

Today, those issues can be observed across Lotus, but they are not yet governed as one persistent
relationship-integrity workflow.

Without this RFC:

1. client relationships can become fragmented across data, workflow, and evidence systems,
2. important servicing or control drift can remain visible only to diligent humans stitching
   together multiple modules,
3. AI remains explain-only rather than integrity-preserving,
4. the platform misses the strongest banking-grade use case for agentic orchestration.

## Relationship to Existing RFCs

This RFC is the most control-oriented extension of the path defined by earlier `lotus-ai` and
platform RFCs.

It builds directly on:

1. RFC-0021 capability-pack direction,
2. RFC-0023 app-capability rollout governance,
3. RFC-0028 relationship-manager briefing orchestration,
4. RFC-0029 portfolio case orchestration,
5. platform RFC-0069 shared AI service boundaries,
6. platform RFC-0072 multi-lane validation governance,
7. platform RFC-0081 AI provenance, review-state, and safe-action UX posture.

This RFC is intentionally more ambitious than RFC-0028 and RFC-0029 because it moves from:

1. explaining a relationship state,
2. and managing a portfolio situation,

to:

1. preserving the integrity of the full client relationship over time,
2. including mandate, risk, servicing, workflow, proposal, and evidence readiness drift.

## Problem Statement

The bank does not only need to know what a portfolio looks like.

It needs to know whether the full client relationship remains in a safe, governed, and
service-ready state.

That integrity can degrade when:

1. portfolio allocations move away from mandate expectations,
2. risk posture worsens without appropriate servicing action,
3. performance changes materially while client engagement remains stale,
4. a proposal remains outdated even though relationship conditions changed,
5. management or operational workflows remain unresolved,
6. reporting or evidence readiness falls behind the current state.

Today, those conditions are distributed across multiple systems and operating flows.

Current limitations:

1. there is no unified integrity model,
2. there is no persistent cross-domain action case tied to relationship drift,
3. there is no governed AI layer that can detect, explain, and coordinate the remediation path,
4. there is no consistent closure model for "relationship back in a governed state."

## Business Context and Value

This is the most banking-grade AI feature in the current Lotus opportunity set because it addresses
not just productivity, but control quality.

Expected value areas:

1. earlier detection of mandate, risk, workflow, and evidence drift,
2. stronger consistency of client-servicing follow-up,
3. reduced risk of stale or misaligned relationship actions,
4. improved auditability of how important relationship drift was identified and resolved,
5. better alignment between front-office readiness and back-office supportability.

This has executive-grade value because it improves:

1. relationship coverage,
2. control integrity,
3. action timeliness,
4. explainability,
5. operating discipline.

It is the kind of feature that justifies a shared AI platform in a bank-grade architecture because
it is directly tied to:

1. fiduciary discipline,
2. front-office trust,
3. internal control quality,
4. evidence-backed remediation.

## Core Product Concept

The system continuously evaluates whether a client relationship remains in an acceptable governed
state across:

1. portfolio posture,
2. mandate alignment,
3. risk alignment,
4. review and servicing readiness,
5. proposal freshness,
6. management workflow readiness,
7. reporting and evidence readiness.

When material drift is detected, it opens an `Integrity Action Case`.

That case:

1. classifies the form of drift,
2. gathers domain evidence,
3. proposes a remediation path,
4. routes accepted actions into the right workflows,
5. stays open until the relationship is restored to an acceptable state or deliberately deferred.

## Primary Use Cases

### 1. Mandate drift

The current portfolio posture is moving away from mandate expectations or expected suitability
bands.

The system should:

1. detect the drift,
2. explain the supporting evidence,
3. identify whether PM, RM, or advisory review is needed,
4. open a remediation case.

### 2. Risk escalation without servicing alignment

Risk posture deteriorates or concentration changes materially, but servicing or client-review action
has not caught up.

The system should:

1. identify the risk change,
2. inspect review and workflow readiness,
3. propose the right relationship action path,
4. track the case until it is resolved.

### 3. Proposal stale after market or portfolio change

The relationship has a stale proposal even though recent portfolio or market conditions materially
changed.

The system should:

1. flag the stale proposal posture,
2. explain why the proposal is no longer aligned,
3. propose refresh or review actions,
4. link those actions into governed downstream workflows.

### 4. Evidence readiness gap

The relationship needs a review or client interaction, but the reporting and evidence layer is not
ready.

The system should:

1. detect the gap,
2. classify it as supportability or evidence drift,
3. route the appropriate remediation path,
4. keep the case open until the evidence posture is acceptable.

### 5. Multi-factor relationship attention case

More than one form of drift occurs at once.

The system should:

1. open a single integrity case,
2. group the drift types coherently,
3. rank what matters first,
4. produce one action plan across servicing, advisory, operational, and evidence tracks.

## Why This Is Agentic

This feature is genuinely agentic because it manages a controlled lifecycle rather than producing a
single answer.

It:

1. monitors for relationship drift,
2. opens persistent action cases,
3. gathers and re-gathers evidence as the case evolves,
4. coordinates specialist assessments,
5. proposes remediation steps,
6. tracks accepted, deferred, and unresolved actions,
7. closes only when integrity is restored or explicitly deferred.

The unit of work is not "generate commentary."

The unit of work is:

1. detect drift,
2. explain drift,
3. coordinate remediation,
4. verify restoration of integrity.

That is a substantially stronger agentic posture than a static briefing or even a situation room.

## Goals

1. Deliver a banking-grade relationship-integrity workflow for Lotus.
2. Detect and classify material cross-domain relationship drift.
3. Coordinate evidence-backed remediation through governed action cases.
4. Keep portfolio, risk, advisory, workflow, and reporting truth in the authoritative systems.
5. Make drift resolution explicit, auditable, and lifecycle-driven.
6. Establish a durable platform pattern for AI-assisted integrity preservation rather than
   AI-assisted narration only.

## Non-Goals

1. Autonomous trade or approval execution.
2. AI-established suitability or consent truth.
3. Replacing domain workflow systems with a central AI control plane.
4. Treating soft AI judgment as a substitute for governed business rules.
5. Hiding unresolved integrity issues behind polished narrative output.

## Decision

`lotus-ai` will add a `Client Mandate Integrity and Action Orchestration` capability family for the
Lotus ecosystem.

This capability will:

1. continuously or eventfully assess relationship integrity posture,
2. open bounded integrity action cases when material drift is detected,
3. use governed domain tools and specialist reasoning to explain the drift,
4. recommend remediation steps and downstream workflow routes,
5. remain read-only and human-controlled in its initial rollout.

The initial implementation boundary is intentionally strict:

1. domain services remain responsible for business truth,
2. `lotus-gateway` remains responsible for experience-facing contract shaping,
3. `lotus-workbench` remains responsible for the operating workspace and human controls,
4. `lotus-ai` remains responsible for orchestration, evidence synthesis, audit, and evaluation,
5. no AI-generated output may act as final approval, suitability, or execution truth.

## Banking-Grade Control Rules

This feature must obey the following non-negotiable rules:

1. the integrity model must be typed and reviewable, not only implied through prompt text,
2. every integrity-dimension finding must link to named evidence or be labeled as inference,
3. AI may recommend remediation but may not establish approval, suitability, consent, or execution
   readiness,
4. an integrity case may not close without explicit closure evidence and human-confirmed or
   policy-confirmed closure conditions,
5. unresolved integrity drift must remain visible and may not be flattened into optimistic
   narrative,
6. every proposed downstream action must identify an owning workflow or owning team.

## Integrity Model

The feature should introduce an explicit relationship-integrity model.

Illustrative integrity dimensions:

1. `mandate_alignment`
2. `risk_alignment`
3. `servicing_readiness`
4. `proposal_alignment`
5. `workflow_readiness`
6. `evidence_readiness`

Version 1 should use a smaller approved subset rather than all dimensions at once.

Each integrity dimension should support:

1. current status,
2. severity,
3. evidence refs,
4. unresolved questions,
5. recommended remediation path.

## Integrity Action Case Model

When one or more dimensions move outside governed thresholds, the system should create an
`Integrity Action Case`.

At minimum, the case should carry:

1. case identity,
2. relationship scope,
3. integrity dimensions in drift,
4. severity and priority,
5. supporting evidence,
6. proposed actions,
7. human decision state,
8. closure criteria and closure evidence.

## Architecture Direction

### 1. Relationship integrity must be modeled explicitly

This feature should not rely only on prompt prose.

It needs a typed integrity model and action-case model so the system can:

1. reason consistently,
2. persist decisions,
3. support audit and review,
4. drive closure logic truthfully.

### 2. Specialist assessment remains bounded and domain-shaped

Illustrative specialist roles:

1. `mandate_integrity_agent`
2. `risk_integrity_agent`
3. `servicing_readiness_agent`
4. `proposal_alignment_agent`
5. `workflow_readiness_agent`
6. `evidence_readiness_agent`
7. `action_coordinator_agent`

Each role must:

1. consume typed evidence,
2. stay within one integrity dimension,
3. link claims to evidence,
4. separate facts from inferences,
5. avoid implying final authority.

### 3. Explicit service-code orchestration remains preferred

The feature should use the existing `lotus-ai` foundation:

1. `FastAPI`,
2. `Pydantic`,
3. `SQLAlchemy`,
4. `Redis`-backed async runtime,
5. prompt, retrieval, safety, eval, and audit seams already in the repo.

It should not depend on a heavyweight external agent framework as the governing control model.

### 4. Domain APIs remain governed typed tools

The system should continue the domain-tool model:

1. business-meaningful operations,
2. typed contracts,
3. clear repository ownership,
4. audit-logged invocation,
5. permission-aware access.

### 5. Gateway and Workbench remain essential product owners

`lotus-gateway` should own:

1. integrity-case composition contracts,
2. degradation and partial-state handling,
3. experience-ready case, evidence, and recommendation shaping.

`lotus-workbench` should own:

1. the integrity-case operating workspace,
2. dimension-level review presentation,
3. action acceptance, defer, and reject controls,
4. explicit status and closure treatment,
5. AI provenance and review-state affordances.

## Operating Model

### Trigger modes

The feature should support:

1. event-driven detection,
2. scheduled integrity scans,
3. user-invoked integrity assessment for a relationship scope.

### Initial integrity-case taxonomy

The first implementation should support a deliberately narrow set of case types:

1. `mandate_alignment_attention`
2. `servicing_readiness_attention`
3. `proposal_alignment_attention`
4. `multi_factor_integrity_attention`

Each case type must define:

1. opening thresholds,
2. required evidence families,
3. specialist roles,
4. closure criteria,
5. allowed remediation categories.

### Run stages

Each integrity case should progress through:

1. drift detection,
2. integrity-dimension classification,
3. evidence gathering,
4. specialist assessment,
5. coordinator action-plan synthesis,
6. human review and workflow handoff,
7. re-check until closure criteria are satisfied.

### Closure model

A case should close only when:

1. integrity is restored,
2. an acceptable remediation path is confirmed and in force,
3. the case is explicitly deferred with rationale and review timing,
4. the supporting evidence for closure is preserved.

### Degradation model

The feature must degrade honestly when:

1. evidence is incomplete,
2. one integrity dimension is blocked,
3. AI generation is unavailable,
4. a safe remediation plan cannot yet be formed.

In those cases the system should:

1. keep the case open if needed,
2. mark affected dimensions explicitly,
3. expose unresolved gaps clearly,
4. avoid false closure or false confidence.

## Initial Release Boundary

The first release should stay narrow and control-worthy.

Version 1 should support:

1. one seeded relationship scope,
2. one or two integrity dimensions such as mandate alignment and servicing readiness,
3. read-only action-case generation,
4. bounded inputs from `lotus-core`, `lotus-risk`, `lotus-manage`, and optionally
   `lotus-advise`,
5. explicit provenance, review-state, action status, and closure criteria,
6. no automatic write-back or autonomous execution.

Version 1 should not attempt:

1. full enterprise-wide integrity scanning,
2. all integrity dimensions at once,
3. automatic closure without human confirmation,
4. direct trade, approval, or mandate mutation.

## Data and Operational Requirements

1. every integrity assessment must identify relationship scope and triggering condition,
2. every integrity-dimension finding must link to named evidence,
3. every proposed action must identify the intended downstream owner,
4. every case state change must be persisted and audit-visible,
5. the system must distinguish facts, inferences, recommendations, and final human decisions,
6. the capability must remain read-only in its initial rollout.

## Delivery Slices

### Slice 1: Integrity model and action-case definition

Outcome:

1. integrity dimensions are modeled explicitly,
2. action-case contracts exist,
3. closure and defer semantics are explicit.

Acceptance gate:

1. the integrity model is typed and reviewable,
2. closure criteria are concrete,
3. the initial dimension set is bounded and justified,
4. the opening and closure rules for each initial case type are explicit.

### Slice 2: Orchestration and persistent case foundation

Outcome:

1. `lotus-ai` can create and refresh integrity cases,
2. specialist dimension assessments exist,
3. coordinator action-plan synthesis exists,
4. audit and async runtime integration exist.

Acceptance gate:

1. the system can persist and refresh case state truthfully,
2. dimension-level outputs are inspectable,
3. degraded assessment paths are explicit,
4. the system can preserve unresolved drift without forcing a false closure path.

### Slice 3: Domain-tool adoption and case evidence

Outcome:

1. required domain tools exist for the initial integrity dimensions,
2. one seeded case type can run end to end,
3. evidence lineage is explicit across the participating systems.

Acceptance gate:

1. ownership boundaries remain clear,
2. upstream truth does not migrate into `lotus-ai`,
3. unsupported inputs are surfaced honestly,
4. at least one seeded integrity case can trace each major remediation recommendation to named
   evidence.

### Slice 4: Gateway and Workbench integrity workspace

Outcome:

1. the action case is exposed through a governed operating workspace,
2. dimension-level review and action controls exist,
3. human acceptance, defer, reject, and close controls exist.

Acceptance gate:

1. AI output is clearly distinct from workflow truth,
2. closure state is explicit and evidence-backed,
3. partial or blocked dimensions are visible to the user,
4. defer, reject, and close actions carry explicit rationale state in the contract.

### Slice 5: Quality, rollout, and control hardening

Outcome:

1. the feature is covered by pack-specific evals and rollout discipline,
2. additional integrity dimensions can be added incrementally,
3. the workflow becomes a durable banking-grade control capability.

Acceptance gate:

1. quality is measured on drift detection usefulness, evidence quality, and remediation clarity,
2. rollout remains bounded and inspectable,
3. the feature improves control and servicing posture beyond a static case summary,
4. at least one integrity case type has explicit eval coverage for insufficient evidence,
   contradictory evidence, and no-safe-remediation scenarios.

### Slice 6: Documentation, Agent Context, and Branch Hygiene

Outcome:

1. documentation and context implications are reviewed explicitly,
2. any durable guidance changes are committed in the same slice as the implementation truth,
3. branch and PR hygiene are part of delivery rather than an afterthought.

Required review areas:

1. `lotus-ai/REPOSITORY-ENGINEERING-CONTEXT.md`
2. `lotus-ai/docs/architecture/system-overview.md`
3. `lotus-ai/docs/architecture/feature-status-and-roadmap.md`
4. relevant `lotus-platform/context/*` guidance if relationship-integrity orchestration becomes
   platform truth,
5. relevant Lotus skills if integrity-case delivery becomes a durable engineering pattern.

Current assessment for this RFC draft:

1. no immediate context or skill update is required before implementation begins,
2. implementation should revisit whether Lotus guidance needs stronger support for case-based
   integrity workflows and typed action orchestration,
3. if no durable change is needed later, that conclusion should still be recorded explicitly in the
   final slice.

Acceptance gate:

1. documentation and context review is completed explicitly,
2. any durable guidance updates are committed truthfully,
3. branch hygiene is closed with real evidence,
4. a deliberate "no change required" outcome is allowed but must be stated with rationale.

## Risks

1. If the integrity model is vague, the feature will become narrative-heavy and control-light.
2. If the case tries to cover too many dimensions in v1, the rollout will become too broad.
3. If remediation suggestions blur into pseudo-authoritative decisions, governance risk will rise
   sharply.
4. If closure is weakly defined, the system will create unresolved AI cases that do not improve
   operating discipline.

## Alternatives Considered

### 1. A better briefing system only

Rejected.

Reason:

1. a briefing helps interpretation,
2. but it does not preserve relationship integrity over time,
3. it does not explicitly govern drift and remediation closure.

### 2. A situation room without an explicit integrity model

Rejected.

Reason:

1. it is useful for events,
2. but weaker for ongoing relationship control,
3. it lacks the explicit banking-grade framing around mandate and servicing integrity.

### 3. A centralized AI decision engine

Rejected.

Reason:

1. it would blur domain ownership,
2. it would overstep authority boundaries,
3. it would be much harder to defend as a banking-grade control design.

## Success Criteria

This RFC is successful when:

1. Lotus can identify and manage material relationship-integrity drift through explicit action
   cases,
2. the feature materially improves control quality and servicing readiness,
3. domain truth and workflow authority remain in the owning systems,
4. the AI layer remains evidence-backed, auditable, and human-controlled,
5. the platform gains a genuinely banking-grade agentic workflow rather than another assistive
   summary feature,
6. the first release proves a credible integrity-preservation path for a bounded seeded use case
   without overreaching into autonomous control.
