# RFC-0008: Governed Live Retrieval Activation

- Status: Draft
- Date: 2026-03-23
- Owners: lotus-ai
- Requires Approval From: lotus-ai maintainers

## Summary

`lotus-ai` should activate real live retrieval search on top of the retrieval indexing, async execution, provider operations, and runtime-backed evaluation foundations that now exist.

RFC-0002 established the real retrieval backbone and durable indexing model.
RFC-0005 made provider operations state durable.
RFC-0006 made async execution durable.
RFC-0007 made evaluation evidence runtime-backed and approval-gate aware.

The next highest-value step is to stop treating retrieval search as catalog-only or disabled once configuration says retrieval is enabled.

## Why This Is Next

The platform now has:

1. durable retrieval metadata, chunk, and indexing state,
2. async runtime support for retrieval indexing execution,
3. controlled provider execution with durable operational guardrails,
4. runtime-backed evaluation execution and approval-gate posture,
5. explicit retrieval governance, evidence, and runbook surfaces.

The main remaining runtime gap is that live retrieval search is still not wired:

1. `retrieval_mode=enabled` still returns a `503` because no live search backend is connected,
2. runtime-backed indexing produces durable state but not an actually usable live search path,
3. `knowledge_search.v1` and `knowledge_answer.v1` remain limited by catalog-only search semantics,
4. retrieval rollout governance is stronger than the actual retrieval product behavior it is supposed to govern.

## Problem Statement

Today the retrieval layer has an asymmetry:

1. indexing is runtime-backed and durable,
2. governance and evaluation evidence are runtime-backed,
3. source and document promotion posture are explicit,
4. but live retrieval search itself is still disabled.

Current code makes that gap explicit:

1. [retrieval_execution_status.py](C:/Users/Sandeep/projects/lotus-ai/src/app/services/retrieval_execution_status.py#L1) reports `live_search_enabled=False` even when retrieval mode is enabled,
2. [retrieval_gateway.py](C:/Users/Sandeep/projects/lotus-ai/src/app/services/retrieval_gateway.py#L1) returns catalog-only hits when retrieval is disabled and a `503` when retrieval is enabled because no live backend is wired,
3. retrieval activation and runbook surfaces therefore describe a rollout target that the service still cannot actually execute.

This leaves `lotus-ai` short of the runtime behavior a shared AI platform needs:

1. governed knowledge search is still weaker than the indexing and governance machinery around it,
2. evaluation-backed rollout evidence cannot yet approve a real retrieval search path,
3. provider-backed answer generation remains artificially bounded by a non-live search backend,
4. downstream Lotus applications still cannot depend on `lotus-ai` for actual live governed search.

## Goals

1. Activate a real live retrieval search path over promoted indexed content.
2. Keep live retrieval behavior bounded, reviewable, and corpus-governed.
3. Preserve explicit source and document promotion controls.
4. Reuse the existing durable async indexing and evaluation approval-gate infrastructure.
5. Make retrieval runtime, governance, and task execution surfaces reflect actual live-search truth.

## Non-Goals

1. Broad web search or open-ended external search.
2. Replacing governed source and document promotion with implicit corpus activation.
3. Free-form semantic ranking experiments outside bounded Lotus retrieval behavior.
4. Reworking the public retrieval API shape unless required for truthful live-search reporting.
5. Building a second retrieval system outside the existing repository and contract seams.

## Current State

The retrieval foundation is already substantial:

1. retrieval sources, documents, chunks, and index jobs are durable,
2. indexing can execute through the durable async runtime,
3. retrieval governance surfaces already expose activation, runbook, evidence, and combined governance posture,
4. evaluation families already cover retrieval search and answer behavior,
5. retrieval-backed tasks already exist for search and conservative answer assembly.

But the final runtime hop is still missing:

1. indexed search is not the active retrieval path,
2. live search remains disabled even when configuration enables retrieval mode,
3. runtime-backed approval evidence cannot yet validate a truly live retrieval backend because that backend is absent.

## Decision

`lotus-ai` will implement governed live retrieval search as the next major platform slice.

The first production-capable retrieval activation should:

1. search only promoted, indexed, approved corpus content,
2. preserve source and document provenance in every hit,
3. expose bounded ranking behavior and conservative failure semantics,
4. keep retrieval activation governed by evaluation, runbook, and operational readiness,
5. feed `knowledge_search.v1` and `knowledge_answer.v1` through that live path once enabled.

This RFC does not widen scope to open-ended retrieval. It completes the already-built retrieval backbone by making the search runtime real.

## State Model and Invariants

This RFC establishes the following invariants:

1. live retrieval search must only operate over promoted indexed content,
2. source- and document-level promotion state must remain authoritative for search eligibility,
3. every live retrieval hit must preserve source and document provenance,
4. retrieval mode must not claim `enabled` while live search is still absent,
5. retrieval governance status must never overstate live-search readiness when the live path is blocked or partial,
6. `knowledge_search.v1` and `knowledge_answer.v1` must not silently mix catalog-only and live-search semantics without explicit reporting.

## Architecture Direction

### Live Search Backend Integration

Wire the retrieval gateway to a real indexed search path over the existing durable retrieval corpus.

Required behavior:

1. use the existing retrieval repository seam rather than bypassing it,
2. search only indexed chunks whose source and document promotion posture permit live search,
3. preserve deterministic tie-breaking and bounded result counts,
4. fail conservatively when the configured live search path is not ready.

### Ranking and Provenance

The first live retrieval path must stay explainable.

Required behavior:

1. hits include source id, document id, chunk id, score, and snippet,
2. ranking remains bounded and reviewable,
3. weak or empty search results remain explicit rather than degraded into fake answers,
4. task-level answer generation must continue to expose citation-backed and refusal posture honestly.

### Governance Convergence

Retrieval runtime, activation, runbook, and evidence surfaces must converge on the same truth.

Required behavior:

1. activation readiness must distinguish indexing-ready from live-search-ready,
2. evidence readiness must validate the live-search path, not only staged or catalog-only behavior,
3. runbooks must document rollout, rollback, degraded behavior, and reindex recovery,
4. governance status must treat live-search failure or stale evidence as blocking.

### Task Runtime Convergence

Once live search exists, retrieval-backed task posture must stop describing catalog-only behavior as the ceiling.

Required behavior:

1. `knowledge_search.v1` resolves through live retrieval when rollout permits it,
2. `knowledge_answer.v1` consumes the same live retrieval path,
3. task runtime and audit evidence distinguish catalog-only fallback from live retrieval explicitly,
4. task evidence and audit summaries remain reviewable across both modes during transition.

## Data and Operational Requirements

1. Live retrieval search must survive restart.
2. Search eligibility must derive from durable corpus state, not process-local caches.
3. Ranking inputs and provenance fields must be inspectable.
4. Retrieval mode, runtime status, and actual gateway behavior must agree.
5. Live retrieval rollout must remain disabled unless evaluation, runbook, and governance gates are satisfied.
6. Search failure or partial indexing must fail conservatively rather than fabricating answers.
7. SQL-backed integration tests must prove real live-search behavior against the repository seam.
8. Reindex, promotion rollback, and degraded search behavior must be documented and testable.

## Delivery Slices

### Slice 1: Live Search Repository and Gateway Wiring

Outcome:

1. the retrieval repository exposes the real live-search query seam,
2. the retrieval gateway uses that seam when retrieval mode is enabled,
3. catalog-only fallback remains explicit and bounded only when live search is not active.

Acceptance gate:

1. enabling retrieval mode no longer returns a `503` because of missing search wiring,
2. live hits preserve chunk and document provenance,
3. repository and gateway tests cover successful and empty live search behavior,
4. task execution still behaves conservatively when no live hits are found.

### Slice 2: Promotion and Search Eligibility Convergence

Outcome:

1. live search eligibility is derived from explicit source and document promotion posture,
2. promotion rollback or staged-only content cannot leak into live search,
3. retrieval status surfaces describe live-search eligibility truthfully.

Acceptance gate:

1. promoted indexed content is searchable,
2. staged-only or rolled-back content is not searchable,
3. integration tests cover promotion-aware search eligibility,
4. runtime and governance surfaces reflect the same eligibility model.

### Slice 3: Retrieval Task Runtime Cutover

Outcome:

1. `knowledge_search.v1` uses live retrieval when permitted,
2. `knowledge_answer.v1` uses the same live retrieval backend,
3. task runtime, audit, and evidence surfaces distinguish live search from catalog fallback.

Acceptance gate:

1. task results expose truthful retrieval mode and provenance,
2. weak live-search support still yields conservative refusal behavior,
3. audit evidence reflects live retrieval instead of generic search placeholders,
4. meaningful tests cover both live-search and fallback task behavior.

### Slice 4: Evaluation and Approval-Gate Upgrade

Outcome:

1. retrieval evaluation families validate actual live-search behavior,
2. approval-gate summaries distinguish catalog-only historical baselines from current live-search evidence,
3. stale or failing live-search evidence blocks approval posture explicitly.

Acceptance gate:

1. evaluation execution covers live retrieval search and answer paths,
2. governance no longer treats catalog-only evidence as sufficient for live rollout,
3. runtime-backed evaluation evidence is the approval source of truth,
4. operator-facing summaries clearly distinguish pass, fail, stale, and staged-only posture.

### Slice 5: Runbook and Operational Hardening

Outcome:

1. retrieval rollout, rollback, degraded-mode, and reindex procedures are documented for the live-search path,
2. runtime status and runbooks match actual live-search behavior,
3. restart-survival and failure recovery are covered by meaningful tests.

Acceptance gate:

1. runbooks describe live-search rollout and rollback concretely,
2. degraded or partially indexed posture is surfaced truthfully,
3. SQL-backed tests prove live-search behavior survives restart,
4. the service is materially closer to bank-grade retrieval activation.

## Risks

1. activating live search without strict promotion controls could widen corpus exposure accidentally,
2. weak ranking semantics could reduce answer quality while appearing more “real,”
3. inconsistent runtime-status versus gateway behavior could damage operator trust,
4. keeping catalog-only fallback during transition could create split-brain retrieval semantics if not labeled carefully.

## Alternatives Considered

### Alternative 1: Prompt Activation Before Live Retrieval Search

Rejected as the next highest-value implementation step.

Reason:

1. prompt governance is important, but it does not unlock the same product utility as real governed retrieval search,
2. the current platform already has more retrieval infrastructure built than live retrieval behavior.

### Alternative 2: Safety Runtime Enforcement Before Live Retrieval Search

Rejected as the next immediate RFC.

Reason:

1. safety enforcement remains important, but the platform’s clearest product/runtime gap is still disabled live retrieval search,
2. the retrieval stack already has stronger technical and governance foundations ready for activation.

### Alternative 3: Broader Agentic Orchestration

Rejected.

Reason:

1. it would widen complexity before the core retrieval runtime is complete,
2. `lotus-ai` still needs to make the existing knowledge retrieval path real before higher-order orchestration is justified.

## Acceptance Criteria

This RFC is complete when:

1. retrieval mode `enabled` activates a real live-search path instead of a `503`,
2. live search operates only over promoted indexed content,
3. retrieval hits preserve reviewable provenance and bounded ranking semantics,
4. retrieval-backed tasks consume the live-search path truthfully,
5. runtime, governance, evaluation, and runbook surfaces describe the same live-search reality,
6. catalog-only evidence cannot silently satisfy live retrieval approval posture,
7. the platform is materially closer to production-grade knowledge retrieval for Lotus applications.

## Approval Requested

Approve this RFC if the team agrees that:

1. live retrieval search activation is the next highest-value runtime capability gap,
2. rollout should build on the existing retrieval, async, provider-operations, and evaluation foundations,
3. live search must remain corpus-governed, bounded, and reviewable,
4. delivery should proceed in the slices defined above.
