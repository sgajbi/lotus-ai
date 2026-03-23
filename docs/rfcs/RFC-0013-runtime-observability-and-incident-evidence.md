# RFC-0013: Runtime Observability and Incident Evidence Backbone

- Status: Draft
- Date: 2026-03-23
- Owners: lotus-ai
- Requires Approval From: lotus-ai maintainers

## Summary

`lotus-ai` should implement a real runtime observability and incident-evidence backbone so platform operators can diagnose, govern, and support live provider, retrieval, prompt, safety, async, and evaluation behavior using authoritative operational telemetry rather than primarily documentation and readiness prose.

RFC-0004 and RFC-0005 hardened provider operations and made their state durable.
RFC-0006 and RFC-0007 made async execution and evaluation execution runtime-backed.
RFC-0011 defines the dedicated worker and queue-backed deployment target.
RFC-0012 defines caller identity and tenant isolation controls for a real shared-service posture.

The next high-value platform gap is that observability expectations are documented in many places, but the platform does not yet have a unified, runtime-backed observability and incident-evidence layer to match those controls.

## Why This Is Next

The platform now has many control surfaces:

1. provider operations, budget, quota, and degradation state,
2. retrieval indexing, activation, governance, and evaluation posture,
3. prompt governance and planned activation state,
4. runtime-backed async and evaluation execution,
5. audit and execution evidence for task-level behavior.

But operator observability is still incomplete:

1. multiple runbook-readiness endpoints explicitly call out missing dashboards, alerts, and supportability views,
2. runtime and governance summaries exist, but they are not yet the same thing as real operational telemetry,
3. incident review still depends too much on reconstructing state from multiple APIs and durable records after the fact,
4. the architecture already calls for observability broken down by caller app and capability, but there is no completed implementation sequence for that.

## Problem Statement

`lotus-ai` now has enough live or near-live control planes that lack of first-class observability is becoming a real platform risk.

Current limitations:

1. provider runbooks call for latency, failure, quota, budget, and degradation dashboards, but those are not yet an implemented platform capability,
2. retrieval runbooks call for indexing, replay, and failure observability, but the platform does not yet expose a cohesive operational evidence layer for those flows,
3. async runbooks call for queue, worker, replay, and escalation dashboards, but those are still mostly documented as future needs,
4. prompt and safety rollout sequences will need stronger approval and rollback evidence than current human-readable readiness summaries.

The result is that:

1. the platform has growing runtime complexity,
2. control planes are increasingly durable and real,
3. but the operational visibility needed to run them safely still lags behind.

## Goals

1. Introduce a first-class runtime observability and incident-evidence model for `lotus-ai`.
2. Expose domain-specific operational summaries grounded in actual runtime telemetry and durable evidence.
3. Break down runtime behavior by caller app, tenant, capability, and execution domain where appropriate.
4. Support incident review without requiring manual reconstruction from many separate endpoints.
5. Keep the observability model aligned with the existing provider, retrieval, prompt, async, evaluation, and audit seams.

## Non-Goals

1. Building a generic enterprise monitoring platform.
2. Replacing external metrics, logs, or tracing systems used by the deployment environment.
3. Creating arbitrary analytics dashboards unrelated to governed platform operations.
4. Storing unlimited raw trace payloads in the service database.
5. Replacing runbooks with telemetry alone.

## Current State

The service already exposes:

1. top-level runtime status,
2. domain-specific readiness, governance, and runbook endpoints,
3. audit catalog and task evidence summaries,
4. provider operations summaries,
5. async, retrieval, and evaluation runtime state.

These are valuable, but they are not yet a cohesive observability backbone.

What is still missing:

1. explicit operational telemetry models for incidents and degraded behavior,
2. unified incident evidence summaries across runtime domains,
3. durable supportability views that reflect caller, tenant, and capability dimensions,
4. a rollout path that turns documented dashboard expectations into implemented platform capability.

## Decision

`lotus-ai` will implement a runtime observability and incident-evidence backbone as a platform capability.

The first production-capable observability layer should:

1. define bounded operational evidence models per major domain,
2. expose incident-ready summaries for provider, retrieval, async, evaluation, prompt, and safety posture,
3. preserve caller- and capability-level breakdown where the underlying data supports it,
4. remain grounded in actual runtime and durable state rather than synthetic status prose,
5. support runbook-driven operations rather than replacing them.

## State Model and Invariants

This RFC establishes the following invariants:

1. observability surfaces must describe actual runtime behavior, not only documented expectation,
2. incident evidence must be attributable to real runtime state and durable records,
3. operator-facing summaries must distinguish healthy, degraded, stale, and unavailable telemetry posture,
4. caller- and tenant-level operational breakdown must only appear where the underlying identity model supports it,
5. observability must not silently weaken audit or safety boundaries,
6. runtime status and observability summaries must not contradict each other.

## Architecture Direction

### Domain Telemetry Model

Introduce bounded operational telemetry models for each major platform domain.

Required behavior:

1. provider telemetry covers latency, failure, quota, budget, degradation, and circuit posture,
2. retrieval telemetry covers indexing throughput, replay posture, search readiness, and failure/rejection patterns,
3. async telemetry covers queue depth, worker activity, replay/recovery posture, and control-action trends,
4. evaluation telemetry covers run throughput, verdict posture, stale evidence, and approval-gate freshness,
5. prompt and safety telemetry cover rollout posture, blocked actions, and rollback/safety-enforcement incident evidence where applicable.

### Supportability and Incident Evidence

Add explicit incident-evidence summaries that can support operator review.

Required behavior:

1. supportability views can explain what failed, when, and in which domain,
2. cross-domain incidents can be correlated through existing audit and correlation metadata,
3. durable event and state models are reused where available,
4. no hidden “dashboard-only” truth is introduced outside the platform contracts.

### Caller and Capability Breakdown

The observability layer should match the shared-platform architecture.

Required behavior:

1. provider, task, and async summaries can be broken down by caller app where meaningful,
2. tenant-aware views exist where tenant identity is present and authorized,
3. capability-level breakdown can explain which task, fixture family, retrieval source, or control-plane path is driving load or failure,
4. breakdowns remain bounded and governable rather than ad hoc analytics.

### Runbook and Governance Convergence

Observability must close the current gap between documented runbook needs and implemented operational evidence.

Required behavior:

1. runbook-readiness surfaces can point to actual observability implementations,
2. governance summaries can use observability freshness and completeness as a readiness dimension where appropriate,
3. operator runtime review can depend less on manual API stitching,
4. deployment-grade worker and queue rollout can inherit the same observability backbone.

## Data and Operational Requirements

1. Observability summaries must survive restart where based on durable state.
2. Volatile metrics and durable incident evidence must be distinguished clearly.
3. Telemetry gaps or stale evidence must surface explicitly.
4. Caller and tenant breakdown must respect the authorization model from the shared-service access layer.
5. Observability data must not leak sensitive content that should remain redacted.
6. SQL-backed tests must prove durable incident evidence behavior where applicable.
7. Runbooks must define how operators use the observability layer during incident review.

## Delivery Slices

### Slice 1: Bounded Domain Telemetry Contracts and Services

Outcome:

1. explicit observability contracts and service seams exist,
2. domain telemetry is modeled directly rather than implied through prose,
3. no broad operational cutover yet.

Acceptance gate:

1. telemetry contracts are typed and bounded,
2. services derive from actual runtime data where available,
3. unit tests cover healthy and degraded posture,
4. runtime status remains consistent with the new observability layer.

### Slice 2: Provider, Retrieval, and Async Incident Summaries

Outcome:

1. the most operationally critical domains expose incident-evidence summaries,
2. supportability views can explain failure and degraded posture directly,
3. operator review improves materially.

Acceptance gate:

1. provider, retrieval, and async incident surfaces are runtime-backed,
2. degraded posture is explicit,
3. meaningful integration tests cover operational summaries,
4. runbook references can point to implemented evidence views.

### Slice 3: Evaluation, Prompt, and Safety Observability Convergence

Outcome:

1. evaluation freshness and approval evidence become part of the observability layer,
2. prompt and safety rollout paths gain incident and rollback evidence views,
3. observability spans the full platform control-plane sequence.

Acceptance gate:

1. evaluation, prompt, and safety telemetry are bounded and truthful,
2. stale or partial evidence is explicit,
3. approval-gate and observability surfaces remain aligned,
4. tests cover operationally meaningful cases instead of only static counts.

### Slice 4: Caller-, Tenant-, and Capability-Level Breakdown

Outcome:

1. observability summaries can be broken down by caller app, tenant, and capability where supported,
2. shared-service support workflows improve materially,
3. noisy-neighbor investigation becomes practical.

Acceptance gate:

1. breakdowns are authorization-aware,
2. supportability views remain bounded and performant,
3. integration tests cover caller/capability perspectives,
4. the platform is materially closer to the documented scaling and supportability model.

### Slice 5: Runbook and Operational Hardening

Outcome:

1. runbooks, readiness surfaces, and observability implementation converge,
2. dashboard and alert expectations are grounded in actual platform capability,
3. incident review becomes more repeatable and less reconstructive.

Acceptance gate:

1. runbooks match implementation reality,
2. readiness surfaces no longer point only to future observability work,
3. degraded or stale observability posture is surfaced truthfully,
4. the platform is materially closer to enterprise-grade operability.

## Risks

1. observability scope could expand into unbounded analytics,
2. weak telemetry semantics could create false operator confidence,
3. sensitive runtime data could leak if incident evidence is not bounded carefully,
4. too many per-domain summaries could fragment rather than unify operational review.

## Alternatives Considered

### Alternative 1: Keep Observability Mostly in External Tooling

Rejected as the sole approach.

Reason:

1. external tooling is necessary, but the platform still needs first-class operational evidence surfaces tied to its governed contracts,
2. many current readiness and governance endpoints already assume a platform-owned observability story.

### Alternative 2: Prioritize Artifact/Object-Storage Scaling First

Deferred.

Reason:

1. object storage will matter, but operational visibility across the growing runtime is the more immediate shared-platform risk,
2. observability will also make future artifact-scaling work safer and easier to govern.

### Alternative 3: Add Only More Runtime Status Endpoints

Rejected.

Reason:

1. status summaries alone are not enough for incident evidence,
2. the platform now needs operational telemetry and supportability views, not only higher-level status prose.

## Acceptance Criteria

This RFC is complete when:

1. `lotus-ai` has a bounded, runtime-backed observability layer across its major operational domains,
2. incident evidence can be reviewed without stitching together many unrelated endpoints manually,
3. caller-, tenant-, and capability-level supportability views exist where the platform has underlying data,
4. runbook-readiness and governance surfaces align with actual observability capability,
5. the platform is materially closer to enterprise-grade operability.

## Approval Requested

Approve this RFC if the team agrees that:

1. runtime observability and incident evidence are the next high-value operability gap after the current control-plane sequence,
2. the platform should expose bounded operational telemetry as part of its governed API surface,
3. runbook and governance readiness should converge on actual observability capability,
4. delivery should proceed in the slices defined above.
