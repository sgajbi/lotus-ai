# RFC-0031: Governed Agent Workflow Packs and Bounded AI Runtime

- Status: In Progress
- Date: 2026-04-18
- Owners:
  - lotus-ai maintainers
  - lotus-gateway maintainers
  - lotus-workbench maintainers
- Requires Approval From:
  - lotus-ai maintainers
  - lotus-gateway maintainers
  - lotus-workbench maintainers
  - lotus-platform maintainers
  - repository maintainers for any domain-owned workflow packs introduced under this RFC
- Related:
  - `RFC-0021-domain-ai-capability-packs-and-product-maturity.md`
  - `RFC-0024-portfolio-narrative-copilot-for-lotus-performance.md`
  - `RFC-0028-relationship-manager-briefing-agent-for-the-lotus-ecosystem.md`
  - `../../../lotus-platform/rfcs/RFC-0069-lotus-ai-shared-ai-platform-service.md`
  - `../../../lotus-platform/rfcs/RFC-0070-gold-standard-product-experience-foundation-and-ownership-model.md`
  - `../../../lotus-platform/rfcs/RFC-0072-platform-wide-multi-lane-ci-validation-and-release-governance.md`
  - `../../../lotus-platform/rfcs/RFC-0080-lotus-agent-runtime-demo-skill-pack-and-guidance-hardening.md`
  - `../../../lotus-platform/rfcs/RFC-0081-slice-9-ai-surface-governance-and-assistive-workflow-controls-evidence.md`
  - `../../../lotus-workbench/docs/rfcs/RFC-0020-ai-advisor-brief-copilot.md`

## Summary

Lotus already has a governed AI capability service in `lotus-ai`, experience orchestration in
`lotus-gateway`, and product-facing AI governance direction in RFC-0081 and Workbench RFC-0020.

What Lotus still lacks is a first-class runtime pattern for packaging multi-step, evidence-grounded,
workflow-safe AI assistance into repeatable product capabilities.

OpenClaw is useful as inspiration here, but not as a direct architectural template. It demonstrates
the value of:

1. explicit task packaging,
2. durable runtime state,
3. asynchronous execution,
4. multi-surface operator interaction,
5. reusable workflow-oriented capability packs.

Lotus should adopt those strengths selectively while rejecting OpenClaw assumptions that are wrong
for a banking platform, especially:

1. host-level tool freedom,
2. weak trust-boundary assumptions,
3. community-installed skills,
4. unbounded memory or agent autonomy,
5. runtime models where AI can blur into workflow authority.

This RFC proposes a Lotus-native answer:

1. introduce governed `workflow packs` as the packaging model for bounded AI-assisted workflows,
2. extend `lotus-ai` into a bounded runtime for pack execution, async jobs, review state, and audit,
3. require calling apps and gateway-owned composition layers to remain accountable for business
   context and workflow consequences,
4. surface pack execution and review state through governed `lotus-gateway` and `lotus-workbench`
   contracts,
5. keep authoritative domain truth in the owning services.

The result should be a Lotus runtime that is more operationally useful than simple prompt calls,
without becoming an unconstrained agent platform.

## Implementation Status

This RFC is now partially implemented.

Foundational work is in progress through the RFC-0032 delivery slices already landed in `lotus-ai`:

1. workflow-pack registry contracts exist,
2. eligibility evaluation exists,
3. bounded operator control actions exist,
4. the first owner-grounded `advisor_brief.pack` family is registered as the Phase-1 reference path.

Still pending under this broader RFC:

1. the full bounded workflow-pack runtime,
2. durable pack-run ledger and review-state contracts,
3. broader multi-pack execution posture,
4. production-grade durable workflow-pack activation history.

## Current Reality And Evidence

The current branch proves only the registry and activation foundations for this broader runtime RFC.

Implemented evidence now available in `lotus-ai`:

1. workflow-pack contracts and seeded registration truth in `src/app/contracts/workflow_packs.py`
   and `src/app/services/workflow_pack_registry.py`,
2. registry, eligibility, and bounded control-plane routes in `src/app/routers/workflow_packs.py`
   and `src/app/main.py`,
3. eligibility and operator-control behavior in `src/app/services/workflow_pack_activation.py` and
   `src/app/services/workflow_pack_control.py`,
4. contract and behavior coverage in `tests/unit/test_workflow_pack_registry.py`,
   `tests/unit/test_workflow_pack_activation.py`, `tests/unit/test_workflow_pack_control.py`,
   `tests/integration/test_workflow_pack_registry_api_contract.py`,
   `tests/integration/test_workflow_pack_activation_api_contract.py`,
   `tests/integration/test_workflow_pack_control_api_contract.py`, and
   `tests/unit/test_openapi_contract.py`,
5. operator and integration guidance in `docs/guides/integration-guide.md`,
   `docs/guides/workflow-pack-owner-onboarding.md`, `docs/runbooks/service-operations.md`, and
   `wiki/`.

Evidence that remains intentionally absent because this RFC is only partially implemented:

1. no durable pack-run ledger schema or storage,
2. no shared runtime-state plus review-state contract family consumed by gateway and Workbench,
3. no workflow-pack execution engine beyond current registration and activation groundwork.

## Repository Fit

