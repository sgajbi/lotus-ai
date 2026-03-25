# RFC-0025: Operational Root-Cause Copilot for lotus-core

- Status: Draft
- Date: 2026-03-25
- Owners: lotus-ai, lotus-core
- Requires Approval From: lotus-ai maintainers, lotus-core maintainers

## Summary

`lotus-core` is now a mature canonical system with:

1. deterministic transaction, position, valuation, and cashflow processing,
2. query and query-control-plane APIs,
3. support and lineage diagnostics,
4. reconciliation and replay visibility,
5. snapshot and simulation contracts,
6. strong operational and traceability posture.

That maturity creates the opportunity for a second genuinely high-value AI feature:

1. an `Operational Root-Cause Copilot`,
2. designed for support, operations, and investigation workflows,
3. grounded in `lotus-core`'s existing support, lineage, reconciliation, and transaction-state
   APIs,
4. capable of turning operational state into likely-cause explanations and next-check guidance.

This is not a generic support chatbot.

It is a bounded diagnostic explanation layer over real `lotus-core` surfaces such as:

1. support overview,
2. calculator SLOs,
3. control stages,
4. replay keys and replay jobs,
5. valuation and aggregation jobs,
6. reconciliation runs and findings,
7. lineage key state,
8. transaction, position, BUY-state, SELL-state, and snapshot contracts.

## Why This RFC Exists

`lotus-core` is feature-rich enough that much of the operational pain is no longer missing data.

It is investigative effort.

Operators and downstream teams still have to:

1. inspect multiple support endpoints,
2. correlate control-stage, replay, and lineage state manually,
3. read transaction and position context alongside reconciliation findings,
4. decide what is most likely wrong,
5. determine what to check next.

The platform already contains the right raw material.

For example, `lotus-core` now exposes control-plane operational surfaces such as:

1. `/support/portfolios/{portfolio_id}/overview`
2. `/support/portfolios/{portfolio_id}/calculator-slos`
3. `/support/portfolios/{portfolio_id}/control-stages`
4. `/support/portfolios/{portfolio_id}/reprocessing-keys`
5. `/support/portfolios/{portfolio_id}/reprocessing-jobs`
6. `/support/portfolios/{portfolio_id}/valuation-jobs`
7. `/support/portfolios/{portfolio_id}/aggregation-jobs`
8. `/support/portfolios/{portfolio_id}/analytics-export-jobs`
9. `/support/portfolios/{portfolio_id}/reconciliation-runs`
10. `/support/portfolios/{portfolio_id}/reconciliation-runs/{run_id}/findings`
11. `/lineage/portfolios/{portfolio_id}/securities/{security_id}`
12. `/lineage/portfolios/{portfolio_id}/keys`

And query-state surfaces such as:

1. portfolio transaction timelines,
2. position snapshots and as-of views,
3. BUY-state linkage and cashflow details,
4. SELL disposal and cash-linkage state,
5. core snapshot contracts for governed downstream consumers.

That means the next real value is not more raw APIs.

It is faster human understanding of:

1. what likely caused the issue,
2. what evidence supports that interpretation,
3. which next checks are most appropriate.

## Relationship to Existing lotus-core RFCs

This RFC should build on existing operational and support work, not replace it.

Most importantly:

1. RFC 033 in `lotus-core` established API-first support and lineage surfaces,
2. the multi-model platform direction keeps `lotus-core` focused on deterministic core truth,
3. the old in-core review/report orchestration idea in archived RFC 012 was explicitly moved out of
   `lotus-core`.

That has direct consequences for this RFC:

1. do build on RFC 033 support and lineage APIs,
2. do build on transaction, snapshot, and stateful query contracts,
3. do not recreate a giant monolithic "review API" inside `lotus-core`,
4. do not ask `lotus-ai` to replace deterministic support surfaces,
5. do use `lotus-ai` as a bounded interpretation layer over those surfaces.

## Problem Statement

`lotus-core` exposes a large amount of operational truth, but root-cause analysis still requires too
much manual synthesis.

Common pain points include:

1. missing or unexpected positions,
2. unexplained cash or holding changes,
3. blocked or failed reconciliation runs,
4. stale replay keys or replay jobs,
5. valuation or aggregation backlog issues,
6. BUY or SELL linkage confusion,
7. snapshot fallback or freshness confusion,
8. portfolio-day control-stage failures that require multi-endpoint inspection.

