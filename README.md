# lotus-ai

Shared AI platform service for Lotus applications.

`lotus-ai` provides the reusable AI infrastructure layer for the Lotus estate. It exists to help the other Lotus apps build governed AI features without moving domain ownership out of the services that already own portfolio data, analytics, workflow state, and deterministic decision logic.

## Current Phase

The repository is in foundation phase.

Current goals:

- define the service architecture clearly,
- document the delivery roadmap,
- establish enterprise-grade governance expectations,
- introduce stable task and capability contracts before integrating any model provider.

This is deliberate. The early focus is to make `lotus-ai` understandable, testable, and governable before it becomes feature-rich.

The current persistence posture is:

- in-memory audit storage by default for simple local development,
- a SQLAlchemy-backed audit adapter available behind the same repository interface for durable storage,
- explicit configuration to move between the two without changing API contracts.

The current retrieval-storage decision is:

- no vector store is wired yet,
- the planned first vector store is PostgreSQL with `pgvector`,
- we are intentionally avoiding a separate vector database until scale or workload evidence justifies it.

The current retrieval posture is:

- approved retrieval sources are registered explicitly,
- retrieval source discovery is exposed through the platform API,
- live retrieval search remains disabled until embeddings and vector indexing are wired.

## What lotus-ai Does

- LLM gateway and model routing
- prompt and prompt-version management
- retrieval over approved Lotus docs, RFCs, schemas, and standards
- AI safety controls such as redaction, output labeling, and role-aware gating
- AI audit logging, cost tracking, and evaluations
- reusable AI task APIs for explanation, summarization, extraction, classification, and structured generation
- async AI run orchestration for longer jobs

## Vector Store Direction

`lotus-ai` will use PostgreSQL with `pgvector` as the first vector-store architecture.

Why this is the current default:

1. it fits the Lotus backend posture,
2. it keeps operations simpler,
3. it is sufficient for the first retrieval phases,
4. it supports metadata filtering and provenance without introducing a separate retrieval runtime too early.

What this means in practice:

1. canonical durable database remains PostgreSQL,
2. vector search lives beside the rest of the governed retrieval metadata,
3. retrieval remains a Lotus-owned layer rather than a framework-owned abstraction.

## What lotus-ai Does Not Do

- own portfolio or transaction truth
- replace deterministic logic in `lotus-core`, `lotus-performance`, `lotus-risk`, `lotus-advise`, or `lotus-manage`
- become the source of truth for approvals, consent, risk, or reporting decisions
- own UI lifecycle orchestration from `lotus-gateway` or `lotus-workbench`
- autonomously execute trades or workflow transitions

## How Other Lotus Apps Should Use It

The preferred integration model is:

1. a Lotus app prepares the structured context it owns,
2. it calls `lotus-ai` for a bounded AI task,
3. `lotus-ai` returns a governed result with audit metadata,
4. the calling app remains responsible for business meaning and user-facing application.

Examples:

- `lotus-manage` can ask `lotus-ai` to explain why a rebalance is `BLOCKED`.
- `lotus-advise` can ask `lotus-ai` to draft a reviewer summary for a proposal.
- `lotus-performance` and `lotus-risk` can ask `lotus-ai` for analytics commentary.
- `lotus-core` can ask `lotus-ai` to summarize supportability anomalies.

## Initial Repository Layout

- `src/app/providers/`: provider adapters and model routing
- `src/app/prompts/`: prompt registry and prompt-version assets
- `src/app/retrieval/`: knowledge indexing and retrieval services
- `src/app/safety/`: redaction, policy checks, and output controls
- `src/app/evals/`: evaluation and regression helpers
- `src/app/services/`: service-layer orchestration
- `src/app/contracts/`: request and response models
- `src/app/routers/`: API surfaces
- `docs/rfcs/`: service-local architecture decisions

## Build Strategy

We are building `lotus-ai` incrementally.

1. Foundation:
   contracts, settings, architecture docs, governance, and evaluation standards.
2. Safe task APIs:
   explanation, summarization, classification, extraction, and knowledge retrieval.
3. Platform controls:
   prompt registry, audit logging, redaction, model routing, and eval harnesses.
4. Cross-app adoption:
   start with one Lotus app integration, then expand based on evidence.
5. Advanced orchestration:
   async runs and tool-using flows only after the core safety and observability layers are solid.

## Enterprise Posture

`lotus-ai` is being built for an enterprise private-banking target environment, while acknowledging startup execution constraints.

That means:

- strong contracts,
- explicit ownership boundaries,
- traceability and auditability,
- pragmatic slice-by-slice delivery,
- no speculative overbuilding,
- no hidden AI behavior in critical workflows.

## Framework Stance

`lotus-ai` is not being built around a large AI orchestration framework as its core architecture.

The foundation remains:

- `FastAPI`
- `Pydantic`
- `pydantic-settings`
- normal Python service modules
- explicit Lotus-owned contracts, routing, safety, and audit behavior

We may use targeted AI libraries where they reduce plumbing, but those libraries should remain implementation helpers rather than the definition of the platform.

Current default position:

1. own contracts, prompts, routing, safety, and audit logic ourselves,
2. use provider SDKs or thin wrappers first,
3. introduce specialized AI libraries only where they clearly improve delivery without obscuring control flow.

## LangGraph Position

LangGraph is not part of the initial foundation of `lotus-ai`.

Why:

1. the first priority is contract-first, auditable platform behavior,
2. our early use cases are explanation, retrieval, and bounded task execution rather than complex autonomous agents,
3. we want to avoid hidden orchestration behavior before the governance model is mature.

LangGraph may be considered later for tightly bounded async or tool-using workflows, but only after:

1. task contracts are stable,
2. audit logging is complete,
3. safety and approval controls are in place,
4. we have real evidence that graph-style orchestration is needed.

Even if adopted later, LangGraph should be used as an internal orchestration helper, not as the public architecture of `lotus-ai`.

## Quick Start

```powershell
make install
make lint
make typecheck
make openapi-gate
make ci
```

## Run

```powershell
uvicorn app.main:app --reload --port 8140
```

## Docker

```powershell
docker compose up --build
```

## Documentation

- architecture overview: `docs/architecture/system-overview.md`
- phased roadmap: `docs/architecture/phased-roadmap.md`
- decisions and rationale: `docs/architecture/decision-log.md`
- domain integration guide: `docs/guides/integration-guide.md`
- task execution contract: `docs/guides/task-execution-contract.md`
- prompt registry and audit: `docs/guides/prompt-registry-and-audit.md`
- retrieval and vector store: `docs/guides/retrieval-and-vector-store.md`
- evaluation strategy: `docs/evals/evaluation-strategy.md`
- security and governance: `docs/security/security-and-governance.md`
- service-local RFCs: `docs/rfcs/`
- service standards: `docs/standards/`
- platform governance source: `../lotus-platform/rfcs/RFC-0069-lotus-ai-shared-ai-platform-service.md`