This RFC is intentionally housed in `lotus-ai` because the primary architectural change is the
evolution of `lotus-ai` from a bounded task-execution service into a bounded workflow-pack runtime.

This is still a cross-app RFC.

It remains dependent on:

1. `lotus-platform` governance for standards and approval posture,
2. `lotus-gateway` for cross-service composition,
3. `lotus-workbench` for governed UI behavior,
4. domain services for pack ownership where business meaning is local.

The repository location reflects implementation center of gravity, not sole ownership.

## Relationship to Existing lotus-ai Pack Model

This RFC does not replace the capability-pack direction established by
`RFC-0021-domain-ai-capability-packs-and-product-maturity.md`.

Instead:

1. `RFC-0021` defined capability packs as the product-maturity layer above generic task families,
2. this RFC defines the next runtime-bearing evolution for the subset of packs that need:
   - multi-step orchestration,
   - durable lifecycle state,
   - explicit review checkpoints,
   - artifact and feedback persistence,
   - cross-app operational visibility.

The intended model is:

1. all workflow packs are capability packs,
2. not all capability packs need workflow-pack runtime semantics.

Simple bounded packs can remain task-oriented.

Workflow packs are for the cases where product value depends on:

1. lifecycle visibility,
2. async execution,
3. human review,
4. cross-service evidence gathering,
5. workflow-safe handoff.

## Why This RFC Exists

The current Lotus AI posture is strong but incomplete.

Today Lotus already has:

1. bounded AI task execution in `lotus-ai`,
2. prompt, provider, retrieval, audit, and async foundations,
3. evidence-carrying AI responses in some gateway flows,
4. governance direction for AI disclosure, review state, feedback, and workflow separation,
5. at least one strong product candidate in the `Advisor Brief` flow.

What is still missing is a platform-level model for packaging these capabilities into reusable,
auditable, workflow-safe units that product teams can adopt consistently.

Without that model, Lotus risks drifting into one of two bad states:

1. every AI-enabled feature becomes a one-off integration seam with duplicated wiring and weak
   runtime consistency,
2. `lotus-ai` grows into a vague central AI monolith that steals business orchestration and domain
   meaning from the services that actually own them.

Lotus needs a middle path:

1. more operational coherence than isolated task calls,
2. much stronger governance and domain boundaries than a general-purpose agent shell.

## Decision

Lotus will introduce a governed workflow-pack and bounded-runtime model for AI-assisted product and
operator workflows.

Specifically:

1. `workflow packs` will become the canonical packaging model for reusable Lotus AI-assisted
   workflows.
   They are the runtime-bearing, orchestration-capable subclass of the broader capability-pack
   model already established in RFC-0021.
2. `lotus-ai` will own the runtime substrate for pack execution, pack policy, async job lifecycle,
   audit, feedback capture, and evidence assembly.
3. calling systems will remain responsible for:
   - business context assembly,
   - source-truth selection,
   - workflow state,
   - human review posture,
   - user-facing consequence of accepting or rejecting AI output.
4. `lotus-gateway` will own cross-service product composition and pack invocation for Workbench or
   other product-facing flows.
5. `lotus-workbench` will render AI-assisted output through shared shell patterns that keep
   authoritative workflow truth separate from AI-generated drafts, rationale, or suggestions.
6. Lotus will not introduce unrestricted tool-execution agents into production workflows under this
   RFC.
7. OpenClaw-style ideas may inform packaging, async runtime state, and operator ergonomics, but
   Lotus will preserve its stricter governance, audit, and ownership boundaries.

## Problem Statement

The current problem is not "Lotus has no AI service." It is that the current seams do not yet form
one coherent runtime operating model.

The concrete gaps are:

1. no platform-standard packaging unit for multi-step AI-assisted workflows,
2. no shared workflow-pack catalog that states who owns a capability, what it may access, what it
   may produce, and how it degrades,
3. no standard model for pack lifecycle states such as submitted, running, partial, awaiting review,
   completed, rejected, or expired,
4. no standard cross-repo pattern for pack-specific evidence, review checkpoints, and banker
   feedback,
5. no standard gateway pattern for cross-service fact assembly plus pack execution plus product-safe
   response shaping,
6. no standard Workbench UX grammar for initiating, monitoring, reviewing, revising, and accepting
   AI-assisted workflow output beyond the first narrow slices.

Without a governed answer, future teams will be tempted to add:

1. page-local copilots,
2. one-off task adapters,
3. duplicated audit rendering,
4. weakly structured AI drafts,
5. hidden partial-data behavior,
6. unsupported action affordances that imply AI workflow authority it does not actually have.

## Goals

1. Define `workflow packs` as the canonical packaging model for Lotus AI-assisted workflows.
2. Extend `lotus-ai` from a task-oriented capability layer into a bounded runtime that can execute,
   monitor, and audit workflow packs.
3. Keep business-domain meaning and workflow authority in the owning Lotus services.
4. Define a consistent lifecycle model for async and synchronous AI-assisted workflow execution.
5. Standardize evidence, audit, review-state, and feedback posture for pack outputs.
6. Provide a reusable cross-service composition pattern for gateway-owned product workflows.
7. Create a platform path for high-value workflows such as advisor briefing, proposal rationale,
   recommendation explanation, reporting QA, and operator support summarization.
