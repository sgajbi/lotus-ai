# RFC-0010: Governed Prompt Activation and Rollback

- Status: Draft
- Date: 2026-03-23
- Owners: lotus-ai
- Requires Approval From: lotus-ai maintainers

## Summary

`lotus-ai` should move prompt management from repository-only activation to a governed live prompt activation and rollback model, with durable promotion state, reviewable rollback controls, and runtime-backed evidence for prompt change approval.

RFC-0001 established the prompt registry and governance foundation.
RFC-0007 made evaluation execution and approval-gate posture runtime-backed.
RFC-0009 is the runtime safety enforcement sequence that hardens output control posture.

After provider, retrieval, evaluation, and safety runtime work are real, the next high-value control-plane gap is that prompt change management is still operationally frozen.

## Why This Is Next

The platform already has:

1. durable prompt definitions,
2. explicit prompt runtime selection surfaces,
3. governance, runbook, and evidence readiness endpoints for prompt rollout,
4. runtime-backed evaluation infrastructure suitable for prompt regression evidence,
5. audit and task execution seams that already record prompt-version selection.

But prompt activation is still intentionally blocked:

1. [prompt_governance.py](C:/Users/Sandeep/projects/lotus-ai/src/app/services/prompt_governance.py#L1) reports `runtime_mutation_enabled=False` and `promotion_write_api_enabled=False`,
2. [prompt_activation_readiness.py](C:/Users/Sandeep/projects/lotus-ai/src/app/services/prompt_activation_readiness.py#L1) explicitly says no live approval and rollback workflow exists,
3. [prompt_runbook_readiness.py](C:/Users/Sandeep/projects/lotus-ai/src/app/services/prompt_runbook_readiness.py#L1) shows change review and rollback still not ready,
4. [prompt_evidence_readiness.py](C:/Users/Sandeep/projects/lotus-ai/src/app/services/prompt_evidence_readiness.py#L1) shows no runtime-backed regression or rollback evidence pack yet.

That means the platform can execute with fixed prompts, but cannot yet govern prompt evolution as a first-class enterprise runtime capability.

## Problem Statement

Today prompt behavior is durable but static:

1. prompt definitions are persisted and selected at runtime,
2. prompt versioning is visible in runtime selection and audit traces,
3. but all prompt activation is still done through reviewed repository changes and migrations,
4. there is no bounded live promotion or rollback path.

This creates a material limitation:

1. prompt regressions cannot be rolled back through the platform itself,
2. runtime-backed evaluation evidence cannot yet serve as a real prompt-approval gate,
3. prompt operations are less mature than provider, retrieval, and evaluation operations,
4. Lotus teams cannot treat prompt evolution as a governed runtime control-plane action.

## Goals

1. Introduce a governed live prompt promotion and rollback model.
2. Make prompt activation state durable, reviewable, and auditable.
3. Reuse runtime-backed evaluation evidence for prompt approval gates.
4. Keep prompt runtime selection truthful during transition.
5. Preserve conservative rollback and failure semantics.

## Non-Goals

1. Free-form prompt editing from arbitrary callers.
2. Broad experimentation tooling outside governed prompt candidates.
3. Replacing task contracts or output-label policy through prompt changes.
4. Allowing prompt mutation without review, approval, and evidence gates.
5. Building a general-purpose prompt IDE inside `lotus-ai`.

## Current State

The prompt layer is structurally strong:

1. prompt definitions are durable,
2. prompt lifecycle and runtime selection are inspectable,
3. task execution and audit already record prompt-version selection,
4. prompt governance surfaces already exist.

What is missing is the actual runtime control plane:

1. no promotion state beyond static active/retired definitions,
2. no reviewable activation action surface,
3. no rollback action model,
4. no runtime-backed prompt approval evidence attached to a real promotion workflow.

## Decision

`lotus-ai` will implement governed prompt activation and rollback as the next prompt-control-plane milestone.

The first production-capable prompt rollout path should:

1. allow only bounded, approved prompt candidates,
2. persist explicit promotion state separate from the prompt body itself,
3. expose reviewable promote and rollback actions with operator metadata,
4. require runtime-backed evaluation evidence before activation,
5. preserve current prompt selection truthfully while rollout remains inactive or partial.

## State Model and Invariants

This RFC establishes the following invariants:

1. prompt runtime selection must always resolve to one authoritative active prompt per task,
2. prompt activation state must be durable and reviewable,
3. prompt rollback must restore a prior known-good runtime selection explicitly,
4. audit records must show the actual selected prompt version after activation or rollback,
5. prompt approval posture must not claim readiness from staged-only evidence,
6. prompt promotion must never silently bypass evaluation or approval requirements.

## Architecture Direction

### Prompt Promotion State

Add an explicit prompt rollout state model separate from prompt definition persistence.

Required behavior:

1. prompt definitions remain durable records,
2. promotion state captures candidate, active, rolled-back, and retired posture,
3. runtime selection resolves through the same authoritative state model,
4. prior active prompt lineage remains reviewable for rollback.

### Prompt Control-Plane Actions

Introduce bounded prompt control actions for promotion and rollback.

Required behavior:

1. promotion and rollback are explicit operator actions,
2. actions carry requested-by, approved-by, reason, and timestamp metadata,
3. rollback restores prior active posture explicitly rather than editing history in place,
4. action history is inspectable through platform APIs.

### Evidence and Evaluation Convergence

Prompt activation should consume the runtime-backed evaluation system rather than inventing parallel approval logic.

Required behavior:

1. prompt candidate approval depends on runtime-backed regression evidence,
2. evidence surfaces distinguish staged-only from runtime-backed prompt evidence,
3. stale or failing prompt evidence blocks activation,
4. rollback evidence must prove restoration of prior runtime behavior.

### Runtime and Audit Convergence

Prompt runtime, task execution, and audit surfaces must all agree.

Required behavior:

1. prompt runtime status reflects actual active and candidate posture,
2. task execution continues to record the selected prompt version truthfully,
3. audit views can explain prompt changes over time,
4. platform runtime status can summarize prompt rollout posture without ambiguity.

## Data and Operational Requirements

1. Prompt promotion state must survive restart.
2. Promotion and rollback actions must be durable and inspectable.
3. Runtime selection must remain deterministic under promotion or rollback.
4. Approval state must derive from runtime-backed evidence, not only documentation.
5. Rollback must fail conservatively if a prior known-good state is unavailable.
6. SQL-backed tests must prove promotion and rollback behavior.
7. Runbooks must define normal promotion, emergency rollback, and incident review procedures.

## Delivery Slices

### Slice 1: Durable Prompt Promotion State and Repository Seam

Outcome:

1. prompt rollout state becomes explicit and durable,
2. repository and service seams exist for activation-state management,
3. public activation behavior remains unchanged.

Acceptance gate:

1. schema is migration-managed,
2. repository contracts are unit-tested,
3. runtime selection still resolves through one authoritative active prompt,
4. existing prompt APIs remain truthful.

### Slice 2: Prompt Promotion and Rollback Action Surface

Outcome:

1. bounded prompt promote and rollback actions exist,
2. action history is durable and reviewable,
3. runtime selection updates through explicit control-plane actions.

Acceptance gate:

1. promotion and rollback are auditable,
2. rollback restores prior active state explicitly,
3. unauthorized or invalid transitions fail conservatively,
4. integration tests cover control-plane behavior.

### Slice 3: Prompt Runtime and Audit Convergence

Outcome:

1. runtime status reflects candidate, active, and rollback posture,
2. task and audit evidence align with actual selected prompt versions,
3. operator views can trace prompt change history cleanly.

Acceptance gate:

1. runtime, task, and audit surfaces agree,
2. rollback history is visible,
3. no silent drift exists between selection state and audit evidence,
4. meaningful tests cover end-to-end prompt selection transitions.

### Slice 4: Evaluation and Approval-Gate Upgrade

Outcome:

1. prompt rollout consumes runtime-backed evaluation evidence,
2. evidence and governance surfaces expose prompt approval posture explicitly,
3. stale or failing prompt evidence blocks activation.

Acceptance gate:

1. prompt evidence is runtime-backed,
2. governance distinguishes staged-only, partial, pass, fail, and stale posture,
3. prompt activation cannot bypass evidence gates,
4. rollout truth materially improves.

### Slice 5: Runbook and Operational Hardening

Outcome:

1. prompt promotion, rollback, incident response, and audit-review procedures are documented,
2. platform runtime status summarizes prompt rollout posture honestly,
3. restart-survival and rollback recovery are covered by meaningful tests.

Acceptance gate:

1. runbooks match implementation reality,
2. degraded or blocked prompt posture is visible,
3. SQL-backed tests prove persistence and restart behavior,
4. the platform is materially closer to enterprise-grade prompt governance.

## Risks

1. weak rollback semantics could make prompt operations less trustworthy than repository-only changes,
2. over-broad prompt mutation could erode bounded task behavior,
3. poor evidence gating could allow unproven prompts into runtime,
4. too much prompt-management complexity could outrun the actual needs of the platform.

## Alternatives Considered

### Alternative 1: Leave Prompt Changes Repository-Only Longer

Rejected as the next high-value prompt step.

Reason:

1. the platform already has the surrounding governance and evaluation infrastructure,
2. static prompt change management is now the main prompt-control-plane bottleneck.

### Alternative 2: Broader Multi-Prompt Experimentation Before Rollout Controls

Rejected.

Reason:

1. it widens experimentation before approval and rollback discipline is in place,
2. the platform needs governed rollout, not a larger prompt playground.

### Alternative 3: Push Prompt Rollout Responsibility Fully to Downstream Apps

Rejected.

Reason:

1. prompt selection and versioning already live in `lotus-ai`,
2. keeping rollout outside the platform would weaken auditability and control-plane coherence.

## Acceptance Criteria

This RFC is complete when:

1. prompt promotion state is durable and reviewable,
2. bounded prompt promote and rollback actions exist,
3. runtime selection, task execution, and audit traces remain aligned,
4. prompt approval posture is backed by runtime evaluation evidence,
5. stale or staged-only evidence cannot silently satisfy live prompt activation,
6. the platform is materially closer to enterprise-grade prompt governance and rollback discipline.

## Approval Requested

Approve this RFC if the team agrees that:

1. prompt activation and rollback is the next highest-value control-plane gap after retrieval and safety runtime work,
2. prompt rollout should become a governed runtime capability rather than remain repository-only,
3. runtime-backed evaluation evidence should gate prompt activation,
4. delivery should proceed in the slices defined above.