Current limitations:

1. support and lineage APIs are strong but mostly descriptor-level,
2. the system tells operators what exists, but not yet the most likely explanation,
3. there is no reusable AI product seam for operational investigation,
4. teams can still end up re-reading the same operational patterns incident after incident.

Without this RFC:

1. support resolution remains slower than it should be,
2. operational knowledge remains concentrated in experienced individuals,
3. downstream teams may build ad hoc diagnostic summarizers with weaker governance,
4. the strongest operational AI opportunity in the Lotus estate remains unaddressed.

## Goals

1. Deliver a high-value AI investigation feature for `lotus-core`.
2. Explain likely operational root causes using existing deterministic support APIs.
3. Provide bounded next-check guidance without taking corrective action automatically.
4. Preserve the authority of `lotus-core` support, lineage, transaction, and snapshot contracts.
5. Make repeated investigation workflows faster and more consistent.
6. Keep the feature reviewable, auditable, and support-safe.

## Non-Goals

1. Automatically mutating `lotus-core` state or replaying jobs.
2. Replacing support, lineage, reconciliation, or query APIs.
3. Letting `lotus-ai` invent operational facts not present in the supplied evidence bundle.
4. Building a generic support chatbot over logs.
5. Recreating the archived lotus-core report/review orchestration model.
6. Turning `lotus-ai` into the owner of runbook or incident decisions.

## Decision

`lotus-ai` will add a new `Operational Root-Cause Copilot` capability for `lotus-core`.

This capability will:

1. consume a bounded investigation bundle composed from real `lotus-core` support and query
   surfaces,
2. produce a structured explanation of likely root cause candidates,
3. surface supporting evidence and uncertainty explicitly,
4. suggest bounded next checks rather than actions that mutate state,
5. remain separate from automated replay, rollback, or remediation controls.

The initial implementation boundary is strict:

1. `lotus-core` or a trusted integration layer assembles the evidence bundle,
2. `lotus-ai` explains the evidence bundle,
3. `lotus-ai` does not fetch arbitrary logs or infer hidden system state,
4. explanations must link back to named evidence sections,
5. the output remains operator-assistive, not operator-authoritative.

## Proposed Capability Shape

The copilot should accept an investigation bundle and return a structured diagnosis response.

### Investigation Types

The initial supported investigation families should be:

1. `reconciliation_failure`
2. `stale_or_stuck_reprocessing`
3. `unexpected_position_change`
4. `unexpected_cash_change`
5. `buy_sell_linkage_issue`
6. `snapshot_or_freshness_issue`

These should be explicit enumerations, not free-form support prompts.

### Required Evidence Bundle

The evidence bundle should be composed from deterministic `lotus-core` APIs.

Initial evidence sections should include:

1. support overview snapshot
2. calculator SLO snapshot when relevant
3. portfolio-day control stages
4. replay keys or replay jobs when relevant
5. reconciliation run and finding detail when relevant
6. lineage key or single-key lineage detail
7. transaction timeline excerpts
8. position and snapshot context
9. BUY-state or SELL-state linkage context when relevant
10. core snapshot metadata when freshness or baseline confusion is part of the issue

### Actual lotus-core Surfaces This RFC Builds On

The bundle should be built from real shipped surfaces, especially:

1. query-control-plane support and lineage APIs from RFC 033
2. query-service transaction APIs
3. query-service position APIs
4. BUY-state and SELL-state APIs
5. core snapshot APIs
6. reconciliation support listings and findings

This keeps the feature aligned with the current `lotus-core` architecture instead of inventing a
parallel source of truth.

## Architecture Direction

### 1. Evidence Assembly Must Stay Outside lotus-ai

`lotus-core` or a thin integration layer should decide:

1. which evidence to fetch,
2. which portfolio, security, run, or transaction scope is relevant,
3. how much evidence is enough for a bounded investigation,
4. which fields are safe and useful to include.

`lotus-ai` should not become a dynamic multi-API orchestration engine in the first implementation.

### 2. Output Must Be Diagnostic and Structured

The response should include:

1. issue summary
2. likely root-cause candidates
3. most likely candidate
4. supporting evidence blocks
5. contradictions or uncertainty notes
6. next checks
7. unsupported or missing evidence notes

This is critical because support teams need inspectable reasoning, not just prose.

