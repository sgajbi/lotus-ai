# RFC-0026: Operator Control-Plane Dashboard and Observability Integration

- Status: Draft
- Date: 2026-03-25
- Owners: lotus-ai
- Requires Approval From: lotus-ai maintainers

## Summary

`lotus-ai` now exposes a large set of operator-facing APIs for:

1. runtime,
2. retrieval,
3. evals,
4. async execution,
5. safety and governance,
6. resilience,
7. ingestion,
8. embeddings and providers,
9. deployment split,
10. production go-live,
11. capability packs,
12. app-capability rollout.

These control planes are strong, but they are still API-first and document-heavy.

This RFC defines the next operational layer:

1. a first-class `lotus-ai` operator control-plane dashboard,
2. built on top of the existing platform APIs,
3. explicitly separated from deep infrastructure observability tooling such as Grafana, Datadog,
   OpenSearch, or cloud-native monitoring,
4. focused on platform posture, rollout truth, governance state, and actionable operator review.

## Why This RFC Exists

The current platform is now mature enough that operators need more than endpoint literacy.

Today, an operator may need to inspect:

1. `/platform/runtime-status`
2. `/platform/providers/*`
3. `/platform/retrieval/*`
4. `/platform/evals/*`
5. `/platform/async/*`
6. `/platform/observability/*`
7. `/platform/production-baseline/*`
8. `/platform/production-go-live/*`
9. `/platform/capability-packs/*`
10. `/platform/app-capability-rollouts/*`

That is powerful, but not yet operationally ergonomic.

Industry-standard practice is not to collapse all of this into one giant custom monitoring system.

The usual model is:

1. API-first control plane,
2. thin operator dashboard for approval, rollout, and review workflows,
3. separate observability tooling for logs, metrics, traces, and alerts.

`lotus-ai` now has enough control-plane surface area that the absence of a dashboard is becoming an
operator friction issue rather than a healthy sign of simplicity.

## Problem Statement

`lotus-ai` can already answer many important questions, but operators still have to reconstruct the
answers manually from multiple APIs.

Examples:

1. is the platform technically healthy but still production-blocked?
2. is retrieval degraded because of corpus posture, embedding posture, or ingestion review?
3. is a capability pack reusable but not go-live approved?
4. is a downstream app in limited rollout, production-approved, paused, or retired?
5. is a first-use-case path blocked by resilience, provider governance, or use-case evidence?

The current situation creates these problems:

1. too much operator context-switching,
2. slow incident or rollout review,
3. duplicated mental stitching across control-plane APIs,
4. risk that downstream teams over-rely on infrastructure dashboards and miss platform-governance
   truth.

Without this RFC:

1. the platform remains harder to operate than it needs to be,
2. governance truth is technically available but ergonomically weak,
3. future multi-app adoption will increase operator friction.

## Goals

1. Add a dedicated operator control-plane dashboard for `lotus-ai`.
2. Keep the dashboard API-first and derived from existing platform surfaces.
3. Make rollout, governance, readiness, and production-approval truth easier to inspect quickly.
4. Preserve separation between control-plane UI and full observability tooling.
5. Give operators one clear entry point for platform posture, use-case posture, and app-rollout
   posture.

## Non-Goals

1. Replacing Grafana, Datadog, Kibana, Sentry, or cloud monitoring stacks.
2. Building a generic BI or analytics dashboard for end users.
3. Creating a consumer-facing chat UI.
4. Re-implementing every platform API as bespoke UI-only logic.
5. Owning deep log search or arbitrary trace exploration in the custom dashboard.

## Decision

`lotus-ai` will add a dedicated operator control-plane dashboard.

This dashboard will:

1. read from existing platform APIs first,
2. focus on governed operator questions rather than raw infrastructure telemetry,
3. present clear platform, capability, use-case, and app-rollout posture,
4. link out to external observability tooling for deep metrics, logs, and traces.

The first implementation boundary is intentionally narrow:

1. platform posture overview,
2. domain control-plane pages,
3. production go-live and rollout review pages,
4. evidence and artifact drill-down links,
5. no attempt yet to reproduce full observability-product functionality inside the app.

## Operator Dashboard Model

The dashboard should have a small number of clear operator views.

### 1. Platform Overview

This page should answer:

1. is the platform running?
2. is it production-capable?
3. is it production-approved?
4. what major domains are degraded or blocked?

It should summarize:

1. runtime
2. provider posture
3. retrieval posture
4. async posture
5. resilience posture
6. production baseline
7. production go-live decision

### 2. Domain Control Pages

