# RFC-0001: Shared AI Platform Service

- Status: Implemented
- Date: 2026-03-22
- Implemented Date: 2026-03-22
- Owners: lotus-ai

## Summary

`lotus-ai` is the shared AI platform service for the Lotus ecosystem.

It provides reusable AI infrastructure and governed task execution for the other Lotus applications while keeping business ownership in the domain services that already own portfolio state, analytics, reporting, and workflow logic.

This RFC originally established the existence and responsibility boundary of `lotus-ai` itself. It is now implemented as the platform-foundation RFC for the service.

## Original Intent

The original intent of RFC-0001 was to define:

1. that `lotus-ai` should exist as a separate Lotus service,
2. what the service owns versus what domain apps still own,
3. how Lotus apps should integrate with it,
4. the initial capability areas and repository shape,
5. the acceptance criteria for saying the shared platform service exists in a meaningful way.

## Responsibilities

`lotus-ai` owns:

1. provider abstraction and model routing,
2. prompt registry and versioning,
3. retrieval over approved Lotus knowledge sources,
4. safety and redaction controls,
5. AI audit logging and usage telemetry,
6. evaluation and regression harnesses,
7. bounded AI task APIs and async AI runs.

## Non-Responsibilities

`lotus-ai` does not own:

1. canonical business data,
2. deterministic trading or portfolio calculations,
3. approval truth,
4. reporting truth,
5. UI lifecycle orchestration,
6. autonomous production actions without an owning service contract.

## Integration Model

The normal path is:

1. domain service assembles structured context,
2. domain service calls `lotus-ai`,
3. `lotus-ai` returns a governed result,
4. domain service remains accountable for the business-facing outcome.

## Initial Capability Areas

1. `explain`
2. `summarize`
3. `classify`
4. `extract`
5. `generate_structured`
6. `knowledge_search`
7. `knowledge_answer`

## Architecture Direction

Initial module layout:

1. `providers`
2. `prompts`
3. `retrieval`
4. `safety`
5. `evals`
6. `services`
7. `routers`
8. `contracts`

## What Was Implemented Under RFC-0001

RFC-0001 is now considered implemented because the repo no longer contains only a concept or scaffold. It contains a real shared platform foundation with the core boundaries, contracts, governance surfaces, and bounded execution paths that make `lotus-ai` a usable Lotus platform service.

Implemented foundation scope includes:

1. standard Lotus backend service structure, startup/readiness controls, and platform metadata endpoints,
2. contract-first API design across tasks, prompts, providers, retrieval, safety, evaluation, async runtime, audit, and platform runtime status,
3. a real task execution pipeline with explicit validation, prompt selection, safety resolution, provider routing, evidence assembly, and audit persistence,
4. prompt registry, prompt runtime selection, and prompt governance/readiness surfaces,
5. provider gateway, provider policy, and provider governance/readiness surfaces,
6. safety policy, safety runtime visibility, and persisted safety posture in task audit records,
7. audit persistence, audit lookup, and bounded audit catalog inspection,
8. retrieval source/document/chunk metadata, retrieval governance, catalog-only retrieval execution, and retrieval-backed task flows,
9. evaluation fixture inventory, run artifacts, validation gates, and evaluation runtime visibility,
10. async runtime contracts, seeded job registry, submission envelope, and governance/readiness surfaces,
11. platform-wide runtime status aggregation that exposes the posture of the major governed seams in one operator entry point,
12. strong local/CI validation gates across formatting, typing, OpenAPI quality, manifest validation, migrations, tests, and coverage.

## Requirement Traceability

