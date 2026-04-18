# Architecture

## Architectural Shape

`lotus-ai` is a FastAPI service built around explicit seams and bounded control planes. The
architecture is designed so the service can expose governed AI capabilities without hiding policy,
audit, or rollout behavior behind framework abstractions.

The core runtime principle is:

1. keep public contracts explicit,
2. keep policy and rollout state inspectable,
3. keep audit and evidence generation part of execution rather than an afterthought,
4. keep the service stateless at the API-serving layer while durable state moves into governed
   stores.

## Primary Runtime Areas

1. `src/app/contracts/`
   public task and platform contract models.
2. `src/app/services/`
   orchestration logic, runtime-context building, response mapping, and audit flow.
3. `src/app/providers/`
   provider adapters, rollout, quota, budget, and degradation handling.
4. `src/app/prompts/`
   prompt definitions, rollout state, control history, and runtime selection.
5. `src/app/retrieval/`
   source governance, document governance, indexed-search posture, and retrieval execution seams.
6. `src/app/safety/`
   output-label-aware policy and runtime safety behavior.
7. `src/app/evals/`
   fixture inventory, runtime execution, approval gates, and evaluation artifacts.
8. `src/app/routers/`
   public API surfaces for task execution and platform inspection.

## Execution Flow

The task runtime is intentionally split into small stages:

1. validate the task and request shape,
2. build one shared runtime context,
3. resolve prompt and safety posture,
4. execute through the provider or retrieval seam,
5. assemble evidence and operator-facing metadata,
6. persist the audit record.

This keeps the runtime understandable and makes later rollout changes less dangerous than embedding
policy, prompt, safety, and response logic in one orchestration block.

## Durability Model

The architecture supports memory-backed and SQL-backed modes through repository seams.

Important examples:

1. prompt rollout state can be durable,
2. audit persistence can be durable,
3. retrieval metadata can be durable,
4. provider operations state can be durable,
5. async runtime and evaluation runtime can be durable.

The durable path matters because `lotus-ai` is designed for restart-safe governance rather than
process-local convenience.

## Architectural Boundaries

The service is intentionally not the place for:

1. business-domain ownership,
2. uncontrolled autonomous tool use in production-facing paths,
3. opaque orchestration frameworks becoming the public architecture,
4. unstated rollout assumptions.

The current framework stance is conservative: use libraries where they reduce plumbing, but do not
let them obscure task contracts, audit boundaries, or policy gates.

## Source Documents

For the detailed architecture and implementation rationale, read:

- `docs/architecture/system-overview.md`
- `docs/architecture/scalability-and-deployment-model.md`
- `docs/architecture/startup-readiness-deployment-policy.md`
- `docs/architecture/decision-log.md`
- `docs/architecture/feature-status-and-roadmap.md`

## Read Next

1. use [Platform Surfaces](./Platform-Surfaces.md) for the grouped public route map,
2. use [Getting Started](./Getting-Started.md) for local runtime choices,
3. use [Development Workflow](./Development-Workflow.md) for the working loop.