The dashboard should expose focused pages for:

1. providers and live execution
2. retrieval, ingestion, and corpus posture
3. evals and approval gates
4. async jobs and worker posture
5. safety and prompt governance
6. resilience and restore posture

These pages should surface control-plane truth, not all raw telemetry.

### 3. Capability and Use-Case Pages

The dashboard should expose:

1. capability-pack catalog and maturity
2. pack governance
3. first-use-case readiness and governance
4. named downstream production approval

This keeps product maturity, rollout posture, and production approval visible in one operator UI.

### 4. App-Rollout Pages

The dashboard should expose:

1. app-capability rollout catalog
2. pairing governance
3. onboarding templates
4. observability summary
5. lifecycle and retirement posture

This is especially important now that `RFC-0023` is implemented.

### 5. Evidence and Drill-Down Links

The dashboard should link operators to:

1. artifact descriptors
2. audit or evidence drill-down
3. incident bundles
4. external observability systems

The dashboard should be a review hub, not a data silo.

## Architecture Direction

### API-First UI

The dashboard must remain a UI over existing APIs.

Required behavior:

1. existing platform APIs remain the source of truth,
2. dashboard pages aggregate and visualize those APIs,
3. UI-specific logic should stay thin and avoid duplicating backend policy logic.

### Separation From Observability Tooling

The dashboard must not try to replace industry-standard tooling.

Required behavior:

1. logs remain in the logging or search stack,
2. metrics and alerts remain in observability systems,
3. traces remain in tracing tools,
4. the dashboard links to those systems when deep inspection is required.

### Role Focus

The first dashboard should be for:

1. platform operators,
2. AI-governance reviewers,
3. downstream app owners during rollout,
4. incident responders.

It should not initially target end users.

### Opinionated Navigation

The dashboard should favor operator questions over API taxonomy.

For example:

1. `Can this go live?`
2. `Why is this blocked?`
3. `Which domain is degraded?`
4. `Which app-capability pairings are active or paused?`
5. `What evidence supports this decision?`

This is more useful than simply mirroring the endpoint tree.

## Data and Operational Requirements

1. Every page must be backed by existing platform APIs or explicitly approved aggregations of them.
2. Dashboard health must not become a hidden dependency for platform correctness.
3. Operators must be able to navigate from dashboard summaries to evidence details.
4. The dashboard must distinguish blocked, degraded, limited-rollout, and production-approved
   states clearly.
5. The dashboard must not hide uncertainty or collapse separate governance domains into vague
   overall labels.

## Delivery Slices

### Slice 1: Overview and Navigation Foundation

Outcome:

1. one operator shell exists,
2. platform overview is available,
3. navigation reflects the current control-plane model.

Acceptance gate:

1. overview is powered by real platform APIs,
2. platform, production-baseline, and production-go-live states are clearly separated,
3. navigation is operator-oriented rather than endpoint-oriented.

### Slice 2: Domain Control Pages

Outcome:

1. provider, retrieval, eval, async, and resilience pages exist,
2. operators can inspect blocked and degraded posture by domain.

Acceptance gate:

1. domain pages use existing governance and runtime APIs,
2. the UI does not duplicate backend policy logic,
3. drill-down remains possible.

### Slice 3: Capability, Use-Case, and App-Rollout Pages

Outcome:

1. capability-pack pages exist,
2. first-use-case review is visible,
3. app-capability rollout governance is visible.

Acceptance gate:

1. capability maturity, production approval, and app rollout are not conflated,
2. app-specific blocked or paused posture is inspectable,
3. adoption templates and lifecycle posture are reachable.

### Slice 4: Evidence and External Observability Integration

Outcome:

1. dashboard links to artifacts and incident evidence,
2. operators can jump from summary state to external logs, metrics, or traces.

Acceptance gate:

1. the dashboard remains a control-plane hub,
2. deep infra inspection is delegated to the right external tools,
3. evidence paths are practical in incidents and rollout review.

## Risks

1. If the dashboard tries to replace observability tooling, it will become bloated and weaker than
   standard tools.
2. If the dashboard merely mirrors APIs without operator focus, it will add little value.
3. If UI aggregations drift from backend truth, operator trust will fall.
4. If rollout and governance states are over-collapsed, real blocking details may be hidden.

## Success Criteria

This RFC is successful when:

1. operators can answer the main platform-governance questions from one dashboard,
2. the dashboard reduces API-by-API manual stitching,
3. it complements rather than replaces standard observability practice,
4. multi-app rollout becomes easier to operate because posture is visible in one place.
