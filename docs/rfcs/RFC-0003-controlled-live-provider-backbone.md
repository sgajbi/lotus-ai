# RFC-0003: Controlled Live Provider Backbone

- Status: In Progress
- Date: 2026-03-22
- Owners: lotus-ai

## Summary

`lotus-ai` should implement a controlled live provider backbone as the next major platform phase.

This RFC moves provider execution from a pure stub-only foundation posture to a governed live-provider backbone for text generation, while intentionally keeping activation disabled by default until technical, operational, and evidence gates are satisfied.

The goal is to make `knowledge_answer.v1` and the broader task runtime capable of enterprise-grade live generation without weakening retrieval grounding, auditability, safety posture, or operational control.

The implementation so far has established the controlled live-provider seam, rollout-state contracts, execution hardening, task-runtime integration, evaluation evidence, and operational activation-readiness posture. It has not yet completed the core live-provider execution goal, which remains the most important closure gap for this RFC.

## Why This Is Next

The platform now has the right foundation for this phase:

1. retrieval has a real governed backbone,
2. prompt, provider, retrieval, async, and evaluation governance surfaces already exist,
3. task execution is modular and auditable,
4. audit and evidence surfaces are materially useful,
5. the remaining major platform gap is real provider execution.

Retrieval came first because grounded enterprise behavior matters more than generation breadth. That ordering is now complete enough that the next highest-value move is controlled live provider activation.

## Problem Statement

The original problem was that provider behavior was intentionally conservative:

1. supported provider modes are validated,
2. execution always routes through the deterministic stub provider,
3. provider governance surfaces describe activation, runbook, and evidence posture,
4. no real provider SDK path exists yet,
5. no live cost, timeout, retry, quota, or failover behavior exists yet.

This kept the platform safe, but it also meant `lotus-ai` was not yet exercising the core live model-execution path that a shared AI platform ultimately needs.

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

The first live provider rollout should also be intentionally narrow:

1. one provider integration,
2. one allowlisted model family at first,
3. task-level allowlisting rather than blanket service-wide enablement,
4. no silent drift from stubbed execution to live execution.

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

Fallback must remain explicit:

1. approved tasks may use an explicit reviewed fallback path,
2. blocked live rollout must not silently masquerade as successful live execution,
3. operator-facing surfaces must make stubbed, blocked, and live execution distinguishable.

### Audit and Evidence

The live path must preserve:

1. provider execution mode,
2. provider identifier and model identifier,
3. timeout/retry/failure posture,
4. token and cost accounting where available,
5. enough structured evidence for support review and rollout governance.

Audit behavior must also remain bank-grade:

1. credentials and provider secrets must never be persisted,
2. prompt/system content must remain governed by existing prompt and audit posture rather than raw provider SDK logging,
3. provider response evidence must be structured enough for incident review without requiring replay against the live provider.

### Safety and Grounding

The provider backbone must not weaken existing controls:

1. retrieval-backed answers remain citation-first,
2. unsupported retrieval answers still refuse conservatively,
3. safety posture remains explicit and inspectable,
4. live generation must not bypass task-level output contracts.

### Configuration and Secret Handling

Live provider activation must also define:

1. credential source-of-truth and environment handling,
2. explicit startup/readiness behavior when credentials are missing or malformed,
3. redaction rules for provider-related operational telemetry,
4. configuration surfaces that separate supported provider modes from enabled rollout state.

### Rollout States

Provider rollout should be treated as an explicit progression:

1. `DOCUMENTED_ONLY`
2. `STUB_DEFAULT`
3. `ALLOWLISTED_DISABLED`
4. `CANARY_ENABLED`
5. `ROLLED_OUT`

The implementation does not need to expose those exact labels immediately, but the rollout model should remain this explicit in behavior and governance.

## Data and Operational Requirements

1. Live provider activation remains disabled by default until governance gates are satisfied.
2. The configured live provider must be allowlisted explicitly.
3. Missing credentials or blocked rollout state must fail clearly.
4. Operational runbooks must exist for rate limits, outages, degraded fallback, and cost anomalies.
5. Provider execution telemetry must be inspectable without reading raw SDK logs.
6. CI and evaluation assets must cover provider failure and fallback behavior, not only happy-path execution.
7. Task-level routing into live provider execution must be reviewable and bounded.
8. Activation must preserve a deterministic fallback or refusal posture for blocked-live cases.

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

### Slice 2: Credential, Configuration, and Rollout-State Contracts

