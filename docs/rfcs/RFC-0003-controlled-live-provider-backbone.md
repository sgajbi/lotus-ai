# RFC-0003: Controlled Live Provider Backbone

- Status: Proposed
- Date: 2026-03-22
- Owners: lotus-ai
- Requires Approval From: lotus-ai maintainers

## Summary

`lotus-ai` should implement a controlled live provider backbone as the next major platform phase.

This RFC moves provider execution from deterministic stub-only behavior to a governed live provider path for text generation, while keeping activation disabled by default until technical, operational, and evidence gates are satisfied.

The goal is to make `knowledge_answer.v1` and the broader task runtime capable of enterprise-grade live generation without weakening retrieval grounding, auditability, safety posture, or operational control.

## Why This Is Next

The platform now has the right foundation for this phase:

1. retrieval has a real governed backbone,
2. prompt, provider, retrieval, async, and evaluation governance surfaces already exist,
3. task execution is modular and auditable,
4. audit and evidence surfaces are materially useful,
5. the remaining major platform gap is real provider execution.

Retrieval came first because grounded enterprise behavior matters more than generation breadth. That ordering is now complete enough that the next highest-value move is controlled live provider activation.

## Problem Statement

Current provider behavior is still intentionally conservative:

1. supported provider modes are validated,
2. execution always routes through the deterministic stub provider,
3. provider governance surfaces describe activation, runbook, and evidence posture,
4. no real provider SDK path exists yet,
5. no live cost, timeout, retry, quota, or failover behavior exists yet.

This keeps the platform safe, but it also means `lotus-ai` is still not exercising the core live model-execution path that a shared AI platform ultimately needs.

## Goals

1. Introduce one governed live text-generation provider path.
2. Keep activation disabled by default until rollout criteria are met.
3. Preserve retrieval-first grounding and citation-first answer behavior.
4. Make provider execution bounded, observable, auditable, and testable.
5. Add explicit failure taxonomy, timeouts, retries, and operator-facing evidence.
6. Keep the provider layer modular enough to support future providers without premature abstraction.

## Non-Goals

1. Multi-provider rollout in the first implementation slice.
2. Broad provider marketplace abstraction before one real provider is proven.
3. Agentic/autonomous business actions.
4. Unbounded prompt experimentation without rollout controls.
5. Enabling embedding-provider activation in the same phase unless explicitly approved later.

## Current State

Today `lotus-ai` already has:

1. an explicit provider gateway,
2. deterministic stub-provider execution,
3. provider activation, runbook, evidence, and governance surfaces,
4. task execution evidence and audit persistence,
5. retrieval-backed answer support and refusal behavior,
6. evaluation fixtures for provider-policy posture,
7. platform runtime surfaces that already embed provider governance posture.

Those pieces should be retained and extended, not replaced.

## Decision

`lotus-ai` will implement live provider execution in controlled layers:

1. a provider adapter and policy layer,
2. a bounded live execution path for one allowlisted text-generation provider,
3. a rollout and operations layer that controls when the live path can be used.

The first live provider rollout should:

1. support text generation only,
2. remain disabled by default,
3. be enabled only through explicit reviewed configuration and governance evidence,
4. preserve the current stub path as the fallback and safe default.

## Architecture Direction

### Provider Adapter Layer

Add or extend:

1. a live provider adapter interface beside the stub provider,
2. explicit provider capability metadata,
3. request/response normalization for provider-specific payloads,
4. a provider failure taxonomy that preserves root-cause clarity.

### Execution Controls

Live provider execution must include:

1. bounded request timeouts,
2. retry rules with explicit safe-retry boundaries,
3. request-size and token budgeting,
4. rate-limit and quota controls,
5. fallback behavior when the live path is unavailable or blocked.

### Audit and Evidence

The live path must preserve:

1. provider execution mode,
2. provider identifier and model identifier,
3. timeout/retry/failure posture,
4. token and cost accounting where available,
5. enough structured evidence for support review and rollout governance.

### Safety and Grounding

The provider backbone must not weaken existing controls:

1. retrieval-backed answers remain citation-first,
2. unsupported retrieval answers still refuse conservatively,
3. safety posture remains explicit and inspectable,
4. live generation must not bypass task-level output contracts.

## Data and Operational Requirements

1. Live provider activation remains disabled by default until governance gates are satisfied.
2. The configured live provider must be allowlisted explicitly.
3. Missing credentials or blocked rollout state must fail clearly.
4. Operational runbooks must exist for rate limits, outages, degraded fallback, and cost anomalies.
5. Provider execution telemetry must be inspectable without reading raw SDK logs.
6. CI and evaluation assets must cover provider failure and fallback behavior, not only happy-path execution.

