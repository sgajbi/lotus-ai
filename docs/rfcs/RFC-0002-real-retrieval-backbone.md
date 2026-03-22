# RFC-0002: Real Retrieval Backbone

- Status: Closed
- Date: 2026-03-22
- Closed Date: 2026-03-22
- Owners: lotus-ai
- Requires Approval From: lotus-ai maintainers

## Summary

`lotus-ai` should implement a real retrieval backbone as the next major platform slice.

This RFC moves retrieval from catalog-only staged metadata lookup to durable indexed retrieval over promoted content, backed by PostgreSQL and `pgvector`, with explicit governance for source promotion, indexing, searchability, and citation behavior.

The goal is to make `knowledge_search.v1` and `knowledge_answer.v1` trustworthy platform capabilities rather than bounded demos over seeded catalog metadata.

## Closure Status

This RFC is closed.

It is considered closed because the implementation outcomes and close-out slices described here now exist in the repository, the local quality gates are green, and the remaining work is no longer “finish the retrieval backbone” work. Future work should build on this backbone rather than reopen it.

## Implementation Status

Implemented so far:

1. Slice 1: Document-Level Promotion Model
2. Slice 2: Durable Chunk and Embedding Schema
3. Slice 3: Real Indexing Pipeline
4. Slice 4: Vector-Backed Retrieval Execution
5. Slice 5: Retrieval-Backed Answer Hardening
6. Slice 6: Evaluation and Operations Hardening
7. Slice 7: Backend-Owned Indexed Search Seam
8. Slice 8: Async Retrieval Indexing Orchestration

Remaining:

1. None

## Why This Is Next

The platform foundation is now strong:

1. contracts are stable,
2. audit and runtime inspection are strong,
3. readiness and governance surfaces exist,
4. bounded retrieval-backed tasks are already live.

The main constraint is now retrieval quality, not platform scaffolding.

Adding live model execution before real retrieval would create generated output on top of weak grounding. For a bank-grade system, grounded retrieval is the higher-priority capability.

## Problem Statement

Current retrieval behavior is materially stronger than when this RFC was opened, but it still has two closure gaps:

1. indexed retrieval now exists, but ranking is still assembled above the backend seam instead of being owned by the backend implementation,
2. deterministic indexing replay now exists, but it is still invoked directly rather than through the governed async-work model,
3. retrieval-backed task quality is now useful, but final enterprise posture depends on closing those two seams cleanly.

This is a strong foundation, but it is not yet the full retrieval backbone described by the RFC.

## Goals

1. Implement durable retrieval indexing state in PostgreSQL.
2. Introduce real chunk-level vector search using `pgvector`.
3. Make promotion explicit at both source and document level.
4. Support deterministic indexing and reindexing flows with persistent job state.
5. Keep retrieval execution bounded, auditable, and citation-first.
6. Preserve conservative refusal behavior when retrieval support is weak.
7. Roll out in slices that can be validated independently.

## Non-Goals

1. Live generative provider rollout.
2. Autonomous document ingestion from external systems.
3. Broad multi-vector-store abstraction.
4. Unbounded semantic search across arbitrary tenant content.
5. Replacing governance and approval controls with automatic activation.

## Current State

Today `lotus-ai` already has:

1. retrieval metadata repositories,
2. migration-managed retrieval tables,
3. retrieval runtime and governance endpoints,
4. catalog-only retrieval execution,
5. `knowledge_search.v1` and `knowledge_answer.v1`,
6. task/audit/evidence inspection surfaces,
7. document-level promotion posture,
8. persisted preview embeddings,
9. indexed retrieval execution behind the retrieval gateway,
10. deterministic retrieval index refresh,
11. retrieval-specific evaluation and operations hardening.

Those pieces should be retained and extended, not replaced.

## Decision

`lotus-ai` will implement retrieval in two layers:

1. a governed persistence and indexing layer for promoted retrieval content,
2. a governed execution layer for bounded vector-backed retrieval and citation selection.

The first production retrieval backend will be:

1. PostgreSQL,
2. `pgvector`,
3. persistent chunk embeddings,
4. explicit index job records,
5. explicit document promotion state.

The existing catalog-only path remains as the safe fallback until the real path is approved and enabled.

## Architecture Direction

### Retrieval Persistence

Add or extend durable models for:

1. retrieval documents,
2. retrieval chunks,
3. document promotion state,
4. chunk embedding records,
5. indexing jobs,
6. indexing job events or status history if needed for replay visibility.

### Retrieval Indexing

Indexing should be deterministic and replayable:

1. document selected for indexing,
2. chunking applied using explicit rules,
3. embedding generated for each chunk,
4. chunk rows and vector data persisted,
5. index job state updated with counts and failure details.

Chunking rules must be documented and versioned enough that reindexing is explainable.

### Retrieval Execution

Execution path should be:

1. validate query and requested source constraints,
2. restrict search to promoted searchable content,
3. perform bounded vector similarity search,
4. apply deterministic result shaping,
5. return explicit citations and support score,
6. refuse or down-rank when support is weak.

### Governance

Governance must distinguish:

1. staged sources,
2. promoted searchable sources,
3. staged documents,
4. promoted searchable documents,
5. indexed chunks present,
6. indexed chunks current versus stale.

The existing runtime and governance endpoints should be extended rather than replaced.

## Data and Operational Requirements