### 3. Next Checks Must Be Bounded

The feature may recommend checks such as:

1. inspect a specific reconciliation finding,
2. verify a replay-key state transition,
3. compare BUY-state and linked cashflow details,
4. confirm whether a snapshot fallback occurred,
5. inspect a specific transaction group or lineage key.

It must not:

1. trigger replay,
2. modify control stages,
3. patch records,
4. re-run ingestion automatically.

### 4. Pairing With Existing Operational Contracts

The feature should strengthen, not obscure, the current `lotus-core` support model.

That means:

1. explanations must cite named operational sections,
2. `lotus-ai` should not flatten distinct support states into vague language,
3. reconciliation blocking severity, replay staleness, and snapshot fallback should remain explicit,
4. audit trails must preserve which evidence sections were used.

### 5. No In-Core Review-Orchestration Regression

RFC 012 in `lotus-core` was archived because review/report orchestration moved out of that repo.

This RFC should therefore avoid:

1. an all-purpose review endpoint in `lotus-core`,
2. an AI-owned incident dashboard in `lotus-core`,
3. bundling unrelated reporting concerns into operational diagnosis.

The capability must stay focused on support and root cause.

## Data and Operational Requirements

1. Every investigation request must identify investigation type and bounded scope.
2. Every diagnosis must reference named evidence sections.
3. The capability must support explicit degraded behavior when evidence is incomplete or
   contradictory.
4. The capability must preserve audit and evidence traceability through the existing `lotus-ai`
   runtime model.
5. The capability must not claim certainty when the underlying evidence only supports multiple
   plausible causes.
6. The capability must remain read-only and support-oriented.

## Delivery Slices

### Slice 1: Contract and Pack Definition

Outcome:

1. a new bounded root-cause capability pack exists,
2. investigation types and response shape are explicit,
3. evidence bundle requirements are documented against real `lotus-core` APIs.

Acceptance gate:

1. the feature is clearly bounded,
2. it builds on shipped `lotus-core` support surfaces,
3. no implicit autonomous retrieval or mutation is introduced.

### Slice 2: Evidence Bundle Integration

Outcome:

1. `lotus-core` can assemble investigation bundles from support, lineage, transaction, position,
   and state contracts,
2. `lotus-ai` can consume those bundles through one named capability seam.

Acceptance gate:

1. evidence section ownership is explicit,
2. different investigation types use bounded evidence subsets,
3. contradiction and insufficiency handling are testable.

### Slice 3: Runtime-Backed Quality Gates

Outcome:

1. dedicated eval families exist for operational diagnosis quality,
2. pack quality is measured on evidence usage, root-cause plausibility, and next-check quality.

Acceptance gate:

1. runtime-backed evals exist,
2. uncertainty and ambiguity cases are included,
3. the feature is not promoted on fluency alone.

### Slice 4: Governance, Runbook, and Support Readiness

Outcome:

1. the capability has activation, runbook, observability, and governance surfaces,
2. operators can inspect diagnosis outputs alongside their evidence refs.

Acceptance gate:

1. support review is practical,
2. bounded rollback and disable posture exists,
3. operational trust does not depend on hidden prompt behavior.

### Slice 5: Reusable Operational Investigation Pattern

Outcome:

1. the feature is reusable across multiple operational investigation families,
2. `lotus-core` support workflows gain one coherent AI investigation seam without weakening the
   deterministic support model.

Acceptance gate:

1. the capability measurably reduces investigation ambiguity,
2. evidence-linked diagnosis remains truthful,
3. no support ownership boundaries are blurred.

## Risks

1. If evidence bundles are too broad, the feature becomes noisy and hard to trust.
2. If evidence bundles are too thin, explanations become generic and low-value.
3. If the feature overstates confidence, operators may follow weak hypotheses.
4. If next checks drift into action suggestions, the system may blur support boundaries.
5. If the feature bypasses existing support APIs, it will create a parallel and weaker ops model.

## Success Criteria

This RFC is successful when:

1. `lotus-core` operators can get a useful, evidence-linked likely-cause explanation for bounded
   incidents,
2. the feature reduces manual synthesis across support endpoints,
3. it clearly accelerates investigation without taking over deterministic support workflows,
4. it strengthens the operational usefulness of `lotus-core`'s existing support and lineage
   surfaces rather than competing with them.