8. Improve Lotus product ergonomics and operator usefulness without degrading the platform's
   banking-grade trust model.

## Non-Goals

1. Turning Lotus into a general-purpose consumer AI assistant product.
2. Allowing unrestricted shell, filesystem, browser, or network tool execution inside production AI
   workflows.
3. Moving portfolio, performance, risk, advisory, management, reporting, or consent truth into
   `lotus-ai`.
4. Replacing deterministic workflow logic with agentic reasoning.
5. Introducing community-installed or dynamically downloaded workflow packs.
6. Creating a memory-first autonomous agent that carries mutable workflow authority across sessions.
7. Replacing RFC-0081 shell governance or RFC-0069 service-boundary rules.

## Principles

### 1. Domain authority stays upstream

`lotus-ai` may assist. It does not own:

1. portfolio truth,
2. analytics truth,
3. proposal lifecycle truth,
4. management workflow truth,
5. reporting truth,
6. approval, consent, or execution truth.

### 2. Packaging is first-class

Lotus should not treat each AI use case as "just another prompt call."

Each reusable workflow needs:

1. an identity,
2. an owner,
3. an input contract,
4. a source-evidence policy,
5. an output contract,
6. a degradation model,
7. a review model,
8. a runtime and audit posture.

### 3. Product workflow is not the same thing as agent autonomy

The runtime may be multi-step internally, but product flows must remain bounded, inspectable, and
reviewable.

### 4. Async state is part of the product contract

When a workflow takes time, Lotus should expose durable states rather than pretending every AI task
is instant.

### 5. AI output must remain subordinate to workflow truth

This RFC inherits RFC-0081's rule that AI-generated content must never masquerade as:

1. approval,
2. consent,
3. booking or execution authority,
4. final banker instruction,
5. authoritative portfolio or analytics truth.

### 6. Inspiration is acceptable; trust-model downgrade is not

Lotus may learn from OpenClaw's packaging and runtime ergonomics, but must not import its looser
operator and execution assumptions.

## Terms

### Workflow Pack

A repository-managed, versioned, governed definition of an AI-assisted workflow capability.

A pack defines:

1. capability identity,
2. owning repository and owning service,
3. supported caller surfaces,
4. structured input contract,
5. required evidence sources,
6. allowed runtime actions,
7. output schema,
8. review-state model,
9. feedback contract,
10. degradation and refusal behavior.

In Lotus terms, a workflow pack is a capability pack that additionally requires:

1. explicit runtime lifecycle,
2. optional async execution,
3. review-state handling,
4. evidence/artifact persistence beyond a single task response.

### Bounded Runtime

The `lotus-ai` execution layer that can run workflow packs with explicit policy, lifecycle, audit,
and evidence contracts.

### Review Checkpoint

A required human or workflow review point where AI output can be:

1. viewed,
2. revised,
3. accepted,
4. rejected,
5. escalated,
6. retried.

### Evidence Bundle

The structured source and runtime evidence attached to a pack run, including:

1. source refs,
2. retrieval posture,
3. prompt and provider metadata,
4. generated artifacts,
5. supportability state,
6. feedback and review linkage.

## Proposed Architecture

### 1. Workflow Pack Model

Each workflow pack should be a governed artifact with at least:

1. `pack_id`
2. `version`
3. `owner_repository`
4. `owner_service`
5. `purpose`
6. `supported_callers`
7. `input_schema`
8. `required_context_sections`
9. `required_source_refs`
10. `runtime_policy`
11. `prompt_policy`
12. `provider_policy`
13. `output_schema`
14. `degradation_rules`
15. `review_model`
16. `feedback_model`
17. `audit_requirements`

The pack definition should remain repository-managed and reviewable in code, not mutable through
uncontrolled runtime editing.

### Canonical storage decision

The canonical workflow-pack definition should live in the owning repository, not centrally in
`lotus-ai`.

That means:

1. the owning repository stores the pack contract, builder logic, and pack-specific schemas,
2. `lotus-ai` stores runtime registration, activation posture, and execution metadata,
3. the runtime consumes registered pack manifests rather than becoming the editorial owner of
   business-domain pack definitions.

This is the right fit for Lotus because it preserves domain ownership:

1. cross-service product packs can be owned by `lotus-gateway`,
2. advisory packs can be owned by `lotus-advise`,
3. management packs can be owned by `lotus-manage`,
4. reporting packs can be owned by `lotus-report`,
5. generic shared packs can still be owned by `lotus-ai`.

### Initial workflow-pack classes

The first high-value classes should be:

1. `advisor_brief`
   source-grounded briefing draft over portfolio/performance facts,
2. `proposal_rationale`
   explanation and reviewer-facing rationale over deterministic advisory outputs,
3. `management_operating_summary`
   management-side supportability or exception summary,
4. `reporting_quality_summary`
   reporting-oriented QA and discrepancy explanation,
5. `operator_incident_explainer`
   support-facing explanation over bounded runtime evidence.

Not every pack must be user-facing in Workbench. Some may be operator-facing or support-facing.

### 2. Runtime Responsibilities in `lotus-ai`

`lotus-ai` should own:

1. workflow-pack registry and activation posture,
2. pack execution orchestration,
3. synchronous and asynchronous execution modes,
4. lifecycle state persistence,
5. prompt and provider resolution,
6. retrieval and evidence governance,
7. audit record persistence,
8. generated artifact persistence where applicable,
9. feedback capture persistence,
10. runtime status and operator surfaces.

### Runtime lifecycle model

The runtime should expose explicit states such as:

1. `SUBMITTED`
2. `VALIDATING`
3. `RUNNING`
4. `PARTIAL`
5. `AWAITING_REVIEW`
6. `COMPLETED`
7. `REJECTED`
8. `FAILED`
9. `EXPIRED`

State names may be normalized to existing Lotus vocabulary, but the lifecycle must stay explicit.

### Runtime action model

Under this RFC, pack runtime actions are bounded to:

1. prompt execution,
2. structured generation,
3. explanation/summarization/classification/extraction,
4. governed retrieval,
5. internal pack-step transitions,
6. artifact assembly and evidence packaging,
7. feedback linkage,
8. explicit handoff to a human or owning workflow.

This RFC does not authorize:

1. arbitrary shell execution,
2. unrestricted browser automation,
3. unrestricted network actions,
4. live workflow mutation without an explicit owning-service contract.

### 3. Calling-Service Responsibilities

Calling services and composition layers must remain responsible for:

1. assembling domain-correct context,
2. selecting authoritative source facts,
3. deciding when a pack is appropriate,
4. determining workflow consequences of accepted output,
5. rejecting unsupported AI outputs,
6. exposing workflow truth distinctly from AI-assist output.

### Gateway-owned pack composition

When a workflow spans multiple upstream services, `lotus-gateway` should usually own:

1. cross-service fact assembly,
2. supportability shaping,
3. pack invocation,
4. product-safe response shaping.

This is the right pattern for:

1. advisor brief,
2. cross-service review summaries,
3. workbench-facing assistant panels that rely on multiple upstream authorities.

### Domain-service-owned pack composition

When a workflow is domain-local, the owning service may assemble and invoke the pack directly while
still using `lotus-ai` as the runtime.

This is the right pattern for:

1. `lotus-advise` proposal rationale,
2. `lotus-manage` management-side supportability summaries,
3. operator and support flows local to one service boundary.

### 4. Workbench Responsibilities

`lotus-workbench` should not become a direct agent host.

It should own:

1. initiation affordances for governed packs,
2. lifecycle-state rendering,
3. provenance and evidence rendering,
4. review-state rendering,
5. feedback capture UI,
6. workflow-safe accept/reject/revise actions through gateway-owned contracts.

It should not own:

1. business fact assembly,
2. prompt assembly,
3. direct browser-to-`lotus-ai` execution for product workflows,
4. silent reinterpretation of AI review or supportability state.

### 5. Workflow-Pack Contract Shape

The exact wire schema can evolve, but the runtime should support a contract family shaped like:

```json
{
  "pack_id": "advisor_brief.v1",
  "caller": {
    "caller_app": "lotus-gateway",
    "requested_by": "advisor@lotus",
    "tenant_id": "tenant-sg-001",
    "correlation_id": "corr-123"
  },
  "execution_mode": "sync_or_async",
  "context": {
    "summary": "Generate a source-grounded advisor briefing draft.",
    "payload": {},
    "source_refs": []
  },
  "review_expectation": {
    "requires_human_review": true,
    "workflow_authority_owner": "lotus-gateway"
  }
}
```

The response family should include:

1. pack identity and version,
2. lifecycle state,
3. result payload,
4. review state,
5. supportability state,
6. audit metadata,
7. evidence bundle,
8. artifact refs,
9. feedback linkage.

### 6. Pack Ownership Model

Workflow-pack ownership must follow business meaning.

### `lotus-ai`

Owns:

1. shared generic packs where business meaning remains generic,
2. runtime registry and execution substrate,
3. pack validation, storage, policy, and lifecycle controls.

### `lotus-gateway`

Owns:

1. cross-service product workflow packs,
2. pack-specific response shaping for Workbench,
3. product-safe partial and degraded state handling.

### `lotus-advise`

Owns:

1. advisory workflow packs,
2. proposal rationale packs,
3. bounded recommendation-explanation packs tied to advisory truth.

### `lotus-manage`

Owns:

1. management-side workflow packs,
2. operational supportability summaries,
3. exception-handling narrative packs that remain subordinate to management workflow truth.

### `lotus-report`

Owns:

1. report-generation explanation packs,
2. report QA and discrepancy explanation packs.

### `lotus-performance` and `lotus-risk`

May own:

1. analytic explanation packs,
2. bounded commentary packs over authoritative metrics,
3. support-facing diagnostic explanation packs.

These packs must still avoid inventing new analytical truth.

## OpenClaw Reference Findings

This RFC was tightened after a local review of the cloned `openclaw` repository under
`c:\Users\Sandeep\projects\openclaw`.

The following findings materially informed the design:

### 1. Skill and pack packaging is useful; install model is not

OpenClaw's skill system, documented in
`openclaw/docs/tools/skills.md`, is strong at:

1. packaging reusable capabilities as on-disk folders with `SKILL.md`,
2. establishing precedence rules,
3. supporting per-workspace and shared skill visibility,
4. making capability packaging first-class.

That reinforces the Lotus decision to make packaging first-class too.

Lotus should not copy:

1. user-installed third-party skill distribution,
2. unmanaged local override sprawl,
3. trust of arbitrary workspace-installed behavior in product workflows.

So the Lotus equivalent is:

1. repo-owned workflow packs,
2. reviewed and versioned in code,
3. registered into `lotus-ai`,
4. never community-installed into production flows.

### 2. Explicit lifecycle and queueing are worth adopting

OpenClaw's `docs/concepts/queue.md` and `docs/concepts/agent-loop.md` show the practical value of:

1. explicit lane-aware queueing,
2. per-session serialization,
3. durable lifecycle events,
4. immediate accepted-state responses with later wait/status inspection.

Lotus should borrow the principle, not the exact model.

The equivalent Lotus runtime posture should be:

1. immediate run acceptance for async workflow packs,
2. durable lifecycle state in `lotus-ai`,
3. product-facing lifecycle rendering in `lotus-gateway` and `lotus-workbench`,
4. no silent "fire and forget" AI work for workflow-critical capabilities.

### 3. OpenClaw's trust model is the clearest reason not to copy its runtime wholesale

OpenClaw's `README.md`, `docs/concepts/architecture.md`, `docs/cli/security.md`, and
`docs/gateway/sandboxing.md` are explicit that:

1. it is fundamentally a personal-assistant trust model,
2. sandboxing is optional,
3. host-level execution is a normal default in some modes,
4. mixed-trust operation is not the primary design center.

That is exactly what Lotus must not import.

Lotus is a banking platform. Therefore:

1. runtime action surfaces stay bounded,
2. no host-level shell or browser freedom is implied by this RFC,
3. review checkpoints and workflow-authority separation remain mandatory,
4. operator ergonomics are welcome, trust-boundary downgrade is not.

### 4. Session snapshots are useful inspiration for registration and rollout

OpenClaw's skills documentation emphasizes snapshot-based visibility and hot reload behavior.

Lotus should apply that idea carefully:

1. pack definitions remain code-owned in their repositories,
2. `lotus-ai` maintains a runtime registration snapshot,
3. activation and rollout posture are explicit,
4. runtime registration should not imply mutable user-level pack editing.

## OpenClaw-to-Lotus Translation Matrix

The goal is not to import OpenClaw terminology or runtime structure wholesale.

It is to translate the useful operating ideas into Lotus-owned contracts.

| OpenClaw reference pattern | Source reviewed in local clone | Lotus translation | Lotus stance |
| --- | --- | --- | --- |
| Skills as first-class on-disk packages with declared metadata | `docs/tools/skills.md` | Repository-owned workflow-pack definitions with explicit metadata, schemas, runtime policy, and owner identity | Adopt the packaging principle, but keep ownership code-reviewed and repository-scoped |
| Workspace and user skill precedence | `docs/tools/skills.md` | Single canonical source in the owning Lotus repository, then explicit registration into `lotus-ai` runtime | Reject mutable local override chains for governed product flows |
| Public skill installation ecosystem | `docs/tools/skills.md` | No third-party or end-user installed workflow packs in production | Reject |
| Immediate run acceptance plus later wait/status inspection | `docs/concepts/agent-loop.md` | Sync and async workflow-pack execution with durable lifecycle APIs and explicit status retrieval | Adopt |
| Queue-backed serialization and lane-aware execution | `docs/concepts/queue.md` | Runtime-managed scheduling, concurrency limits, and execution isolation inside `lotus-ai` | Adopt the need for queueing; keep the concrete shape Lotus-native |
| Gateway daemon coordinating clients, sessions, and agent execution | `docs/concepts/architecture.md` | `lotus-ai` as bounded runtime service, with `lotus-gateway` remaining product composition owner | Adapt with stricter service boundaries |
| Optional sandboxing around potentially dangerous tools | `docs/gateway/sandboxing.md` | Production packs expose only explicitly governed runtime actions; there is no assumption of general host-tool access | Reject the default trust posture; keep bounded action surfaces instead |
| Personal-assistant trust model with warnings for mixed-trust use | `README.md`, `docs/cli/security.md` | Banking-grade multi-actor model with provenance, review checkpoints, and workflow-authority separation as baseline requirements | Reject |
| Snapshot and hot-reload visibility for skills | `docs/tools/skills.md` | Registered workflow-pack manifest snapshots, explicit activation posture, versioned rollout, and auditable change history | Adapt carefully |

## Why Not Adopt OpenClaw Directly

OpenClaw is not the right platform substrate for Lotus.

### OpenClaw strengths worth learning from

1. skill-packaging model,
2. explicit runtime identity for reusable capabilities,
3. async execution ergonomics,
4. operator-facing task state,
5. coherent workflow-pack composition.

### OpenClaw assumptions Lotus must reject

1. one trusted operator boundary as the default model,
2. broad host-level tool access,
3. user-installed unreviewed skill ecosystems,
4. conversational autonomy as a primary operating model,
5. runtime patterns where AI can act with weak domain boundary control.

