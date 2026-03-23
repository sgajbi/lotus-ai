# RFC-0009: Runtime Safety Enforcement and Redaction Controls

- Status: Implemented
- Date: 2026-03-23
- Owners: lotus-ai
- Requires Approval From: lotus-ai maintainers

## Summary

`lotus-ai` should move safety posture from partly documented guidance to explicit runtime enforcement, with bounded redaction controls, reviewable safety evidence, and truthful operator/runtime reporting.

RFC-0003 established the controlled live-provider backbone.
RFC-0004 and RFC-0005 hardened and durably persisted provider operations.
RFC-0008 is the governed live retrieval activation sequence.

After retrieval and provider runtime capabilities are real, the highest-value remaining enterprise gap is that key safety controls are still documented rather than enforced.

## Why This Is Next

The platform now has:

1. controlled live-provider execution,
2. durable provider-operations controls,
3. durable async and evaluation execution,
4. runtime-backed rollout evidence,
5. governed retrieval indexing and a planned live-search activation path.

But safety posture still has a hard limit:

1. [safety_policy.py](C:/Users/Sandeep/projects/lotus-ai/src/app/services/safety_policy.py#L1) marks `runtime_redaction_engine` as `DOCUMENTED`,
2. [safety_runtime.py](C:/Users/Sandeep/projects/lotus-ai/src/app/services/safety_runtime.py#L1) only records static control metadata rather than enforcing redaction,
3. [safety_status.py](C:/Users/Sandeep/projects/lotus-ai/src/app/services/safety_status.py#L1) reports `runtime_redaction_active=False`,
4. the runbooks and runtime status are honest, but the platform still relies on calling applications to do too much of the last-mile safety work.

Once live provider and retrieval paths are materially useful, this becomes the next highest-risk and highest-value gap to close.

## Problem Statement

`lotus-ai` already enforces:

1. response labeling,
2. correlation and audit retention,
3. bounded task contracts,
4. governed provider and retrieval rollout posture.

What it does not yet enforce at runtime is equally important:

1. role-aware redaction,
2. structured output minimization beyond caller discipline,
3. consistent safety treatment across retrieval-backed and provider-backed outputs,
4. runtime-blocking behavior for safety-policy violations.

This creates a platform mismatch:

1. operators can inspect safety posture, but the strongest safety control is still documentary,
2. provider and retrieval runtime capabilities are becoming more real than the redaction posture around them,
3. audit records preserve evidence of what happened, but not yet a strong enforced redaction decision model,
4. downstream apps still need to assume too much responsibility for sensitive-field handling.

## Goals

1. Introduce explicit runtime redaction enforcement for bounded task outputs.
2. Make safety enforcement policy-driven, typed, and inspectable.
3. Preserve truthful audit and evidence about what safety controls actually ran.
4. Keep redaction behavior conservative, reviewable, and deterministic.
5. Make safety runtime, runbook, evidence, and governance surfaces reflect actual enforced posture.

## Non-Goals

1. Free-form content moderation across arbitrary user text.
2. Replacing caller-side domain authorization with generic AI-layer policy.
3. Building an unbounded policy engine unrelated to the existing task/output-label model.
4. Hiding redaction decisions behind opaque model behavior.
5. Broad PII discovery beyond the bounded Lotus task and output contracts.

## Current State

Today the safety layer is intentionally modest but incomplete:

1. output-label posture is explicit,
2. intended-use notes and redaction posture are exposed per task,
3. enforced controls are limited to response labeling and correlation/audit,
4. runtime redaction remains documented-only.

This is acceptable in a foundation phase, but no longer a sufficient end state if:

1. provider-backed outputs become live,
2. retrieval-backed tasks become genuinely useful,
3. Lotus applications start depending on `lotus-ai` as a shared enterprise runtime instead of a narrowly governed scaffold.

## Decision

`lotus-ai` will implement explicit runtime safety enforcement and redaction controls on top of the existing task, output-label, audit, and governance seams.

The first production-capable safety runtime should:

1. enforce deterministic redaction and minimization for bounded output classes,
2. record which safety controls executed and what action they took,
3. fail conservatively when safety policy cannot be applied confidently,
4. preserve reviewable operator and audit visibility into safety outcomes,
5. keep all safety behavior bounded by existing task and contract semantics rather than introducing a broad generic policy system.

## First Implementation Scope

The first runtime-enforced safety release under this RFC is intentionally narrow.

Included in scope:

1. bounded Lotus task outputs only,
2. deterministic treatment of structured output payloads and result previews,
3. shared safety enforcement for both provider-backed and retrieval-backed task execution paths,
4. typed blocked and degraded outcomes when required safety controls cannot be applied.

Explicitly out of scope for this RFC:

1. generic moderation of arbitrary free-form user text,
2. model-generated or heuristic redaction behavior,
3. prompt rollout or prompt mutation controls,
4. broad caller-authorization policy beyond the existing bounded task/output contract model.

## State Model and Invariants

This RFC establishes the following invariants:

1. safety runtime status must not claim enforcement for controls that remain documentary,
2. redaction enforcement must be derived from task and output-label policy, not ad hoc caller hints,
3. audit and execution evidence must show the actual enforced safety controls per execution,
4. redaction decisions must be deterministic and reviewable,
5. failure to apply required safety controls must block or conservatively degrade the affected execution path,
6. retrieval-backed and provider-backed outputs must not diverge silently in safety posture when they share the same output-label contract.
7. required safety enforcement must happen before task response mapping and audit persistence, so emitted payloads, audit records, and execution evidence describe the same post-safety result.
8. documented-only posture must never be presented as runtime enforcement in policy, runtime status, audit, governance, or evaluation surfaces.

## Architecture Direction

### Safety Policy and Control Model

The existing safety-policy surface should remain the contract anchor, but it must gain real runtime meaning.

Required behavior:

1. control descriptors distinguish documented versus enforced behavior truthfully,
2. task-level redaction posture maps to explicit runtime control decisions,
3. policy remains bounded by task category and output label,
4. runtime safety outcomes use typed control results rather than generic prose,
5. safety policy resolution and safety enforcement execution remain separate seams so future control additions do not overload one helper.

### Runtime Redaction Engine

Introduce a bounded redaction engine for the actual task result payloads that `lotus-ai` emits.

Required behavior:

1. apply deterministic redaction/minimization to structured outputs and result previews,
2. preserve non-sensitive provenance and audit usefulness where possible,
3. keep behavior explainable from the policy and output-label model,
4. avoid opaque or model-driven redaction logic,
5. treat inability to apply a required safety rule as a blocked or degraded runtime condition rather than silently returning unredacted data.

### Audit and Evidence Convergence

Safety evidence must be first-class runtime truth.

Required behavior:

1. audit records preserve enforced safety-control ids and outcome details,
2. task execution evidence distinguishes documented-only posture from runtime-enforced posture,
3. operator summaries and governance surfaces can see whether redaction actually ran,
4. safety failures and degraded behavior are reviewable after the fact,
5. request-level task responses, stored audit records, and evidence descriptors all reflect the same post-safety payload posture.

### Runbook and Approval Convergence

If safety enforcement becomes runtime-critical, it needs the same operational discipline as providers and retrieval.

Required behavior:

1. safety runbook readiness must cover activation, rollback, degraded behavior, and incident review,
2. evidence readiness must include runtime-backed safety evaluation coverage,
3. governance status must block rollout if safety enforcement is stale, partial, or failing,
4. platform runtime status must summarize actual safety enforcement posture honestly,
5. prompt rollout remains out of scope and must not be coupled into this RFC's activation path.

## Data and Operational Requirements

1. Safety enforcement must survive restart.
2. Safety-control outcomes must be auditable and inspectable.
3. Redaction behavior must be deterministic for the same policy and payload shape.
4. Runtime status, audit evidence, and actual behavior must agree.
5. Required safety controls must fail conservatively when they cannot be applied.
6. Redaction must preserve enough structure for operator review without leaking sensitive material.
7. SQL-backed tests must prove safety outcomes and persistence paths.
8. Rollback and degraded-mode procedures must be documented before activation is treated as ready.
9. Public API contracts must prove the enforced-vs-documented safety distinction at the route level, not only in unit seams.
10. Any state introduced for safety enforcement must either be restart-safe or be explicitly documented as stateless with durability provided by audit and evaluation evidence.

## Delivery Slices

### Slice 1: Typed Safety Outcome and Enforcement Seam

Outcome:

1. safety runtime gains an explicit enforcement seam rather than only descriptive metadata,
2. safety outcomes are typed and can represent enforced, documented-only, blocked, and degraded posture,
3. no broad behavior change yet.

Acceptance gate:

1. contracts and service seams are explicit,
2. unit tests cover policy-to-enforcement mapping,
3. runtime status remains truthful about what is and is not active,
4. no hidden redaction behavior is introduced,
5. task, audit, and OpenAPI contracts prove the broadened safety shape without changing emitted task payloads yet.

### Slice 2: Deterministic Redaction for Bounded Outputs

Outcome:

1. bounded task outputs run through deterministic redaction/minimization,
2. enforced safety controls now affect actual response payloads and previews,
3. failure semantics are conservative.

Acceptance gate:

1. redaction runs on real task execution paths,
2. result preview and audit payload handling remain consistent,
3. meaningful tests cover safe pass-through, required redaction, and blocked/degraded cases,
4. runtime status reports active redaction truthfully,
5. integration tests prove provider-backed and retrieval-backed tasks both traverse the same enforcement seam.

### Slice 3: Audit and Task-Evidence Convergence

Outcome:

1. audit records preserve actual safety outcomes,
2. task evidence and summaries expose runtime-enforced safety posture,
3. operator inspection can distinguish documented-only history from enforced history.

Acceptance gate:

1. audit evidence is explicit and reviewable,
2. task execution summaries reflect real safety behavior,
3. integration tests cover safety evidence in task and audit APIs,
4. no silent mismatch exists between runtime behavior and persisted evidence,
5. SQL-backed audit persistence proves enforced-redaction and blocked/degraded outcomes survive round-trip storage.

### Slice 4: Safety Evaluation and Governance Upgrade

Outcome:

1. runtime-backed evaluation families validate safety enforcement behavior,
2. evidence, runbook, and governance surfaces consume that runtime-backed truth,
3. stale or failing safety evidence blocks approval posture explicitly.

Acceptance gate:

1. evaluation execution covers enforced safety behavior,
2. governance distinguishes staged-only, partial, pass, fail, and stale safety posture,
3. operator-facing readiness and governance summaries are aligned,
4. runtime-backed evidence becomes the source of truth for safety rollout review,
5. policy-only staged fixtures no longer masquerade as rollout-ready safety approval evidence.

### Slice 5: Runbook and Operational Hardening

Outcome:

1. safety activation, rollback, degraded-mode, and incident-response procedures are documented,
2. platform runtime status summarizes actual safety enforcement posture,
3. restart-survival and failure recovery are covered by meaningful tests.

Acceptance gate:

1. runbooks match implementation reality,
2. degraded and blocked safety posture is surfaced truthfully,
3. SQL-backed tests prove persistence and restart behavior where relevant,
4. the platform is materially closer to enterprise-grade runtime safety enforcement,
5. the RFC explicitly documents whether safety enforcement is stateless or introduces restart-sensitive state.

## Risks

1. over-broad redaction could make outputs unusable,
2. under-scoped redaction could create false confidence,
3. weak audit evidence could hide safety regressions,
4. introducing generic policy machinery could add complexity without improving the bounded Lotus use cases.

## Alternatives Considered

### Alternative 1: Prompt Activation Before Safety Enforcement

Rejected as the next highest-value RFC.

Reason:

1. prompt activation matters, but it does not reduce platform risk as directly as real safety enforcement,
2. once provider and retrieval behavior are live, documented-only redaction is the more serious gap.

### Alternative 2: Broader Model Orchestration

Rejected.

Reason:

1. orchestration without stronger runtime safety would widen capability before hardening the control plane,
2. the platform still needs to enforce its bounded safety contract more concretely.

### Alternative 3: Leave Safety Fully to Downstream Apps

Rejected.

Reason:

1. that would undermine the point of `lotus-ai` as a shared governed platform,
2. shared provider, retrieval, and task execution should carry shared safety enforcement where the output contract is already centralized.

## Acceptance Criteria

This RFC is complete when:

1. runtime safety enforcement exists for bounded task outputs,
2. redaction and minimization behavior are deterministic and reviewable,
3. audit and execution evidence reflect actual enforced safety controls,
4. runtime, evidence, runbook, and governance surfaces describe the same safety reality,
5. documented-only safety posture can no longer masquerade as enforced protection,
6. the platform is materially closer to enterprise-grade shared AI runtime safety.

## Implementation Notes

This RFC is implemented on `main`.

Delivered scope:

1. typed safety execution outcomes now distinguish documented-only, enforced pass-through, enforced redacted, blocked, and degraded execution posture,
2. deterministic runtime safety enforcement now applies bounded minimization rules to structured outputs and result previews for the initial enforced output classes,
3. blocked and degraded runtime safety outcomes now remain visible and aligned across task responses, audit records, and execution evidence,
4. runtime-backed safety evaluation fixtures and approval-gate summaries now govern safety evidence posture rather than relying on staged policy-only continuity records,
5. safety runbook readiness, safety governance status, and platform runtime status now converge on one explicit runtime, runbook, and evidence model,
6. safety enforcement remains intentionally stateless, with durability living in persisted audit records, execution evidence, and runtime-backed evaluation runs rather than a separate mutable safety store.

Follow-on work is intentionally left to later RFCs:

1. broader prompt rollout and approval logic remains in RFC-0010,
2. dedicated observability packs and named on-call approval remain broader operational maturity work rather than a blocker to the bounded runtime-safety slice delivered here.

## Approval Requested

Approve this RFC if the team agrees that:

1. safety runtime enforcement is the next highest-value control-plane gap after live retrieval activation,
2. redaction and minimization should be enforced centrally for bounded Lotus AI outputs,
3. safety rollout should reuse the same evidence, governance, and runbook discipline already applied to providers, retrieval, and evaluation,
4. delivery should proceed in the slices defined above.
