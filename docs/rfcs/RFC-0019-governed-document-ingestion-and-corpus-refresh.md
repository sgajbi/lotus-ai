# RFC-0019: Governed Document Ingestion and Corpus Refresh

- Status: Implemented
- Date: 2026-03-23
- Owners: lotus-ai
- Requires Approval From: lotus-ai maintainers

## Summary

`lotus-ai` should implement a governed document-ingestion and corpus-refresh backbone so retrieval can evolve from repository-staged corpus state to real approved document onboarding, reindex, replay, and refresh workflows.

The platform now has:

1. retrieval metadata, chunk, and indexing state,
2. runtime-backed retrieval indexing through the async backbone,
3. planned live retrieval activation,
4. governed artifact, observability, and deployment evolution paths.

But corpus growth is still constrained by staged, repository-managed content rather than a real ingestion control plane.

## Why This Is Next

The architecture and retrieval docs already point toward this gap:

1. [scalability-and-deployment-model.md](C:/Users/Sandeep/projects/lotus-ai/docs/architecture/scalability-and-deployment-model.md#L1) explicitly names large document ingestion as async-capable work,
2. [retrieval-and-vector-store.md](C:/Users/Sandeep/projects/lotus-ai/docs/guides/retrieval-and-vector-store.md#L1) still says live embedding generation, runtime vector writes, and production retrieval execution remain incomplete,
3. [retrieval_runbook_readiness.py](C:/Users/Sandeep/projects/lotus-ai/src/app/services/retrieval_runbook_readiness.py#L1) still calls out reindex, replay, failure recovery, and corpus refresh as incomplete,
4. current retrieval job detail in [job_registry.py](C:/Users/Sandeep/projects/lotus-ai/src/app/retrieval/job_registry.py#L1) centers on indexing staged sources, not on governed ingestion of new document material.

This means retrieval will eventually hit a product ceiling unless corpus onboarding becomes a first-class platform capability.

## Problem Statement

`lotus-ai` has a real retrieval control plane, but not yet a real corpus-ingestion control plane.

Current limitations:

1. approved sources and documents are still primarily seeded or migration-managed,
2. there is no bounded runtime path for new document onboarding,
3. corpus refresh still depends on repository and migration updates rather than a governed ingestion workflow,
4. live retrieval activation will be operationally incomplete if corpus change management remains mostly static.

Without this RFC:

1. retrieval can become technically “live” while still being operationally static,
2. corpus freshness and refresh will remain manual and fragile,
3. future use cases will have no governed path for onboarding new source material,
4. document growth could bypass the same governance discipline applied elsewhere in the platform.

## Goals

1. Introduce a governed document-ingestion workflow for retrieval corpus growth.
2. Make corpus refresh, replay, and reindex first-class platform actions.
3. Preserve source, document, and promotion governance throughout ingestion.
4. Reuse async, artifact, authorization, observability, and evaluation foundations.
5. Keep ingestion bounded, reviewable, and enterprise-safe.

## Non-Goals

1. Open web crawling or uncontrolled content collection.
2. Arbitrary end-user uploads directly into the retrieval corpus.
3. Replacing source and document promotion governance with automatic indexing.
4. Unbounded ETL beyond approved retrieval-domain needs.
5. Building a generic content-management platform inside `lotus-ai`.

## Current State

The retrieval platform already supports:

1. durable source, document, chunk, and indexing metadata,
2. runtime-backed indexing execution,
3. source and document governance surfaces,
4. approval-gate and evidence posture for retrieval rollout.

The missing layer is a governed runtime path for:

1. onboarding new approved documents,
2. refreshing existing corpus content,
3. handling superseded or withdrawn documents,
4. replaying or recovering corpus state after ingestion failures.

## Decision

`lotus-ai` will implement a governed document-ingestion and corpus-refresh capability.

The first production-capable ingestion backbone should:

1. accept only approved source/document onboarding requests,
2. persist explicit ingestion job and document-version state,
3. reuse the async execution backbone for heavy ingestion work,
4. preserve artifact, audit, and approval evidence for corpus changes,
5. keep indexing and live search behavior truthful during ingestion and refresh.

This RFC is intentionally bounded:

1. relational metadata remains authoritative for ingestion state, document lineage, approval posture, and operator review,
2. object or artifact storage may carry larger payloads later, but it must not become the authoritative source of corpus truth,
3. ingestion state, document-version lineage, and indexing state are separate models and must stay separately inspectable,
4. this RFC does not create a generic file-management or end-user upload product,
5. Slice 1 introduces durable ingestion state and truthful runtime inspection only; it does not yet claim live onboarding execution.

## State Model and Invariants

This RFC establishes the following invariants:

1. ingestion must not bypass source and document governance,
2. corpus changes must be durable, reviewable, and attributable,
3. superseded, withdrawn, and refreshed document posture must be explicit,
4. live retrieval must not silently serve stale or unapproved content,
5. replay and recovery must preserve coherent corpus truth rather than mutate history invisibly,
6. ingestion and indexing state must remain distinguishable but linked.

Additional state-model rules:

1. a retrieval document may have multiple recorded versions over time, but only explicitly governed active versions can represent current corpus truth,
2. superseded and withdrawn document versions remain visible as historical state and must not be silently deleted,
3. ingestion jobs describe requested corpus change actions; they do not replace document-version lineage,
4. document lineage must support refresh and withdrawal review without requiring operators to infer history from chunk or index tables,
5. existing staged retrieval catalog records remain valid during rollout and are linked forward into the ingestion lineage model rather than replaced wholesale.

## Architecture Direction

### Document Ingestion State Model

Introduce explicit ingestion state and lineage.

Required behavior:

1. ingestion jobs are durable and reviewable,
2. document versions and refresh lineage are explicit,
3. superseded or withdrawn documents remain visible as governed state,
4. document promotion and ingestion state can be reasoned about independently.

### Async Ingestion Execution

Use the existing async backbone rather than inventing a separate ingestion runtime.

Required behavior:

1. ingestion jobs submit through the async control plane,
2. replay, retry, and recovery use the same operator semantics already present,
3. worker-backed evolution can support ingestion later,
4. ingestion does not create a second long-running-job system.

### Retrieval and Search Convergence

Corpus refresh must remain visible to retrieval behavior.

Required behavior:

1. retrieval indexing reflects ingestion outcomes,
2. live search can distinguish fresh, stale, partial, or blocked corpus posture,
3. document withdrawal or supersession affects search eligibility truthfully,
4. retrieval evidence and governance can review corpus change posture.

### Artifact, Audit, and Observability Convergence

Ingestion is not only a storage problem. It is also an operational and governance problem.

Required behavior:

1. larger ingestion outputs and diagnostics can use the governed artifact backbone,
2. audit and incident evidence can explain corpus changes,
3. observability surfaces can show ingestion throughput, failure, and replay posture,
4. authorization and tenant/caller controls apply where relevant.

## Data and Operational Requirements

1. Ingestion state must survive restart.
2. Document-version lineage must be durable.
3. Corpus refresh and withdrawal actions must be auditable.
4. Live retrieval must reflect corpus state truthfully during refresh or recovery.
5. SQL-backed and async-backed tests must prove ingestion and replay behavior.
6. Runbooks must define onboarding, refresh, withdrawal, replay, and failure-recovery procedures.
7. Governance surfaces must not overstate corpus freshness or approval posture.

## Delivery Slices

### Slice 1: Ingestion Contracts and Durable State Model

Outcome:

1. explicit ingestion contracts and state entities exist,
2. document lineage and refresh posture are modeled durably,
3. no live onboarding yet.

Acceptance gate:

1. schema is migration-managed,
2. repository/service seams are explicit,
3. superseded and withdrawn posture are modeled,
4. retrieval runtime stays truthful,
5. a bounded ingestion runtime surface proves the new durable model without overstating activation.

### Slice 2: Async Ingestion Execution and Recovery

Outcome:

1. bounded ingestion jobs can execute through the async backbone,
2. replay, retry, and recovery semantics are real,
3. indexing can follow ingestion through a governed path.

Acceptance gate:

1. ingestion jobs are runtime-backed,
2. recovery and replay are reviewable,
3. integration tests cover ingestion lifecycle behavior,
4. no separate long-running-job framework is introduced.

### Slice 3: Retrieval Runtime and Governance Convergence

Outcome:

1. retrieval status and governance surfaces reflect ingestion and corpus-refresh posture,
2. search eligibility responds truthfully to refreshed or withdrawn documents,
3. approval review includes corpus-change evidence.

Acceptance gate:

1. runtime and governance surfaces are aligned,
2. live retrieval does not hide stale or partial corpus posture,
3. evaluation evidence covers corpus-refresh scenarios,
4. supportability improves materially.

Current implementation note:

1. retrieval runtime, activation, evidence, runbook, and governance surfaces now expose refresh-pending and withdrawn corpus posture explicitly,
2. live search now withholds only the affected document lineage instead of collapsing unrelated searchable documents behind a single source-level blocker,
3. corpus-change review is now represented explicitly in retrieval evidence and runbook posture.

### Slice 4: Artifact, Observability, and Operational Hardening

Outcome:

1. ingestion artifacts and diagnostics use the governed artifact backbone,
2. observability surfaces expose ingestion behavior explicitly,
3. runbooks and governance posture become production-capable.

Acceptance gate:

1. artifact and observability integration are real,
2. runbooks match implementation reality,
3. degraded ingestion or refresh posture is visible,
4. the platform is materially closer to production-grade corpus management.

Current implementation note:

1. ingestion jobs now emit bounded retrieval-owned diagnostic artifacts for completed and failed corpus-change execution,
2. retrieval observability now includes corpus-change runtime posture alongside live-search activation posture,
3. retrieval runbook and evidence surfaces now treat corpus-change review as an explicit governed requirement rather than future-only prose.
4. the final operationally hardened posture requires retrieval ingestion diagnostics to flow through the governed artifact backbone; async execution alone is not enough.

## Risks

1. ingestion could widen corpus scope too aggressively if governance is weak,
2. document lineage could become confusing if supersession and withdrawal are not explicit,
3. retrieval freshness could be overstated during partial refresh,
4. ingestion complexity could outpace actual early use-case needs if rollout is not bounded.

## Alternatives Considered

### Alternative 1: Keep Corpus Changes Repository-Managed Longer

Rejected as the long-term posture.

Reason:

1. it does not scale operationally for live retrieval,
2. it prevents `lotus-ai` from becoming a real shared retrieval service.

### Alternative 2: Let Downstream Apps Push Documents Directly Into Retrieval Storage

Rejected.

Reason:

1. it would bypass source and document governance,
2. it would weaken platform auditability and corpus control.

### Alternative 3: Do Ingestion as Part of Artifact Storage Only

Rejected.

Reason:

1. artifact storage matters, but ingestion also needs lineage, governance, and retrieval-runtime convergence,
2. treating it only as blob handling would miss the real platform-control problem.

## Acceptance Criteria

This RFC is complete when:

1. `lotus-ai` has a governed document-ingestion and corpus-refresh capability,
2. corpus changes are durable, reviewable, and async-capable,
3. retrieval runtime and governance surfaces reflect corpus freshness and approval truthfully,
4. replay, recovery, and withdrawal are operationally real,
5. the platform is materially closer to production-grade retrieval corpus management.

## Approval Requested

Approve this RFC if the team agrees that:

1. governed document ingestion is the next retrieval-platform gap after the current runtime/provider/control-plane sequence,
2. corpus growth should happen through the same governance discipline as the rest of `lotus-ai`,
3. ingestion should reuse the async, artifact, observability, and authorization foundations already being built,
4. delivery should proceed in the slices defined above.