| Original requirement | Implemented reality | Evidence |
| --- | --- | --- |
| Separate shared AI service exists | `lotus-ai` is a standalone FastAPI backend with its own contracts, routers, startup policy, and metadata surfaces | [main.py](../../src/app/main.py#L1), [README.md](../../README.md#L1) |
| Clear ownership boundary versus domain apps | Service docs and contracts consistently position `lotus-ai` as assistive/governed infrastructure rather than business truth | [README.md](../../README.md#L1), [system-overview.md](../architecture/system-overview.md#L1) |
| Contract-first architecture | API and internal boundaries are modeled explicitly through `contracts`, routers, and service-layer orchestration | [contracts](../../src/app/contracts), [routers](../../src/app/routers), [services](../../src/app/services) |
| Shared provider layer | Provider gateway, policy, governance, and runtime posture exist even while live execution remains disabled | [provider_gateway.py](../../src/app/services/provider_gateway.py#L1), [providers.py](../../src/app/routers/providers.py#L1) |
| Shared prompt layer | Prompt registry, runtime selection, and governance/readiness surfaces exist | [prompts.py](../../src/app/routers/prompts.py#L1), [prompt_runtime.py](../../src/app/services/prompt_runtime.py#L1) |
| Shared retrieval layer | Retrieval metadata, governance, execution, and retrieval-backed task behavior exist in bounded form | [retrieval.py](../../src/app/routers/retrieval.py#L1), [retrieval_service.py](../../src/app/services/retrieval_service.py#L1), [task_execution_contract.md](../guides/task-execution-contract.md#L1) |
| Shared safety layer | Safety posture is modeled explicitly and reflected in runtime and audit behavior | [safety.py](../../src/app/routers/safety.py#L1), [task_execution_mapping.py](../../src/app/services/task_execution_mapping.py#L1) |
| Shared audit and telemetry posture | Audit persistence and bounded audit inspection are implemented | [audit.py](../../src/app/routers/audit.py#L1), [sqlalchemy_audit_repository.py](../../src/app/repositories/sqlalchemy_audit_repository.py#L1) |
| Shared evaluation harnesses | Eval catalog, eval runtime, run artifacts, validation gates, and fixture manifest are implemented | [evals.py](../../src/app/routers/evals.py#L1), [fixture-manifest.json](../evals/fixture-manifest.json#L1), [run-artifacts.json](../evals/run-artifacts.json#L1) |
| Shared async platform posture | Async contracts, job artifacts, submission path, and governance/readiness surfaces are implemented | [async_runtime.py](../../src/app/routers/async_runtime.py#L1), [job-artifacts.json](../async/job-artifacts.json#L1) |
| Reusable AI task APIs | Bounded task APIs exist with real execution pipeline and dedicated inspection surfaces | [tasks.py](../../src/app/routers/tasks.py#L1), [task_runtime.py](../../src/app/routers/task_runtime.py#L1) |

## Current Reality

`lotus-ai` is now a real shared platform service with:

1. reusable governed task APIs,
2. prompt, provider, retrieval, safety, evaluation, async, and audit seams,
3. operator-facing runtime and governance visibility,
4. migration-managed persistence,
5. a bounded but real execution path for key task categories.

What it is not yet:

1. a broadly activated live-provider platform,
2. an unconstrained agent runtime,
3. the owner of domain business truth,
4. a replacement for deterministic Lotus domain services.

## Design Evolution Since The Original RFC

RFC-0001 started as a high-level platform-establishment RFC. In implementation, that foundation grew into a substantial amount of concrete platform work before later major phases were split into their own RFCs.

The main evolution was:

1. RFC-0001 absorbed the foundation platform build-out: contracts, governance, bounded execution, audit, evaluation, and async posture,
2. deeper real retrieval work was then split into RFC-0002 because it became a major phase in its own right,
3. live provider activation is now being proposed separately in RFC-0003 because it is also a major phase with its own rollout risks.

That split is the right architecture/documentation outcome. RFC-0001 remains the platform-foundation RFC, while later RFCs describe major capability deepening on top of that foundation.

## Acceptance Criteria Status

### 1. The service is scaffolded as a standard Lotus backend repo.

Implemented.

Evidence:

1. [main.py](../../src/app/main.py#L1)
2. [README.md](../../README.md#L1)
3. [system-overview.md](../architecture/system-overview.md#L1)

### 2. The repo clearly documents what it does and does not own.

Implemented.

Evidence:

1. [README.md](../../README.md#L1)
2. [RFC-0001-shared-ai-platform-service.md](RFC-0001-shared-ai-platform-service.md#L1)
3. [decision-log.md](../architecture/decision-log.md#L1)

### 3. The platform can depend on `lotus-ai` for shared AI infrastructure without moving domain logic into it.

Implemented.

Evidence:

1. [tasks.py](../../src/app/routers/tasks.py#L1)
2. [task_execution_pipeline.py](../../src/app/services/task_execution_pipeline.py#L1)
3. [system-overview.md](../architecture/system-overview.md#L1)

## Close-Out Notes

RFC-0001 is closed as implemented in the sense intended for a platform-foundation RFC:

1. the shared service exists,
2. the ownership boundary is explicit,
3. the core platform seams are present,
4. downstream Lotus apps have a governed integration surface to depend on.

Follow-on work should not reopen RFC-0001. Major capability deepening should continue through focused follow-on RFCs such as retrieval and live provider activation.