Outcome:

1. live-provider credentials and configuration posture are modeled explicitly,
2. rollout state is separated from supported provider mode,
3. startup/readiness behavior for malformed or missing provider configuration is defined.

Acceptance gate:

1. missing or invalid credentials fail clearly,
2. no secret material appears in logs, runtime status, or audit records,
3. rollout state remains inspectable before any live task execution is possible.

### Slice 3: Controlled Live Text Generation Path

Outcome:

1. one allowlisted live provider is integrated for text generation,
2. the path remains disabled by default,
3. configuration explicitly distinguishes stub, blocked-live, and enabled-live execution.

Acceptance gate:

1. unsupported or unapproved modes fail clearly,
2. stub fallback remains intact,
3. no hidden runtime enablement exists.

### Slice 4: Execution Hardening

Outcome:

1. provider timeouts, retries, and request bounds are enforced,
2. token and cost metadata are captured where available,
3. failure classification is explicit and auditable.

Acceptance gate:

1. timeout and failure paths are directly tested,
2. audit evidence preserves execution posture,
3. operator-facing runtime surfaces reflect the live path honestly.

### Slice 5: Task Runtime Integration

Outcome:

1. approved tasks can route through the live provider path when rollout allows it,
2. retrieval-backed tasks still preserve citation-first behavior,
3. provider execution is reflected in task runtime and evidence summaries.

Acceptance gate:

1. retrieval-backed answers do not regress in support/refusal posture,
2. non-retrieval tasks remain contract-bound,
3. task audit and evidence surfaces remain clear.

### Slice 6: Evaluation and Failure-Mode Evidence

Outcome:

1. provider eval fixtures cover success, timeout, rejection, and fallback behavior,
2. evidence readiness reflects real live-provider risks rather than only policy posture,
3. provider activation is blocked until meaningful evidence exists.

Acceptance gate:

1. provider evaluation assets are file-backed and governed,
2. failure-mode evidence is visible in provider governance posture,
3. CI gates protect core provider contracts.

### Slice 7: Operational Activation Readiness

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
5. provider credential handling can create avoidable risk if secret-management and audit-redaction rules are not explicit from the first slice.

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

### Alternative 4: Service-Wide Live Provider Enablement

Rejected.

Reason:

1. bank-grade rollout should be task-bounded and reviewable,
2. service-wide enablement would make fallback, evaluation, and support posture too coarse.

## Acceptance Criteria

## What Has Been Implemented

Implemented scope under RFC-0003 includes:

1. a real provider adapter seam beside the stub path,
2. explicit provider mode, adapter-kind, failure-category, and rollout-state contracts,
3. explicit live-provider configuration and credential posture without exposing secret material,
4. bounded provider execution controls for timeout, retry, and output-token budget,
5. task-runtime integration that now distinguishes retrieval-backed, stubbed provider-backed, blocked provider-backed, and allowlisted-but-disabled provider posture honestly,
6. provider evaluation fixtures covering policy, runtime, and failure-mode behavior,
7. provider evidence readiness grounded in staged eval assets and recorded regression runs,
8. provider operational activation readiness that explicitly includes incident response, rollback, observability, and quota-handling expectations.

## Remaining Closure Gaps

RFC-0003 should not be treated as complete yet because these material gaps still remain:

1. there is still no real allowlisted live text-generation adapter integrated behind the provider gateway; the current documented live-provider adapter is a governed rejection seam, not an executable live path,
2. provider policy still only permits `disabled` and `stub` modes for text generation, so the configured live rollout state cannot yet drive a real live-provider execution path,
3. task-level allowlisting for live provider execution is not implemented yet, even though the RFC explicitly called for bounded task-level rollout rather than blanket service-wide enablement,
4. token and cost accounting are still not preserved in provider contracts or provider execution evidence, even though the RFC called for those fields where available.

## Acceptance Criteria

This RFC will be complete when:

1. one live text-generation provider path exists behind the provider gateway,
2. that path is disabled by default and allowlisted explicitly,
3. task execution can use the live provider path only when rollout posture permits it,
4. provider audit and evidence surfaces preserve meaningful execution detail,
5. provider failure, timeout, and fallback behavior are evaluated and governed,
6. credentials, rollout state, and startup/readiness behavior are explicit and inspectable,
7. provider operations and rollout readiness are documented and reviewable,
8. the platform remains retrieval-grounded and citation-first where applicable.
