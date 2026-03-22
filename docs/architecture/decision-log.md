# Decision Log

This file records the core architectural decisions for `lotus-ai` in a concise format.

## Decision 1: Separate AI Platform Service

Decision:

`lotus-ai` is a separate Lotus application rather than embedding all AI capability directly into every Lotus repo.

Why:

1. central prompt and safety governance,
2. shared auditability,
3. reusable retrieval and evaluation tooling,
4. lower duplication across apps.

Trade-off:

Requires careful ownership discipline so the service does not absorb business logic.

## Decision 2: Domain Apps Keep Business Ownership

Decision:

Each Lotus app keeps ownership of the business meaning of AI features that touch its workflows.

Why:

1. domain services understand their own semantics,
2. deterministic systems remain authoritative,
3. AI remains assistive rather than authoritative.

## Decision 3: Build Contract-First

Decision:

Introduce capability and task contracts before real provider integrations.

Why:

1. easier integration with downstream apps,
2. clearer versioning and testing,
3. avoids provider-driven architecture drift.

## Decision 4: Start With Explanation and Retrieval

Decision:

Initial business-facing AI value should come from explanation, summarization, retrieval, and drafting.

Why:

1. lower risk,
2. high user value,
3. fits well with Lotus deterministic services,
4. easier to govern in a banking context.

## Decision 5: Enterprise-Grade Controls, Startup-Grade Scope

Decision:

Use bank-grade engineering controls, but keep the actual feature scope narrow and incremental.

Why:

1. target customers require strong governance,
2. startup constraints require disciplined sequencing rather than big-bang builds.

## Decision 6: No Large AI Framework as the Core Architecture

Decision:

Do not make a large AI framework the primary architectural foundation of `lotus-ai`.

Why:

1. we need explicit control over contracts, safety, auditability, and request flow,
2. framework abstractions can hide important behavior,
3. bank-grade platform services need clarity over convenience,
4. our current use cases do not justify an agent-first architecture.

Allowed use:

Frameworks or helper libraries may be used in narrow internal roles where they reduce plumbing without taking over the service design.

## Decision 7: LangGraph Is Deferred, Not Rejected

Decision:

LangGraph is deferred from the initial implementation of `lotus-ai`.

Why:

1. early `lotus-ai` slices are contract-first and explanation-first,
2. graph orchestration is not yet the main bottleneck,
3. we should first prove the need for multi-step agent workflows with real usage evidence.

Future position:

LangGraph can be reconsidered for bounded internal orchestration later, especially for async multi-step flows, but it should remain an implementation detail rather than the public platform architecture.

## Decision 8: Startup and Readiness Policies Are Separate Controls

Decision:

`lotus-ai` treats startup blocking policy and readiness-probe degradation policy as separate operational controls.

Why:

1. some environments need visibility without startup failure,
2. enterprise environments need stricter rollout behavior,
3. orchestration signaling and startup permissiveness solve different problems,
4. separating them keeps policy explicit instead of embedding assumptions in one switch.

Current target posture:

1. local development: `warn` + `observe`
2. shared integration: `warn` + `degrade`
3. enterprise / production-like: `enforce` + `degrade`

## Decision 9: Prompt Promotion Is Read-Only at Runtime

Decision:

Prompt definitions in `lotus-ai` are inspectable through APIs, but runtime mutation and promotion remain disabled.

Why:

1. prompt changes are platform-governed behavior changes and must stay reviewable,
2. bank-grade environments need provenance and controlled rollout for prompt changes,
3. repository-reviewed changes plus Alembic-managed persistence keep promotion traceable without adding unsafe runtime write paths too early.

Current posture:

1. prompt definitions expose lifecycle and provenance metadata,
2. SQL-backed prompt definitions are promoted through migrations,
3. runtime prompt write APIs remain disabled until a stronger approval and rollout model exists.

## Decision 10: Provider Gateway Before Live Models

Decision:

`lotus-ai` routes task execution through an explicit provider gateway before any live model SDK is enabled.

Why:

1. provider selection needs its own typed boundary instead of being hidden inside task orchestration,
2. we want to prove audit and policy flow through a stable execution seam before introducing real providers,
3. this keeps the public task API stable while letting provider internals evolve safely.

Current posture:

1. the gateway currently routes only to deterministic stub providers,
2. provider inventory is visible through the provider catalog,
3. live model execution remains disabled until safety, approval, and rollout controls mature.