The right Lotus move is not "adopt OpenClaw."

It is:

1. borrow useful runtime packaging ideas,
2. translate them into Lotus governance vocabulary,
3. enforce them through `lotus-ai`, `lotus-gateway`, `lotus-workbench`, and domain-owned pack
   boundaries.

## Detailed Boundary Rules

### Rule 1: No pack may establish workflow authority

Workflow packs may produce:

1. draft text,
2. explanation,
3. recommendation framing,
4. issue summaries,
5. operator hints,
6. structured candidate outputs.

Workflow packs may not establish:

1. approval,
2. execution readiness,
3. client consent,
4. booking or trading authority,
5. source-of-truth analytics or portfolio state.

### Rule 2: Every pack must declare its truth owner

Each pack must state:

1. which service owns workflow truth,
2. which services own source facts,
3. whether output is draft, explanation, suggestion, or support summary,
4. which human or system must review it before consequence-bearing use.

### Rule 3: Partial data must stay visible

Pack outputs must preserve:

1. partial source readiness,
2. unsupported inputs,
3. retrieval gaps,
4. provider fallback or stub posture,
5. evidence limitations.

### Rule 4: Feedback is part of the contract

Banker and operator feedback should be standardized as part of the workflow-pack model, not added
page by page.

### Rule 5: Runtime evidence must be durable

Where a workflow pack materially affects:

1. customer-facing preparation,
2. operator explanation,
3. workflow review,
4. audit posture,
5. generated artifacts,

the runtime must preserve sufficient audit and evidence linkage to explain:

1. what ran,
2. what it saw,
3. what it produced,
4. why it degraded or failed,
5. who accepted or rejected the result.

## Initial Target Use Cases

### 1. Advisor Brief

This is the flagship starting point because Lotus already has:

1. Workbench UX direction,
2. gateway composition direction,
3. bounded `lotus-ai` task contracts,
4. evidence and audit posture.

Under this RFC, Advisor Brief should graduate from a task-specific seam into a pack-governed model.

### 2. Proposal Rationale and Alternatives Review

`lotus-advise` should be able to request pack-governed explanation and review assistance over
deterministic proposal artifacts while preserving advisory workflow truth.

### 3. Management Exception Summaries

`lotus-manage` should gain bounded AI assistance for operational supportability and exception review
without moving management workflow control into `lotus-ai`.

### 4. Reporting QA and Review Summaries

`lotus-report` should be able to generate bounded QA and discrepancy narratives over reporting
payloads and evidence bundles.

### 5. Operator Support and Incident Explanation

Platform and service operators should be able to use bounded packs to summarize incident evidence,
runtime posture, and likely diagnostics over explicit evidence bundles.

## Resolved Design Decisions

This RFC intentionally resolves the following design decisions rather than leaving them open.

### 1. Pack ownership and physical location

Decision:

1. canonical workflow-pack definitions live in the owning repository,
2. `lotus-ai` owns the runtime registry, activation posture, and execution substrate,
3. pack registration into `lotus-ai` is required before execution.

Why:

1. it preserves domain ownership,
2. it avoids turning `lotus-ai` into the editorial owner of every business workflow,
3. it keeps review and schema evolution close to the repo that owns the business meaning.

### 2. Phase-1 flagship use case

Decision:

The first end-to-end workflow-pack implementation should be `advisor_brief`, using the existing
`lotus-gateway` plus `lotus-workbench` plus `lotus-ai` path as the proving ground.

Why:

1. Lotus already has the strongest concrete groundwork there,
2. it is cross-service enough to prove the model,
3. it is safer and more auditable than jumping directly to write-bearing workflow assistance.

### 3. Lifecycle vocabulary posture

Decision:

Workflow-pack lifecycle should reuse the existing Lotus async-runtime vocabulary where possible and
extend it only where product review state genuinely requires more precision.

Target posture:

1. execution status remains aligned with existing async runtime and audit/event posture,
2. review-state is layered on top rather than smuggled into generic execution state,
3. product surfaces render both execution state and review state explicitly.

Why:

1. this reduces avoidable contract sprawl,
2. it keeps runtime and review concerns separate,
3. it aligns better with existing `lotus-ai` async foundations than inventing a parallel state
   machine from scratch.

## Repository Impact Matrix

The following matrix states what this RFC is expected to change, what remains unchanged, and why.