1. Retrieval activation remains disabled by default until governance gates are satisfied.
2. Real retrieval search must fail clearly when configured prerequisites are missing.
3. Indexing state must survive service restarts.
4. Search execution must remain bounded by explicit limits.
5. Search results must always preserve source and document provenance.
6. Audit records must preserve retrieval evidence sufficient for support review.

## Delivery Slices

### Slice 1: Document-Level Promotion Model

Outcome:

1. searchable versus staged state exists at document level,
2. retrieval governance surfaces expose document promotion posture,
3. no vector execution yet.

Acceptance gate:

1. migrations land cleanly,
2. document-level governance is inspectable,
3. no regression to current catalog-only path.

### Slice 2: Durable Chunk and Embedding Schema

Outcome:

1. retrieval chunks have durable persisted shape,
2. embedding storage is defined for PostgreSQL plus `pgvector`,
3. indexing job records can account for chunk and embedding counts.

Acceptance gate:

1. schema is migration-managed,
2. persistence contracts are tested,
3. no hidden runtime table creation.

### Slice 3: Real Indexing Pipeline

Outcome:

1. deterministic chunking implemented,
2. indexing jobs persist status and counts,
3. chunk embeddings are stored for promoted documents,
4. replay and reindex behavior is explicit.

Acceptance gate:

1. indexing job lifecycle is testable,
2. failure states are explicit,
3. runtime readiness reflects indexing prerequisites.

### Slice 4: Vector-Backed Retrieval Execution

Outcome:

1. real vector search runs over promoted indexed content,
2. `knowledge_search.v1` uses the real path when enabled,
3. catalog-only path remains available as fallback.

Acceptance gate:

1. bounded result counts,
2. citation provenance preserved,
3. fallback behavior remains explicit.

### Slice 5: Retrieval-Backed Answer Hardening

Outcome:

1. `knowledge_answer.v1` uses vector-backed retrieval support,
2. refusal behavior is tied to stronger support thresholds,
3. answer citations reflect promoted indexed content.

Acceptance gate:

1. citation-backed answers verified,
2. weak-support refusals verified,
3. audit and evidence surfaces preserve answer support details.

### Slice 6: Evaluation and Operations Hardening

Outcome:

1. retrieval evaluation fixtures cover relevance, citations, and refusals,
2. operational runbooks and readiness checks reflect the real backend,
3. CI gates validate the real retrieval path where feasible.

Acceptance gate:

1. meaningful retrieval eval assets exist,
2. operational posture is documented and testable,
3. rollout remains governed.

### Slice 7: Backend-Owned Indexed Search Seam

Outcome:

1. indexed retrieval ranking is owned by the retrieval backend seam rather than assembled in the gateway service layer,
2. SQL-backed retrieval can execute bounded ranking through backend-specific query logic,
3. the current preview-vector path remains deterministic while becoming easier to replace with `pgvector`.

Acceptance gate:

1. retrieval gateway no longer assembles indexed ranking itself,
2. repository-backed indexed search is directly tested,
3. the execution path is clearer and more modular than the current service-scored implementation.

### Slice 8: Async Retrieval Indexing Orchestration

Outcome:

1. retrieval indexing refresh can be driven through the governed async-work model,
2. retrieval indexing no longer depends only on direct synchronous execution,
3. runtime and operational surfaces reflect the async indexing path honestly.

Acceptance gate:

1. retrieval indexing has an async submission or execution seam,
2. indexing replay remains deterministic and inspectable,
3. retrieval and async runtime surfaces stay aligned.

## Risks

1. retrieval quality may still appear better in tests than in real product use if the promoted corpus is too small or too clean,
2. embedding generation introduces new operational and cost controls,
3. chunking decisions can lock in poor retrieval quality if treated as an implementation detail instead of a governed rule,
4. introducing vector search without document promotion controls would weaken provenance discipline.

## Alternatives Considered

### Alternative 1: Live Provider First

Rejected for now.

Reason:

1. it would improve generation before grounding,
2. that is the wrong order for enterprise quality.

### Alternative 2: Keep Catalog-Only Retrieval Longer

Rejected as the next major phase.

Reason:

1. it is useful as a fallback,
2. but it cannot become the long-term retrieval platform.

### Alternative 3: Abstract Multiple Vector Stores Now

Rejected for now.

Reason:

1. premature abstraction would add complexity,
2. `PostgreSQL + pgvector` is already the chosen first architecture in the roadmap.

## Acceptance Criteria

This RFC is complete when:

1. retrieval is backed by durable indexed content rather than staged metadata alone,
2. document-level promotion posture is explicit and inspectable,
3. `knowledge_search.v1` can execute through a real vector-backed path,
4. `knowledge_answer.v1` can produce citation-backed responses over that path while preserving conservative refusals,
5. evaluation and operational readiness are documented and tested,
6. indexed retrieval ranking is owned by the backend seam rather than the gateway service layer,
7. deterministic indexing replay is available through the governed async-work model.

## Close-Out Notes

The retrieval backbone is now materially in place:

1. document and source promotion are explicit and inspectable,
2. chunk and embedding persistence are migration-managed,
3. indexed retrieval execution exists behind the retrieval backend seam,
4. retrieval-backed answer support is hardened and audited,
5. deterministic indexing refresh exists,
6. async indexing orchestration exists in governed stubbed mode,
7. evaluation and operational posture reflect the implemented retrieval path.

Follow-on work should be tracked under new RFCs or implementation plans, not by extending this RFC indefinitely.
