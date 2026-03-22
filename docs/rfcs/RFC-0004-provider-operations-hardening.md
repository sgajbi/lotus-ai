# RFC-0004: Provider Operations Hardening

- Status: Implemented
- Date: 2026-03-23
- Owners: lotus-ai

## Summary

`lotus-ai` should harden live-provider operations before any broader provider rollout is treated as enterprise-ready.

RFC-0003 established the controlled live-provider backbone:

1. a real allowlisted live-provider adapter exists,
2. rollout posture, credentials, and task-level allowlisting are explicit,
3. provider execution evidence now captures token and estimated-cost metadata,
4. activation remains disabled by default unless governed controls permit it.

That is necessary, but not sufficient for gold-standard activation.

The next phase must make the live-provider path operationally governable under real load by adding:

1. task and caller-aware quota controls,
2. spend guardrails and budget signals,
3. structured provider observability and incident evidence,
4. explicit degradation and circuit-breaker posture,
5. operator-facing visibility for quota and budget state.

## Why This Is Next

The platform now has:

1. governed retrieval,
2. a real live-provider execution seam,
3. explicit provider rollout posture,
4. audit and execution evidence,
5. good CI and RFC discipline.

The highest-value remaining provider gap is not another adapter. It is runtime operations control.

Without that layer:

1. live-provider enablement is difficult to trust under bursty caller behavior,
2. cost anomalies are visible too late,
3. incident response depends on scattered evidence rather than operator-grade summaries,
4. bank-grade rollout remains more theoretical than real.

## Problem Statement

Current provider behavior is technically governed, but not yet operationally hardened enough for broad enterprise activation:

1. there is no first-class quota contract per task or caller,
2. token/cost data is emitted but not compared against configured budgets,
3. there is no operator-facing budget or spend-status summary,
4. there is no structured circuit-breaker or degraded-upstream posture,
5. provider observability remains execution-local rather than summarized as runtime operations posture.

This means the live-provider path exists, but its production control plane is still too thin.

## Goals

1. Introduce bounded quota controls for live provider usage.
2. Introduce spend-guardrail contracts and operator-facing budget posture.
3. Make degraded-upstream and circuit-breaker posture explicit and inspectable.
4. Improve incident-review evidence for provider failures and throttling.
5. Keep all new behavior task-bounded, reviewable, and disabled by default unless configured.

## Non-Goals

1. Multi-provider marketplace rollout.
2. Full billing integration with external finance systems.
3. Background optimization or autoscaling work not directly tied to provider control posture.
4. Replacing existing provider governance surfaces with a new parallel model.

## Current State

Today `lotus-ai` already has:

1. a real OpenAI live text provider seam,
2. explicit provider rollout and configuration posture,
3. token and estimated-cost capture on live provider responses,
4. provider activation, runbook, evidence, and governance views,
5. task-runtime visibility into stubbed, blocked, and live provider posture.

Those should remain and be extended, not replaced.

## Decision

`lotus-ai` will introduce a provider operations control layer on top of the RFC-0003 backbone.

This layer should make provider activation operationally honest by modeling:

1. quota state,
2. budget state,
3. degradation state,
4. incident-review evidence,
5. runtime operator summaries.

The first implementation should stay intentionally narrow:

1. one live text-generation provider only,
2. one family of bounded quota policies,
3. one spend-guardrail model,
4. no hidden auto-enable behavior.

The default rollout posture must remain safe:

1. quota enforcement can exist before live-provider activation expands,
2. budget posture can block execution even when credentials are present,
3. degraded-upstream posture must never be reported as healthy live readiness,
4. no operator summary may imply that a blocked live path is healthy just because the stub path still works.

## Rollout State Model

This RFC extends provider posture with operational sub-states that sit alongside the existing rollout model from RFC-0003.

Provider operations status must distinguish:

1. `NORMAL`
2. `OPERATIONS_INVALID`
3. `QUOTA_BLOCKED`
4. `BUDGET_SOFT_LIMIT`
5. `BUDGET_BLOCKED`
6. `DEGRADED_UPSTREAM`
7. `CIRCUIT_OPEN`
8. `ROLLOUT_BLOCKED`

These states are operator-facing truth states. They must not be inferred from prose or reconstructed ad hoc from unrelated endpoints.

## Architecture Direction

### Quota Controls

Add:

1. task-level request quotas,
2. caller-app quota posture,
3. tenant-aware quota posture where tenant context exists,
3. bounded rejection behavior when quota is exceeded,
4. operator-facing quota summaries.

Quotas should remain governed configuration, not implicit code constants scattered across services.

The first delivery may use deterministic in-process counters if needed, but the contract must make the enforcement model explicit so future persistence does not break external behavior.

### Spend Guardrails

Add:

1. configured soft and hard budget posture for live-provider execution,
2. structured budget-state summaries,
3. explicit rejection or degrade behavior when hard budget posture is reached,
4. operator-facing evidence showing current spend posture and blocking reasons.

Budget posture must be based on structured usage accounting already emitted by the live-provider path. It must not depend on free-form log parsing or best-effort heuristics hidden from operator views.

### Degradation and Circuit-Breaker Posture

Add:

1. explicit upstream health posture for provider execution,
2. failure-window counters or equivalent bounded degraded state,
3. circuit-breaker summaries that distinguish normal, degraded, and blocked provider posture,
4. explicit fallback or rejection behavior when upstream health is unsafe.

The first implementation should prefer explicit rejection over silent rerouting. If a task falls back to a stub path, that fallback must be reflected plainly in runtime and evidence surfaces.

### Observability and Incident Evidence

Add:

1. provider operations summaries built from structured provider execution evidence,
2. runtime visibility into rate-limit, timeout, upstream-error, and quota-rejection counts,
3. enough structured incident-review evidence to explain why the provider path is blocked or degraded,
4. no raw secret-bearing provider telemetry.

Observability must stay redacted-by-default:

1. no credential material in logs, audit records, or runtime summaries,
2. no raw provider response payload persistence beyond approved evidence fields,
3. incident evidence should preserve classification and counters, not unrestricted body dumps.

## Data and Operational Requirements

1. Quota and budget posture must be inspectable before activation expands.
2. Exceeded quota or hard-budget states must fail clearly.
3. Operator-facing provider status must distinguish:
   - normal
   - degraded
   - quota-blocked
   - budget-blocked
   - rollout-blocked
4. CI and eval assets must cover quota and budget failure behavior.
5. Runbooks must explicitly describe spend-anomaly response and provider-throttling response.
6. Operator summaries must clearly separate:
   - configured limits
   - current usage posture
   - current blocking posture
7. Failure accounting windows and reset semantics must be documented and testable.

## Delivery Slices

### Slice 1: Provider Quota Contracts

Outcome:

1. task and caller-aware provider quota contracts exist,
2. quota posture is separated from provider rollout posture,
3. exceeded quota behavior is explicit and typed,
4. quota configuration surfaces make the enforcement scope visible.

Acceptance gate:

1. no silent quota fallback exists,
2. contracts are stable and tested,
3. operator surfaces can inspect configured quota posture,
4. malformed quota configuration fails clearly.

### Slice 2: Spend Guardrail Contracts

Outcome:

1. provider budget posture is modeled explicitly,
2. soft and hard budget states are inspectable,
3. hard-budget behavior is explicit and reviewable,
4. usage-to-budget comparison semantics are documented.

Acceptance gate:

1. budget state does not depend on hidden local-only logic,
2. audit/evidence surfaces preserve blocking reasons,
3. tests cover below-budget and blocked-budget paths,
4. soft-limit behavior is distinguishable from hard blocking.

### Slice 3: Provider Operations Runtime Status

Outcome:

1. provider operations status is exposed as a dedicated operator view,
2. quota, budget, and degradation posture are summarized together,
3. platform runtime status embeds that posture,
4. top-level state transitions are explicit.

Acceptance gate:

1. runtime/operator views are truthful,
2. blocked reasons are explicit,
3. no duplicate summary logic exists across services,
4. rollout-blocked and operations-blocked are distinct.

### Slice 4: Degradation and Circuit-Breaker Controls

Outcome:

1. degraded-upstream posture is modeled explicitly,
2. repeated failures can drive a blocked or degraded state,
3. fallback or rejection behavior is explicit when upstream health is unsafe,
4. reset semantics are deliberate and documented.

Acceptance gate:

1. failure escalation logic is directly tested,
2. operator summaries distinguish degradation from quota or budget blocks,
3. evidence remains structured and incident-reviewable,
4. timeout, upstream-error, and rate-limit paths are classified separately.

### Slice 5: Evaluation and Runbook Hardening

Outcome:

1. eval fixtures cover quota, budget, and degraded-upstream behavior,
2. runbooks include spend anomalies and provider throttling response,
3. provider governance reflects the new operations-hardening requirements,
4. recorded eval evidence reflects the new provider operations seams.

Acceptance gate:

1. eval assets are file-backed and governed,
2. runbook expectations are explicit,
3. provider governance remains blocked until required operational evidence is complete,
4. eval seam summaries and run artifacts stay aligned with implementation reality.

## Risks

1. overcomplicated quota logic can make rollout harder to reason about,
2. weak budget posture can create false operator confidence,
3. poor degradation semantics can blur the distinction between blocked rollout and transient upstream failure,
4. duplicated operator summaries can create conflicting truth,
5. overly permissive evidence capture can create data-handling risk.

## Alternatives Considered

### Alternative 1: Activate More Tasks First

Rejected.

Reason:

1. activation breadth without stronger runtime controls would reduce operational safety,
2. the provider path should become safer before it becomes broader.

### Alternative 2: Delay Operations Hardening Until Real Production Traffic

Rejected.

Reason:

1. bank-grade posture requires controls before production pressure arrives,
2. retrofitting quota and spend semantics later would create avoidable churn.

## Acceptance Criteria

This RFC is complete when:

1. provider quota posture is explicit and inspectable,
2. provider budget posture is explicit and inspectable,
3. provider operations runtime summaries show quota, budget, and degradation truthfully,
4. degraded-upstream behavior is explicit and tested,
5. eval and runbook assets cover the new operations-hardening behavior,
6. provider governance incorporates these operational controls cleanly,
7. operator-facing state models do not overstate health or readiness,
8. all new controls remain disabled-by-default unless explicitly configured.

## Implementation Notes

RFC-0004 has been implemented in five slices:

1. Slice 1 added provider quota contracts, operator quota inspection, and live-path quota enforcement.
2. Slice 2 added provider budget policy contracts, spend posture inspection, and hard-budget execution blocking.
3. Slice 3 added a dedicated provider operations status view and embedded that posture into platform runtime status.
4. Slice 4 added degraded-upstream classification, circuit-breaker behavior, and structured degradation evidence.
5. Slice 5 added governed eval assets, recorded run artifacts, and runbook/evidence requirements for provider operations posture.

The resulting provider operations layer now exposes:

1. `GET /platform/providers/quota-policy`
2. `GET /platform/providers/budget-policy`
3. `GET /platform/providers/operations-status`

The platform runtime summary also embeds provider operations posture directly, and provider governance now reflects quota, budget, degradation, eval, and runbook readiness truthfully.