| Repository | Expected Change Level | What Changes | What Stays Unchanged |
| --- | --- | --- | --- |
| `lotus-ai` | High | Workflow-pack registry, pack execution model, lifecycle state, async runtime linkage, evidence and artifact model, feedback and review linkage, operator status surfaces, pack-oriented API/contracts | It still does not own business-domain truth, workflow authority, or deterministic domain logic |
| `lotus-gateway` | High | Cross-service fact assembly for pack-backed flows, pack invocation adapters, product-safe lifecycle mapping, supportability/degraded-state contracts, provenance-preserving response envelopes | It still does not become the authority for AI generation policy, portfolio truth, or analytics truth |
| `lotus-workbench` | High | Shared UI primitives for lifecycle, provenance, review, and feedback; pack-backed assistive modules; workflow-safe accept/reject/revise surfaces | It still does not call `lotus-ai` directly for product workflows or assemble business facts locally |
| `lotus-advise` | Medium | Domain-owned advisory packs such as proposal rationale, alternatives review, reviewer-note assistance, bounded workflow explanation | Advisory lifecycle truth, approval rules, and deterministic proposal semantics stay in `lotus-advise` |
| `lotus-manage` | Medium | Domain-owned management packs such as operating summaries, supportability explanation, exception review summaries | Discretionary management workflow authority and operational lifecycle truth stay in `lotus-manage` |
| `lotus-report` | Medium | Reporting QA/discrepancy explanation packs, generated review summaries over reporting evidence bundles | Report assembly and reporting contract truth stay in `lotus-report`; source truth remains upstream |
| `lotus-performance` | Low to Medium | Optional bounded explanation/commentary packs over performance outputs; pack input builders for gateway/domain-owned flows | Performance methods, benchmark analytics, lineage, and calculation truth stay in `lotus-performance` |
| `lotus-risk` | Low to Medium | Optional bounded explanation/commentary packs over risk outputs; support-facing diagnostic packs | Risk methodology and authoritative risk outputs stay in `lotus-risk` |
| `lotus-core` | Low | Mostly indirect change through upstream evidence shape, supportability payloads, and fact-bundle inputs for other pack-backed flows | `lotus-core` remains system-of-record and must not become a workflow-pack owner for downstream business meaning |
| `lotus-platform` | Medium | Governance, RFC cross-links, standards, validation posture, possible contract or registry guards, onboarding/context updates if adopted | It still does not become the runtime host; it governs rather than owning product execution |

### Phase-1 implementation center of gravity

If this RFC is approved, the first implementation wave should focus on:

1. `lotus-ai`
2. `lotus-gateway`
3. `lotus-workbench`

That is the smallest slice that can prove the runtime model end to end.

### Likely later-phase adopters

The next likely adopters after the first cross-app slice are:

1. `lotus-advise`
2. `lotus-manage`
3. `lotus-report`

`lotus-performance` and `lotus-risk` are more likely to contribute bounded explanation packs or
fact-bundle helpers than to become the first primary rollout surface.

`lotus-core` should remain mostly upstream and indirect unless a narrowly scoped support/operator
use case truly requires a core-owned pack family.

## Implementation Plan

Every completed slice under this RFC should be reviewed before the next slice begins.

That review should check:

1. whether the slice reduced or increased complexity,
2. whether code, contracts, tests, docs, and context remained aligned,
3. whether dead code, duplicate logic, or stale wording can be removed before continuing,
4. whether any durable lesson should be promoted into repo docs, context, wiki source, or shared
   agent guidance.

### Slice 1: Workflow-Pack Contract and Registry Foundation

1. define pack metadata schema,
2. define runtime lifecycle states,
3. define review-state and feedback-state primitives,
4. define pack registry ownership and activation posture,
5. document which repo owns which initial pack families,
6. implement owning-repo registration into `lotus-ai` rather than centralizing pack definitions in
   the runtime repo.

Deliverables:

1. pack metadata contract,
2. lifecycle contract,
3. registry and ownership docs,
4. targeted validation or schema tests.

### Slice 2: `lotus-ai` Runtime Extension

1. add workflow-pack execution surfaces to `lotus-ai`,
2. unify sync and async pack execution posture,
3. persist lifecycle, audit, and artifact references,
4. preserve retrieval and provider governance,
5. expose operator runtime-status surfaces for pack execution,
6. keep runtime status separate from review-state semantics.

Deliverables:

1. runtime endpoints or service seams,
2. persistence models,
3. lifecycle tests,
4. async execution tests,
5. audit and evidence contract tests.

### Slice 3: Gateway Product Integration Pattern

1. define gateway-owned composition pattern for cross-service packs,
2. map pack lifecycle and review state into product-safe response envelopes,
3. standardize degraded-state handling for pack-backed product surfaces,
4. prove the pattern first through advisor brief,
5. avoid direct browser-to-`lotus-ai` pack execution for Workbench surfaces.

Deliverables:

1. gateway composition guidance,
2. one implemented gateway-owned pack flow,
3. contract and integration tests,
4. supportability guidance.

### Slice 4: Shared Workbench AI Workflow Primitives

1. add shell-wide primitives for:
   - provenance,
   - review state,
   - feedback,
   - pack lifecycle rendering,
   - draft-vs-truth separation,
2. integrate those primitives into the first pack-backed surfaces,
3. keep UI workflow-safe and audit-aware.

Deliverables:

1. shared Workbench primitives,
2. product-surface integration,
3. interaction tests,
4. visual and supportability evidence.

### Slice 5: Domain-Owned Pack Rollout

1. add at least one domain-owned pack outside the first gateway-backed case,
2. prove pack ownership boundaries across:
   - `lotus-advise`,
   - `lotus-manage`,
   - optionally `lotus-report`,
3. validate that domain services remain accountable for business meaning.

Deliverables:

1. implemented domain-owned pack,
2. repo-local contract docs,
3. pack execution evidence,
4. integration tests.

### Slice 6: Governance, Feedback, and Evaluation Hardening

