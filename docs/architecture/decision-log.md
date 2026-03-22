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

## Decision 11: Provider Modes Must Fail Explicitly

Decision:

Unsupported provider modes must fail explicitly through a governed provider policy instead of falling
through silently.

Why:

1. enterprise operators need deterministic behavior when runtime configuration drifts,
2. silent fallback hides rollout mistakes and weakens auditability,
3. a policy layer lets us expand from `disabled` and `stub` toward future allowlisted live modes without reshaping task contracts.

Current posture:

1. provider policy is inspectable through `/platform/providers/policy`,
2. only `disabled` and `stub` modes are currently supported for text and embedding capabilities,
3. unsupported modes are rejected with a service-unavailable response.

## Decision 12: Safety Posture Must Be Inspectable

Decision:

`lotus-ai` exposes a read-only safety policy surface before introducing runtime redaction engines.

Why:

1. downstream teams need to know which controls are enforced versus documented,
2. bank-grade platform behavior should not rely on tribal knowledge,
3. task-level output-label and redaction posture should be visible before live model execution exists.

Current posture:

1. safety policy is inspectable through `/platform/safety/policy`,
2. response labeling and audit evidence are enforced controls,
3. redaction remains documented guidance at this phase rather than a runtime mutation engine.

## Decision 13: Safety Outcomes Belong In Audit Metadata

Decision:

Each task execution must persist the safety posture that applied to the run, not just expose safety policy separately.

Why:

1. audit consumers need execution-specific evidence instead of only a platform-wide policy view,
2. future safety rollout changes should remain traceable per request,
3. this creates a clean bridge from documented safety posture to future enforced runtime controls.

Current posture:

1. execution audit metadata now records `safety_mode`,
2. task-specific `redaction_posture` is persisted per run,
3. enforced safety-control identifiers are stored with each audit record.

## Decision 14: Runtime Safety Status Should Be Observable

Decision:

`lotus-ai` exposes a dedicated runtime safety status surface in addition to policy and audit metadata.

Why:

1. operators need a quick operational view without inspecting individual audit records,
2. platform runtime status should summarize safety posture just like persistence posture,
3. it creates a clean place to surface future runtime redaction or policy-engine activation.

Current posture:

1. runtime safety status is inspectable through `/platform/safety/runtime-status`,
2. platform runtime status now embeds a safety runtime summary,
3. runtime redaction remains inactive in the foundation phase.

## Decision 15: Retrieval Needs Its Own Execution Gateway

Decision:

Retrieval search now flows through an explicit execution gateway before any live vector search backend is introduced.

Why:

1. search execution needs a clean boundary separate from catalog and indexing metadata,
2. this lets us make disabled-versus-enabled retrieval behavior explicit and testable,
3. future live retrieval backends can be introduced behind the same seam without changing the public retrieval API.

Current posture:

1. retrieval execution is inspectable through `/platform/retrieval/execution-status`,
2. the gateway rejects live retrieval execution while the platform remains in staged retrieval mode,
3. catalog, indexing, and execution status are now separate but coordinated surfaces.

## Decision 16: Prompt Runtime Selection Should Be Inspectable

Decision:

`lotus-ai` exposes prompt runtime selection status separately from prompt definition and governance views.

Why:

1. operators and downstream teams need to know which prompt version is actually active per task,
2. rollout state should be inspectable even before a write-based promotion workflow exists,
3. this gives us a stable runtime-selection surface before future prompt promotion or rollback mechanics are introduced.

Current posture:

1. prompt runtime selection is inspectable through `/platform/prompts/runtime-status`,
2. the current selection mode is static active-prompt selection,
3. runtime promotion remains read-only and repository-governed.

## Decision 17: Platform Runtime Status Should Summarize Prompt Runtime

Decision:

`/platform/runtime-status` now embeds prompt runtime status instead of leaving prompt rollout posture on a separate island.

Why:

1. operators need one primary runtime dashboard for the service,
2. prompt runtime selection is operationally important once multiple governance surfaces exist,
3. embedding the summary reduces the number of calls required for routine checks while preserving the dedicated prompt endpoint.

Current posture:

1. platform runtime status includes prompt runtime selection summary,
2. dedicated prompt runtime status remains available for focused inspection,
3. the embedded view remains read-only and aligned with the prompt governance model.

## Decision 18: Task Runs Should Emit Structured Execution Evidence

Decision:

Task execution responses now include a typed execution evidence bundle describing the main decision inputs used for the run.

Why:

1. enterprise review needs more than a raw message and audit id,
2. a stable evidence schema gives later evaluation work a clean foundation,
3. this improves explainability without changing the deterministic execution posture.

Current posture:

1. task responses emit evidence for task contract, prompt selection, provider resolution, safety outcome, and retrieval posture,
2. evidence is deterministic and read-only in foundation phase,
3. live provider behavior is still disabled; the evidence model exists ahead of it.

## Decision 19: Evaluation Readiness Should Be Discoverable

Decision:

`lotus-ai` exposes a read-only evaluation catalog so teams can inspect execution evidence categories and staged fixture families directly from the service.

Why:

1. evaluation posture should be visible as a platform capability, not buried only in docs,
2. regression and governance workflows need a stable surface to target,
3. this prepares the service for future fixture manifests and evaluation APIs without overbuilding them now.

Current posture:

1. evaluation readiness is inspectable through `/platform/evals/catalog`,
2. evidence categories mirror the deterministic execution evidence bundle,
3. fixture families are staged and documented before a fuller evaluation runner exists.

## Decision 20: Platform Runtime Status Should Summarize Evaluation Posture

Decision:

`/platform/runtime-status` now embeds evaluation runtime posture in addition to the dedicated evaluation endpoints.

Why:

1. evaluation readiness is part of operational platform posture, not just developer documentation,
2. operators should not need multiple endpoint hops for routine readiness checks,
3. this keeps evaluation aligned with the same runtime-summary pattern already used for prompt and safety posture.

Current posture:

1. evaluation runtime status is available through `/platform/evals/runtime-status`,
2. platform runtime status embeds the same evaluation summary,
3. the evaluation runner remains inactive in the foundation phase.
