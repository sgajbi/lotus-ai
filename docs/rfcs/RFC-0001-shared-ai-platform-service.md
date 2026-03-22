# RFC-0001: Shared AI Platform Service

- Status: Proposed
- Date: 2026-03-22
- Owners: lotus-ai

## Summary

`lotus-ai` is the shared AI platform service for the Lotus ecosystem.

It provides reusable AI infrastructure and governed task execution for the other Lotus applications while keeping business ownership in the domain services that already own portfolio state, analytics, reporting, and workflow logic.

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

## Acceptance Criteria

1. The service is scaffolded as a standard Lotus backend repo.
2. The repo clearly documents what it does and does not own.
3. The platform can depend on `lotus-ai` for shared AI infrastructure without moving domain logic into it.