## Delivery Slices

### Slice 1: Provider Adapter and Mode Contracts

Outcome:

1. a real live-provider adapter seam exists beside the stub path,
2. provider mode and provider identifier semantics are explicit,
3. provider failure taxonomy is introduced.

Acceptance gate:

1. no live provider is enabled yet,
2. contracts are stable and tested,
3. the gateway is cleaner and more modular than the current stub-only branch.

### Slice 2: Controlled Live Text Generation Path

Outcome:

1. one allowlisted live provider is integrated for text generation,
2. the path remains disabled by default,
3. configuration explicitly distinguishes stub, blocked-live, and enabled-live execution.

Acceptance gate:

1. unsupported or unapproved modes fail clearly,
2. stub fallback remains intact,
3. no hidden runtime enablement exists.

### Slice 3: Execution Hardening

Outcome:

1. provider timeouts, retries, and request bounds are enforced,
2. token and cost metadata are captured where available,
3. failure classification is explicit and auditable.

Acceptance gate:

1. timeout and failure paths are directly tested,
2. audit evidence preserves execution posture,
3. operator-facing runtime surfaces reflect the live path honestly.

### Slice 4: Task Runtime Integration

Outcome:

1. approved tasks can route through the live provider path when rollout allows it,
2. retrieval-backed tasks still preserve citation-first behavior,
3. provider execution is reflected in task runtime and evidence summaries.

Acceptance gate:

1. retrieval-backed answers do not regress in support/refusal posture,
2. non-retrieval tasks remain contract-bound,
3. task audit and evidence surfaces remain clear.

### Slice 5: Evaluation and Failure-Mode Evidence

Outcome:

1. provider eval fixtures cover success, timeout, rejection, and fallback behavior,
2. evidence readiness reflects real live-provider risks rather than only policy posture,
3. provider activation is blocked until meaningful evidence exists.

Acceptance gate:

1. provider evaluation assets are file-backed and governed,
2. failure-mode evidence is visible in provider governance posture,
3. CI gates protect core provider contracts.

### Slice 6: Operational Activation Readiness

Outcome:

1. runbooks and rollout posture reflect the real live provider path,
2. observability, quota handling, and incident response expectations are explicit,
3. the platform can eventually move from disabled-by-default to governed activation.

Acceptance gate:

1. provider governance remains blocked until the required runbook items are complete,
2. runtime status exposes live-provider posture honestly,
3. the activation path is reviewable end to end.

## Risks

1. live provider execution can create operational volatility through latency, outages, and rate limits,
2. cost visibility can lag actual usage if token accounting is treated as optional,
3. weak fallback behavior can make the platform harder to debug than the current stub path,
4. live generation can weaken enterprise trust if it is activated before retrieval grounding and safety controls remain clearly enforced.

## Alternatives Considered

### Alternative 1: Continue Stub-Only Execution Longer

Rejected as the next major phase.

Reason:

1. the platform would remain structurally strong but functionally incomplete,
2. downstream Lotus apps need a real provider path to validate shared AI value.

### Alternative 2: Enable Multiple Providers Immediately

Rejected for now.

Reason:

1. multi-provider breadth adds complexity before one provider path is proven,
2. one high-quality governed provider path is the right first enterprise move.

### Alternative 3: Activate Embedding Providers in the Same RFC

Deferred.

Reason:

1. retrieval already has a functional deterministic preview-vector path,
2. text-generation rollout is the higher-value and higher-risk next phase,
3. embedding-provider activation can be handled as a follow-on slice if still needed.

## Acceptance Criteria

This RFC is complete when:

1. one live text-generation provider path exists behind the provider gateway,
2. that path is disabled by default and allowlisted explicitly,
3. task execution can use the live provider path only when rollout posture permits it,
4. provider audit and evidence surfaces preserve meaningful execution detail,
5. provider failure, timeout, and fallback behavior are evaluated and governed,
6. provider operations and rollout readiness are documented and reviewable,
7. the platform remains retrieval-grounded and citation-first where applicable.

## Approval Requested

Approve this RFC if the team agrees that:

1. controlled live provider execution is the next major platform phase,
2. rollout should begin with one governed text-generation provider only,
3. activation must remain disabled by default until technical, evidence, and runbook gates are satisfied,
4. retrieval grounding and citation-first behavior must remain stronger priorities than generative breadth.