1. standardize feedback capture,
2. bind evaluation posture to pack rollout,
3. ensure review-state and feedback metadata flow through UI and audit surfaces,
4. update AGENTS and AI-surface guidance only where runtime truth has changed materially.

Deliverables:

1. feedback contract,
2. eval linkage,
3. operator docs,
4. governance updates.

## API and Contract Implications

This RFC expects evolution in:

1. `lotus-ai` task/runtime contracts,
2. gateway composition contracts for pack-backed flows,
3. Workbench view models for lifecycle, review, provenance, and feedback,
4. domain-service integration contracts where a service owns a pack family.

It does not require immediate replacement of all existing task contracts. A staged coexistence model
is acceptable while pack-based execution becomes the preferred path for multi-step or workflow-rich
capabilities.

## Testing and Validation Requirements

### `lotus-ai`

1. workflow-pack schema validation,
2. lifecycle transition tests,
3. async worker and persistence tests,
4. retrieval and provider posture tests,
5. audit/evidence propagation tests,
6. feedback and review linkage tests.

### `lotus-gateway`

1. product-safe composition tests,
2. partial and degraded-state tests,
3. contract tests for pack-backed UI flows,
4. upstream evidence preservation tests.

### `lotus-workbench`

1. lifecycle rendering tests,
2. provenance and review-state rendering tests,
3. feedback interaction tests,
4. browser validation where pack-backed surfaces are materially changed.

### Domain services

1. pack-specific context assembly tests,
2. refusal and unsupported-condition tests,
3. business-boundary tests proving AI output remains subordinate to domain truth.

## Risks and Mitigations

### Risk: Lotus accidentally builds a central AI monolith

Mitigation:

1. require explicit pack ownership,
2. require truth-owner declarations,
3. keep business context assembly in the calling service or gateway.

### Risk: Workflow packs become disguised prompt files with weak contracts

Mitigation:

1. require pack schemas,
2. require evidence policy,
3. require review and degradation models,
4. add registry and contract validation.

### Risk: Product teams bypass pack governance with one-off task calls

Mitigation:

1. define pack-backed flows as the standard path for workflow-rich capabilities,
2. add architectural review pressure through gateway and workbench governance,
3. keep task APIs for simpler bounded utilities only.

### Risk: OpenClaw inspiration is misunderstood as permission for broader autonomy

Mitigation:

1. document explicitly what Lotus is not adopting,
2. keep action boundaries narrow,
3. preserve human review and workflow authority separation.

### Risk: Async runtime makes failures harder to understand

Mitigation:

1. preserve explicit lifecycle states,
2. require operator-facing runtime surfaces,
3. persist evidence and artifact refs,
4. standardize failure and partial-state rendering.

## Alternatives Considered

### Alternative 1: Keep the current task-only model and let each team wire its own orchestration

Rejected because it would create:

1. duplicated integration seams,
2. inconsistent lifecycle handling,
3. inconsistent audit and review posture,
4. growing cross-repo drift.

### Alternative 2: Move full workflow orchestration into `lotus-ai`

Rejected because it would pull business ownership away from:

1. gateway,
2. domain services,
3. product workflow owners.

### Alternative 3: Adopt an OpenClaw-like general agent platform directly

Rejected because Lotus needs:

1. stronger role boundaries,
2. stronger audit posture,
3. bounded execution,
4. review checkpoints,
5. domain-truth preservation.

## Acceptance Criteria

1. Lotus has a documented workflow-pack model with explicit ownership, evidence, lifecycle, and
   review posture.
2. `lotus-ai` exposes a bounded runtime capable of executing workflow packs with durable async and
   audit support.
3. at least one gateway-owned product workflow is implemented through the pack model,
4. at least one domain-owned workflow is implemented through the pack model,
5. Workbench exposes shared lifecycle, provenance, review, and feedback primitives for pack-backed
   flows,
6. documentation clearly states what Lotus borrowed conceptually from OpenClaw and what Lotus
   explicitly refuses to adopt,
7. no implemented slice under this RFC grants AI workflow authority over approval, consent,
   execution, or source truth.

## Final Delivery Slice

Every implementation program under this RFC should end with a final slice dedicated to:

1. documentation updates,
2. agent-context and repository-context updates where implementation truth changed,
3. wiki-source updates where operator or onboarding guidance changed,
4. skill updates where implementation changed durable agent workflow guidance or delivery posture,
5. branch hygiene, truthful PR evidence, and cleanup.

That final slice is required because this RFC changes platform operating posture, not just code.

## Open Questions

1. should pack feedback be stored only in `lotus-ai`, or also surfaced in gateway/workbench-owned
   operator analytics contracts?
2. should the first operator-facing pack family live in `lotus-platform`, `lotus-ai`, or the
   owning service repo where the source evidence is assembled?
3. at what point should AGENTS and runtime-validation guidance be extended to require explicit
   AI-provenance validation for pack-backed front-office surfaces?

## Approval Request

Approve this RFC if Lotus should:

1. keep its current banking-grade AI governance posture,
2. adopt a workflow-pack model for reusable AI-assisted flows,
3. extend `lotus-ai` into a bounded runtime for pack execution and lifecycle management,
4. improve Lotus product and operator usefulness by borrowing the right runtime ideas from OpenClaw
   without importing OpenClaw's weaker trust model.
