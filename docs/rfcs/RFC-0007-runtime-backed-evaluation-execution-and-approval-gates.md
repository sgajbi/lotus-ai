# RFC-0007: Runtime-Backed Evaluation Execution and Approval Gates

- Status: Implemented
- Date: 2026-03-23
- Owners: lotus-ai
- Requires Approval From: lotus-ai maintainers

## Summary

`lotus-ai` should replace the current read-only evaluation-run artifact facade with runtime-backed evaluation execution, persisted results, and explicit approval-gating posture for governed platform rollout.

RFC-0001 established the evaluation contracts and fixture-governance posture.
RFC-0002, RFC-0004, and RFC-0005 expanded the fixture inventory and recorded baseline evidence.
RFC-0006 is the durable async backbone that makes bank-grade background execution possible.

The next high-value step after that backbone is to make evaluation execution itself real.

## Why This Is Next

The platform now has:

1. real retrieval execution,
2. a controlled live-provider backbone,
3. durable provider operations state,
4. strong fixture and run-artifact governance,
5. a planned durable async backbone for long-running work.

The biggest remaining trust gap is that evaluation evidence is still mostly staged and recorded by governed files rather than produced by an authoritative runtime execution path.

Without runtime-backed evaluation execution:

1. provider and retrieval rollout evidence remains partly documentary,
2. recorded evaluation history cannot be retried or reproduced through the platform itself,
3. approval decisions still depend on manually curated run artifacts,
4. the service lacks a first-class quality gate that is as real as its runtime behavior.

## Problem Statement

Today evaluation posture is still largely documentation-backed:

1. run catalogs and detail views are loaded from static governed artifacts in [eval_run_service.py](C:/Users/Sandeep/projects/lotus-ai/src/app/services/eval_run_service.py#L1),
2. recorded runs come from manifest files in [run_registry.py](C:/Users/Sandeep/projects/lotus-ai/src/app/evals/run_registry.py#L1),
3. evaluation runtime status explicitly says no live runner is active in [eval_status.py](C:/Users/Sandeep/projects/lotus-ai/src/app/services/eval_status.py#L1),
4. rollout evidence for retrieval and provider governance is therefore stronger than foundation scaffolding, but weaker than authoritative runtime truth.

This creates real limitations:

1. evaluation runs are inspectable but not executable through the service,
2. recorded pass or fail posture is not tied to runtime-backed attempt history,
3. operators cannot trigger bounded re-runs or inspect execution evidence through one durable control plane,
4. approval readiness for retrieval and provider rollout still relies on staged artifacts more than runtime-produced evidence.

## Goals

1. Introduce durable runtime-backed evaluation run persistence.
2. Enable governed async execution for explicitly allowlisted evaluation families.
3. Persist run attempts, case results, summary verdicts, and evidence references.
4. Make evaluation runtime, run detail, and governance surfaces report authoritative live state.
5. Add explicit approval-gating summaries for rollout domains such as retrieval and provider execution.

## Non-Goals

1. Free-form experimentation or notebook-style evaluation authoring.
2. Broad benchmark infrastructure outside governed Lotus evaluation families.
3. Automatic deployment blocking outside the existing governance model.
4. Replacing fixture-manifest governance with ad hoc runtime inputs.
5. Building a generic ML experiment platform.

## Current State

Today `lotus-ai` already has:

1. governed fixture manifests,
2. governed recorded run artifacts,
3. seam coverage summaries,
4. rollout evidence readiness surfaces for retrieval and provider execution,
5. a planned durable async backbone that is the right home for bounded evaluation work.

Those surfaces should remain, but the runtime underneath them should become authoritative for allowlisted evaluation execution.

## Decision

`lotus-ai` will implement runtime-backed evaluation execution on top of the durable async backbone from RFC-0006.

The first version should:

1. persist evaluation run submissions, attempts, and case-level outcomes,
2. execute bounded allowlisted evaluation families through the async runtime,
3. record explicit run verdicts and evidence references,
4. expose approval-gating summaries that distinguish staged documentary evidence from runtime-produced evidence,
5. preserve existing fixture-manifest governance as the source of allowed evaluation inputs.

The focus is not on widening evaluation APIs unnecessarily. The focus is on making evaluation evidence runtime-produced, reviewable, and reusable for rollout governance.

## State Model and Invariants

This RFC establishes one authoritative rule:

1. runtime-backed evaluation truth must come from durable evaluation run state rather than static run-artifact files,
2. evaluation runtime summaries, run detail, and approval posture must derive from that same durable state,
3. fixture manifests remain the governed input inventory, but they must not masquerade as execution results,
4. historical file-backed baseline runs may remain visible only if clearly labeled as staged or historical.

The runtime-backed evaluation model should preserve these invariants:

1. each submitted evaluation run must create one authoritative persisted run record,
2. case results must remain attributable to the exact fixture family and manifest version used at execution time,
3. run verdicts must be explainable from persisted case outcomes rather than handwritten notes,
4. rerun, replay, or retry actions must produce explicit new attempt history,
5. approval summaries must distinguish runtime-produced evidence from staged documentary baselines,
6. no rollout domain should appear approved only because a stale recorded artifact still exists.

## Architecture Direction

### Evaluation Runtime Persistence

Add migration-managed persistence for:

1. evaluation runs,
2. evaluation run attempts,
3. case-level outcomes or result summaries,
4. explicit verdict and evidence-reference fields needed for rollout review.

The persistence model should remain evaluation-specific rather than hidden in generic opaque blobs.

### Repository and Service Boundaries

Introduce an evaluation runtime repository seam so:

1. run catalog and detail no longer depend only on file-backed artifacts,
2. runtime-backed submissions and retries can be tested directly,
3. verdict assembly is not spread ad hoc across routers and services,
4. approval-gating summaries can reuse one authoritative persistence path.

### Async Execution Integration

Evaluation execution should reuse RFC-0006 rather than inventing its own worker path.

Required semantics:

1. allowlisted evaluation job types submit through the durable async runtime,
2. worker execution records attempt history and bounded progress truthfully,
3. evaluation retries and replays remain explicit async control actions,
4. no second queue or process-local runner is introduced just for evaluation work.

### Approval-Gating Surfaces

Add explicit evaluation-backed approval summaries for rollout domains such as:

1. retrieval execution,
2. provider execution,
3. future task or safety domains only if they consume the same durable evaluation runtime.

Those summaries should expose:

1. latest authoritative runtime-backed run id,
2. verdict posture,
3. covered seam or fixture family scope,
4. whether current approval posture is runtime-backed, staged-only, or stale.

### Compatibility and Historical Baselines

The migration from file-backed recorded runs to runtime-backed runs should avoid split-brain truth.

Required compatibility rules:

1. staged historical run artifacts may remain visible for continuity,
2. runtime-backed runs must be clearly distinguishable from historical artifact-only runs,
3. approval surfaces must prefer current runtime-backed evidence over historical artifacts,
4. no silent fallback from failed runtime execution to file-backed success is allowed.

## First-Class Evaluation Families

The first runtime-backed evaluation families should stay narrow and high-value:

1. retrieval citation and refusal behavior,
2. provider execution policy, runtime, failure-mode, and provider-operations behavior,
3. task-contract families only if they fit the same deterministic execution posture.

The first implementation should resist broad evaluation-family expansion until the execution backbone and verdict model are proven.

## Data and Operational Requirements

1. Runtime-backed evaluation runs must survive restart.
2. Run attempts, case outcomes, and verdicts must be durable and inspectable.
3. Historical artifact-backed baselines must remain clearly labeled.
4. Approval-gating summaries must be explainable from persisted runtime-backed evidence.
5. Repository unavailability must fail safely and truthfully rather than silently preserving stale approval posture.
6. Run state must not leak credentials or unrestricted raw provider payloads.
7. The database schema must be migration-managed and integration-tested.
8. Verdict wording must remain conservative and reviewable.
9. Retry or replay must not overwrite prior case evidence in place.
10. Approval state must distinguish:
    - no evidence
    - staged-only evidence
    - runtime-backed evidence
    - runtime-backed failure or stale evidence

## Delivery Slices

### Slice 1: Durable Evaluation Runtime Schema

Outcome:

1. migration-managed schema exists for runtime-backed evaluation runs, attempts, and case outcomes,
2. explicit repository contracts are introduced,
3. no public API behavior changes yet.

Acceptance gate:

1. schema is migration-managed,
2. repository contracts are unit-tested,
3. evaluation state entities are explicit rather than opaque blobs,
4. staged historical artifacts remain separate from runtime-backed records.

### Slice 2: Runtime-Backed Evaluation Submission and Catalog State

Outcome:

1. allowlisted evaluation families can be submitted into durable runtime state,
2. evaluation run catalogs and detail views report runtime-backed records,
3. historical artifact-backed runs remain visible only as clearly labeled baseline records.

Acceptance gate:

1. persisted submission creates authoritative run records,
2. restart does not erase queued or terminal run truth,
3. integration tests cover runtime-backed catalog and detail behavior,
4. unsupported evaluation families still fail truthfully.

### Slice 3: Async Worker Execution and Case Outcome Persistence

Outcome:

1. allowlisted evaluation runs execute through the durable async runtime,
2. case-level outcomes and summary verdicts are persisted,
3. retry and replay history remains explicit and reviewable.

Acceptance gate:

1. run attempts, case results, and verdicts survive restart,
2. worker execution remains truthful under retry and failure,
3. meaningful tests cover actual case execution behavior rather than shallow status assertions,
4. verdicts are derived from persisted outcomes rather than handwritten run notes.

### Slice 4: Approval-Gating and Governance Convergence

Outcome:

1. rollout domains such as retrieval and provider execution expose approval-gating summaries backed by runtime evaluation evidence,
2. evidence readiness and governance surfaces distinguish staged-only from runtime-backed evidence,
3. stale or failed evaluation posture is explicit.

Acceptance gate:

1. governance summaries prefer current runtime-backed evidence,
2. stale historical artifacts cannot silently satisfy approval posture,
3. operator views distinguish pass, fail, stale, and staged-only evidence,
4. the change materially improves rollout-review truth.

### Slice 5: Runbook, Eval Asset, and Runtime Convergence

Outcome:

1. runbooks describe runtime-backed evaluation execution, retry, and approval review,
2. eval assets and recorded baselines remain aligned with implementation reality,
3. platform runtime and evaluation summaries truthfully describe the new execution posture.

Acceptance gate:

1. runbooks and governance docs match implementation reality,
2. runtime-backed evaluation execution is reviewable end to end,
3. restart-survival and replay scenarios are covered by meaningful tests,
4. the platform is materially closer to bank-grade rollout evidence.

## Risks

1. overly broad evaluation execution could turn the service into a generic experiment runner,
2. poor verdict modeling could make approval posture less trustworthy instead of more trustworthy,
3. split-brain handling between historical artifacts and runtime-backed runs could confuse operators,
4. excessive per-case persistence could add avoidable complexity if not kept bounded.

## Alternatives Considered

### Alternative 1: Keep Evaluation as a Recorded Artifact Surface Longer

Rejected as the next phase after RFC-0006.

Reason:

1. the platform already has enough runtime capability that evaluation truth should become real,
2. rollout governance now needs runtime-backed evidence more than more staged artifacts.

### Alternative 2: Expand Async Job Types First Without Evaluation Verdicts

Rejected for now.

Reason:

1. that would grow async breadth before demonstrating its value on one high-signal consumer,
2. evaluation execution is the clearest trust-building consumer of RFC-0006.

### Alternative 3: Build a Standalone Evaluation Service

Rejected for the current phase.

Reason:

1. `lotus-ai` already owns the relevant task, retrieval, provider, and governance seams,
2. splitting evaluation out now would weaken traceability instead of improving it.

## Acceptance Criteria

This RFC is complete when:

1. runtime-backed evaluation runs are durable,
2. allowlisted evaluation execution runs through the authoritative async backbone,
3. case outcomes and verdicts are durable and reviewable,
4. evaluation catalogs and detail views distinguish runtime-backed runs from historical artifact baselines,
5. rollout approval-gating surfaces reflect runtime-backed evidence truthfully,
6. stale or staged-only evidence cannot silently satisfy current approval posture,
7. runbooks and governance assets reflect the runtime-backed evaluation model,
8. the platform is materially closer to bank-grade rollout evidence and approval discipline.

## Implementation Notes

Implemented on `codex/rfc-runtime-eval-execution-gates`.

Delivered outcomes:

1. durable evaluation runtime state now exists for runs, attempts, and per-case outcomes,
2. allowlisted evaluation families can be submitted and executed through the authoritative async backbone,
3. evaluation run detail now exposes persisted attempt history and replay-safe case-result history,
4. provider and retrieval governance surfaces now consume explicit runtime-backed approval-gate summaries instead of relying on staged baselines alone,
5. async replay, requeue, abandon, and lease-expiry recovery now preserve matching evaluation attempt truth rather than updating only async job state,
6. evaluation runtime status, runbooks, and historical baseline wording now describe staged continuity records versus current runtime-backed approval posture explicitly.

The implemented result is:

1. runtime-backed evaluation evidence is now durable, replayable, and reviewable through platform APIs,
2. retrieval and provider rollout review can distinguish staged-only, partial runtime, passing runtime, failing runtime, and stale runtime evaluation posture,
3. historical `foundation_eval_*` artifacts remain visible for continuity but no longer masquerade as current approval proof,
4. the platform is materially closer to bank-grade rollout evidence and approval discipline than the artifact-only posture that existed before RFC-0007.

## Approval Requested

Approve this RFC if the team agrees that:

1. runtime-backed evaluation execution is the next highest-value consumer of the durable async backbone from RFC-0006,
2. the first evaluation execution state store should be the service database,
3. delivery should proceed in the slices defined above,
4. rollout-approval truth should come from runtime-backed evaluation evidence rather than only staged recorded artifacts.
