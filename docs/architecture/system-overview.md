# System Overview

`lotus-ai` is the shared AI platform service for Lotus.

Its role is to provide:

1. model access,
2. retrieval,
3. prompt governance,
4. safety,
5. auditability,
6. reusable AI task execution.

The other Lotus applications remain responsible for:

1. business context assembly,
2. domain semantics,
3. deterministic workflows,
4. applying or rejecting AI output.

## Architectural Shape

The service is intentionally being built in layers.

The required scalability posture is documented separately in:

- [scalability-and-deployment-model.md](C:/Users/Sandeep/projects/lotus-ai/docs/architecture/scalability-and-deployment-model.md)

That document should be treated as a strict architecture rule, not optional guidance.

### Contracts

- `src/app/contracts/`

Owns:

1. task categories,
2. output labels,
3. capability catalog response models,
4. future task request and response envelopes.

### Configuration

- `src/app/config.py`

Owns:

1. service phase settings,
2. provider mode settings,
3. retrieval mode settings,
4. safety mode settings,
5. startup readiness and readiness-probe policy settings.

### Services

- `src/app/services/`

Owns:

1. orchestration logic behind routers,
2. capability catalog assembly,
3. future prompt and provider orchestration.

The API-facing service layer should remain stateless so multiple replicas can serve the same
contracts without hidden node-local behavior.

### Async Runtime

- `src/app/services/async_runtime_status.py`
- `src/app/routers/async_runtime.py`

Owns:

1. async queue and worker posture exposure,
2. governed queue backend strategy exposure,
3. governed worker execution strategy exposure,
4. governed async activation-readiness exposure,
5. governed async runbook-readiness exposure,
6. governed async governance-summary exposure,
7. known background job-type inventory,
8. seeded async job artifact inspection,
9. governed async job submission contracts,
10. relationships between async job artifacts and evaluation history when applicable,
11. the contract boundary for future worker-backed execution.

### Providers

- `src/app/providers/`

Owns:

1. provider-specific execution adapters,
2. deterministic stub providers for foundation phase,
3. the future boundary where live model SDK integrations will sit.

### Retrieval

- `src/app/retrieval/`

Owns:

1. retrieval-source definitions,
2. chunking and indexing policies,
3. embedding and vector-search orchestration,
4. source provenance handling.

Initial storage direction:

1. PostgreSQL as the canonical durable database,
2. `pgvector` as the first vector-store extension,
3. no separate vector database unless later evidence justifies it.

Retrieval and evaluation workloads are also expected to move through worker-style execution paths
when they become heavy enough to threaten API responsiveness.

### Routers

- `src/app/routers/`

Owns:

1. public API endpoints,
2. OpenAPI-facing contracts,
3. upstream integration surfaces.

## Framework Policy

`lotus-ai` is a normal backend service first and an AI platform second.

That means the service is built around:

1. explicit API contracts,
2. typed Python modules,
3. observable service orchestration,
4. Lotus-owned safety and audit controls.

AI frameworks may be used selectively, but they must not become the source of truth for:

1. request flow,
2. task semantics,
3. output policy,
4. audit boundaries.

## LangGraph Guidance

LangGraph is currently out of the foundation scope.

It may be appropriate later for:

1. bounded async orchestration,
2. multi-step tool workflows,
3. internal state-machine style AI execution.

It is not appropriate right now as the base architecture for all of `lotus-ai`.

## Current Foundation Endpoints

1. `/`
2. `/health`
3. `/health/live`
4. `/health/ready`
5. `/metadata`
6. `/platform/runtime-status`
7. `/platform/capabilities`
8. `/platform/async/runtime-status`
9. `/platform/async/queue-backends`
10. `/platform/async/worker-executions`
11. `/platform/async/activation-readiness`
12. `/platform/async/runbook-readiness`
13. `/platform/async/governance-status`

The current capability endpoint is intentionally simple. It gives other Lotus apps a stable discovery surface while the rest of the platform is still under construction.

`/platform/runtime-status` now embeds both async runtime posture and async governance posture so
operators have one primary entry point for rollout review without losing the more detailed async
inspection endpoints.

## Provider Posture

`lotus-ai` exposes a governed provider catalog so downstream teams can inspect execution posture
without relying on implementation guesses.

Current rules:

1. provider inventory is visible through `/platform/providers`,
2. provider execution policy is visible through `/platform/providers/policy`,
3. provider activation readiness is visible through `/platform/providers/activation-readiness`,
4. provider runbook readiness is visible through `/platform/providers/runbook-readiness`,
5. provider governance status is visible through `/platform/providers/governance-status`,
6. foundation-phase providers are documented and inspectable,
7. task execution already flows through an internal provider gateway,
8. runtime execution remains disabled until a stronger provider gateway and safety posture is in place.

## Safety Posture

`lotus-ai` exposes a governed safety policy so downstream teams can inspect what is enforced today
versus what is still documented guidance.

Current rules:

1. safety posture is visible through `/platform/safety/policy`,
2. runtime safety status is visible through `/platform/safety/runtime-status`,
3. response labeling and audit evidence are already enforced,
4. redaction is currently documented at the task-policy level and will be hardened later.

## Deployment Policy

`lotus-ai` now has an explicit deployment policy for:

1. startup blocking behavior,
2. readiness-probe degradation behavior,
3. environment-specific persistence expectations.

The canonical reference is:

- `docs/architecture/startup-readiness-deployment-policy.md`

The canonical scalability reference is:

- `docs/architecture/scalability-and-deployment-model.md`
