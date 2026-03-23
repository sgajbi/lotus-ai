# RFC-0018: Governed Embeddings and Provider Expansion

- Status: Draft
- Date: 2026-03-23
- Owners: lotus-ai
- Requires Approval From: lotus-ai maintainers

## Summary

`lotus-ai` should expand the provider backbone beyond the current single text-generation live path by introducing governed embedding execution and a bounded multi-provider expansion model.

The platform now has:

1. a controlled live text-generation path,
2. durable provider operations controls,
3. retrieval activation and safety/runtime governance sequences,
4. evaluation, observability, artifact, and deployment evolution paths.

But the provider layer is still materially incomplete for the next phase of platform maturity:

1. embeddings remain `disabled` or `stub` only,
2. retrieval activation still depends on reviewed future embedding rollout,
3. provider breadth is still narrower than the platform runtime now requires.

## Why This Is Next

Current code and docs make the gap explicit:

1. [provider_policy.py](C:/Users/Sandeep/projects/lotus-ai/src/app/services/provider_policy.py#L1) allows `openai` only for text generation, while embeddings are limited to `disabled` and `stub`,
2. [provider_catalog.py](C:/Users/Sandeep/projects/lotus-ai/src/app/services/provider_catalog.py#L1) exposes only `embeddings.stub`,
3. [retrieval_activation_readiness.py](C:/Users/Sandeep/projects/lotus-ai/src/app/services/retrieval_activation_readiness.py#L1) explicitly calls out embedding-provider execution as part of future retrieval rollout,
4. [README.md](C:/Users/Sandeep/projects/lotus-ai/README.md#L1) still says live retrieval search remains disabled until embeddings and vector indexing are wired.

This means the provider platform is still asymmetric:

1. text generation has a real governed live path,
2. embeddings do not,
3. multi-provider growth is still not formally governed.

## Problem Statement

`lotus-ai` is now approaching a stage where:

1. live retrieval activation needs real embedding execution,
2. provider resilience and cost posture will eventually benefit from bounded provider breadth,
3. later production use cases and deployment splits will need a clearer provider expansion model.

Without this RFC:

1. retrieval remains artificially blocked on provider incompleteness,
2. embedding rollout may happen piecemeal rather than through the same governance standard as text generation,
3. future provider expansion risks becoming reactive and inconsistent.

## Goals

1. Introduce a governed live embedding-provider path.
2. Extend provider policy, catalog, and operations posture to cover embeddings honestly.
3. Define a bounded multi-provider expansion model for later phases.
4. Reuse the same rollout, evidence, runbook, and governance discipline already applied to live text generation.
5. Keep expansion incremental and bank-grade rather than broad and speculative.

## Non-Goals

1. Enabling many providers at once.
2. Building a generic provider marketplace.
3. Treating embeddings as an ungoverned implementation detail.
4. Broad model experimentation outside bounded rollout control.
5. Replacing the existing controlled text-generation path.

## Current State

The provider layer already supports:

1. governed text-generation provider catalog and policy,
2. live-provider rollout posture,
3. quota, budget, degradation, and operations controls,
4. runtime-backed evaluation evidence for provider behavior.

The missing pieces are:

1. live embedding-provider execution,
2. embedding-specific rollout and operations posture,
3. a formal policy for later provider-family expansion.

## Decision

`lotus-ai` will implement governed embedding-provider activation and a bounded provider expansion model.

The first implementation should:

1. add one governed live embedding path,
2. keep it disabled by default until the same evidence, runbook, and operational gates are satisfied,
3. extend provider policy and catalog contracts so embeddings are first-class rather than stub-only,
4. define how later provider additions are evaluated without opening broad provider sprawl,
5. keep task and retrieval runtime behavior truthful during rollout.

## State Model and Invariants

This RFC establishes the following invariants:

1. embedding-provider execution must remain governed separately from text-generation execution,
2. provider catalog and policy must describe embedding rollout truthfully,
3. retrieval runtime must not imply live embedding execution unless the provider path is actually active,
4. provider operations, evidence, and runbook posture must not overstate embedding readiness,
5. later provider additions must remain bounded and reviewable rather than opportunistic.

## Architecture Direction

### Embedding Provider Backbone

Introduce one real governed embedding-provider path.

Required behavior:

1. provider catalog exposes embedding provider identity, adapter kind, lifecycle status, and rollout posture explicitly,
2. provider policy supports live embedding mode as a bounded allowed mode,
3. runtime selection remains typed and inspectable,
4. failure semantics remain explicit and conservative.

### Retrieval and Embedding Convergence

Embedding rollout should serve retrieval directly.

Required behavior:

1. retrieval activation can depend on actual embedding-provider posture rather than only a future placeholder,
2. retrieval indexing and live search surfaces describe embedding readiness truthfully,
3. embedding execution evidence can be tied to retrieval approval posture,
4. retrieval runtime does not hide embedding-provider degradation or blocking posture.

### Provider Expansion Governance

Going beyond one text provider and one embedding provider should be governed, not assumed.

Required behavior:

1. expansion criteria for later providers are explicit,
2. provider catalog and policy can express multiple bounded providers without ambiguity,
3. cost, degradation, fallback, and rollout posture stay reviewable,
4. no new provider can bypass the existing operational and evidence gates.

### Runbook and Evidence Convergence

Embeddings and provider expansion should use the same bank-grade discipline as text generation.

Required behavior:

1. embedding-provider runbook readiness is explicit,
2. embedding-provider evaluation evidence is runtime-backed,
3. governance surfaces include embedding posture honestly,
4. observability and artifact flows can support provider expansion safely.

## Data and Operational Requirements

1. Embedding-provider execution must have explicit quota, budget, and degradation posture where relevant.
2. Provider catalog and policy must remain authoritative for both text and embeddings.
3. Retrieval runtime must reflect embedding dependency truthfully.
4. Evaluation evidence must cover embedding behavior before activation.
5. SQL-backed and integration tests must prove provider and retrieval convergence behavior.
6. Runbooks must define activation, rollback, degraded-mode, and incident response for embedding execution.

## Delivery Slices

### Slice 1: Embedding Provider Contracts and Catalog/Policy Upgrade

Outcome:

1. embeddings become a first-class provider capability in policy and catalog,
2. one live embedding-provider seam exists,
3. runtime behavior remains disabled by default.

Acceptance gate:

1. provider contracts are explicit,
2. policy and catalog remain truthful,
3. unit tests cover embedding capability posture,
4. no silent retrieval behavior change is introduced.

### Slice 2: Governed Live Embedding Execution

Outcome:

1. one bounded live embedding-provider path becomes available,
2. retrieval indexing/search rollout can consume it,
3. failures remain conservative and reviewable.

Acceptance gate:

1. embedding execution is real and bounded,
2. retrieval-related provider behavior is truthful,
3. integration tests cover successful and blocked embedding paths,
4. operations posture remains coherent.

### Slice 3: Evaluation, Operations, and Governance Upgrade

Outcome:

1. embedding-provider evaluation families exist,
2. runbook, evidence, and governance surfaces include embedding readiness,
3. rollout review becomes complete for retrieval/provider convergence.

Acceptance gate:

1. embedding evidence is runtime-backed,
2. runbook posture is explicit,
3. governance distinguishes staged, partial, pass, fail, and stale embedding posture,
4. the platform can review retrieval activation against real provider dependency evidence.

### Slice 4: Bounded Multi-Provider Expansion Model

Outcome:

1. later provider additions have an explicit governance model,
2. catalog, policy, and operations surfaces can support bounded provider breadth,
3. provider expansion remains disciplined.

Acceptance gate:

1. expansion rules are explicit,
2. provider breadth does not weaken control-plane clarity,
3. tests cover multi-provider policy semantics,
4. the platform is materially closer to a mature shared-provider layer.

## Risks

1. provider breadth could outpace governance maturity,
2. embeddings could be activated without enough operational evidence,
3. retrieval and provider status could drift if dependency posture is not modeled carefully,
4. multi-provider support could create complexity without enough immediate product value.

## Alternatives Considered

### Alternative 1: Keep Embeddings Stub-Only Longer

Rejected as the long-term posture.

Reason:

1. retrieval activation increasingly depends on real embedding execution,
2. the provider platform should not remain text-only once retrieval is live.

### Alternative 2: Activate Embeddings Ad Hoc Inside Retrieval Work

Rejected.

Reason:

1. embedding execution is part of the provider platform, not just a retrieval implementation detail,
2. it should inherit the same governance, operations, and evaluation model.

### Alternative 3: Add Many Providers First, Then Govern Them Later

Rejected.

Reason:

1. it would weaken the platform’s control-plane discipline,
2. bounded expansion is the only defensible path for an enterprise shared service.

## Acceptance Criteria

This RFC is complete when:

1. embeddings are a first-class governed provider capability,
2. one real live embedding-provider path exists under explicit rollout controls,
3. retrieval runtime can depend on embedding-provider posture truthfully,
4. evaluation, runbook, and governance surfaces cover embedding execution,
5. later provider expansion has an explicit bounded governance model,
6. the platform is materially closer to a mature shared-provider architecture.

## Approval Requested

Approve this RFC if the team agrees that:

1. governed embeddings and provider expansion are the next provider-platform gap after the current runtime/control-plane sequence,
2. embedding execution should be treated as a first-class provider concern rather than a hidden retrieval detail,
3. provider breadth should remain bounded and evidence-driven,
4. delivery should proceed in the slices defined above.
