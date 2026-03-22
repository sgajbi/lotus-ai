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

The current execution posture is:

- task execution flows through an explicit internal provider gateway,
- task execution now flows through an explicit internal runtime pipeline with separate validation, resolution, response, evidence, and audit stages,
- the provider handoff now carries resolved output-label and safety metadata rather than only raw caller context,
- prompt runtime selection is now resolved through a shared runtime service used by both task execution and prompt-status reporting,
- task execution now builds a shared runtime context object so later stages consume one coherent execution model instead of duplicated fields,
- response and audit-record assembly for task execution now live in a dedicated mapper layer instead of being embedded in pipeline orchestration,
- provider execution requests are now assembled through a dedicated builder instead of inline payload construction,
- capability and expected-output validation now live in a dedicated validator instead of being embedded in task context construction,
- runtime-context construction and shared execution models now live in dedicated modules rather than inside the pipeline service,
- task execution and audit API behavior now have their own dedicated integration module instead of relying only on the broad health suite,
- prompt API behavior now also has its own dedicated integration module instead of living only inside the broad health suite,
- provider API behavior now also has its own dedicated integration module instead of living only inside the broad health suite,
- retrieval API behavior now also has its own dedicated integration module instead of living only inside the broad health suite,
- safety API behavior now also has its own dedicated integration module instead of living only inside the broad health suite,
- evaluation API behavior now also has its own dedicated integration module instead of living only inside the broad health suite,
- async API behavior now also has its own dedicated integration module instead of living only inside the broad health suite,
- the provider gateway currently routes only to documented stub providers,
- provider policy exposes which runtime modes are supported and how unsupported modes are rejected,
- provider activation readiness is now exposed through a dedicated rollout-readiness endpoint,
- provider runbook readiness is now exposed through a dedicated operational-readiness endpoint,
- provider evidence readiness is now exposed through a dedicated evidence-readiness endpoint,
- provider governance status is now exposed through a dedicated review-summary endpoint with technical, operational, and evidence posture,
- platform runtime status now embeds provider governance posture directly,
- safety policy exposes task-level output-label and redaction posture,
- task audit records now persist the applied safety posture for every execution,
- runtime safety status exposes which controls are enforced versus documented-only,
- retrieval now has an explicit execution seam and runtime execution-status surface,
- retrieval activation readiness is now exposed through a dedicated rollout-readiness endpoint,
- retrieval runbook readiness is now exposed through a dedicated operational-readiness endpoint,
- retrieval evidence readiness is now exposed through a dedicated evidence-readiness endpoint,
- retrieval governance status is now exposed through a dedicated review-summary endpoint with technical, operational, and evidence posture,
- platform runtime status now embeds retrieval governance posture directly,
- prompts now expose runtime selection status in addition to governance posture,
- prompt activation readiness is now exposed through a dedicated rollout-readiness endpoint,
- prompt runbook readiness is now exposed through a dedicated operational-readiness endpoint,
- prompt evidence readiness is now exposed through a dedicated evidence-readiness endpoint,
- prompt governance status is now exposed through a dedicated review-summary endpoint with technical, operational, and evidence posture,
- platform runtime status now embeds prompt governance posture directly,
- platform runtime status now summarizes prompt runtime posture directly,
- task execution responses now include structured evidence about prompt, provider, safety, and retrieval posture,
- evaluation catalog now exposes staged evidence categories and fixture families,
- evaluation fixture family detail is now inspectable through a dedicated read-only endpoint,
- platform runtime status now summarizes evaluation runtime posture too,
- evaluation fixture inventory is now backed by a versioned in-repo manifest,
- the first real file-backed fixture family now exists for `explain.v1`,
- a second file-backed fixture family now exists for `summarize.v1`,
- retrieval citation and refusal examples are now staged as file-backed evaluation fixtures,
- provider policy behavior is now staged as file-backed evaluation fixtures,
- safety policy behavior is now staged as file-backed evaluation fixtures,
- task capability and enablement behavior is now staged as file-backed evaluation fixtures,
- evaluation fixture manifest validity is now enforced by a dedicated CI gate,
- evaluation runtime status now summarizes staged coverage by platform seam,
- recorded evaluation run artifacts are now exposed through read-only inspection endpoints,
- recorded evaluation run artifacts are now validated by a dedicated gate,
- evaluation run artifacts now model both current and superseded lifecycle states,
- async queue and worker posture is now exposed through a dedicated runtime-status endpoint,
- governed queue backend strategies are now exposed through a dedicated async catalog endpoint,
- governed worker execution strategies are now exposed through a dedicated async catalog endpoint,
- async activation readiness is now exposed through a dedicated rollout-readiness endpoint,
- async runbook readiness is now exposed through a dedicated operational-readiness endpoint,
- async governance status is now exposed through a dedicated review-summary endpoint,
- platform runtime status now embeds async governance posture directly,
- seeded async job artifacts are now exposed and validated through dedicated contracts,
- async job submission now has a governed request/response contract with explicit foundation-phase rejection behavior,
- async job artifacts can now reference related evaluation run artifacts for cross-seam traceability,
- live model execution remains disabled until a governed provider rollout exists.

The current persistence posture is:

- in-memory audit storage by default for simple local development,
- in-memory prompt registry by default, with a SQLAlchemy-backed prompt adapter available behind the same repository seam,
- prompt definitions now expose lifecycle and provenance metadata in both memory and SQL-backed modes,
- a SQLAlchemy-backed audit adapter available behind the same repository interface for durable storage,
- in-memory retrieval metadata by default, with a SQLAlchemy-backed retrieval adapter available behind the same repository seam,
- explicit configuration to move between the two without changing API contracts,
- Alembic-managed schema migrations for relational persistence; repository adapters do not create tables at runtime.
- prompt promotion remains read-only at runtime and is governed through reviewed repository changes plus Alembic-managed persistence updates.
- startup readiness policy defaults to `warn` and can be raised to `enforce` for SQL-backed enterprise environments.
- readiness probe policy defaults to `observe` and can be raised to `degrade` when orchestration should react to readiness findings.

The current retrieval-storage decision is:

- no vector store is wired yet,
- the planned first vector store is PostgreSQL with `pgvector`,
- we are intentionally avoiding a separate vector database until scale or workload evidence justifies it.

The current retrieval posture is:

- approved retrieval sources are registered explicitly,
- retrieval source discovery is exposed through the platform API,
- provider posture discovery is exposed through the platform API,
- runtime posture for retrieval and platform services is exposed through the platform API,
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

Internally, `lotus-ai` now also treats task execution as a governed pipeline rather than a single
monolithic function. That keeps the runtime easier to test, easier to audit, and easier to extend
when live providers and retrieval execution are introduced later.

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

The service also follows a strict scalability model:

1. API-serving components stay stateless,
2. durable state moves to governed stores,
3. long-running work scales through worker processes,
4. internal seams stay clean enough to split into separate deployables later without changing external contracts.

The local security audit posture is also intentionally isolated:

1. `make ci` runs dependency audit inside a temporary project-only virtual environment,
2. this avoids false positives from unrelated machine-wide Python packages,
3. the audit still fails on vulnerabilities in the actual `lotus-ai` dependency set.

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
make eval-manifest-gate
make eval-run-gate
make async-job-gate
make migration-smoke
make runtime-mode-smoke
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
- startup readiness deployment policy: `docs/architecture/startup-readiness-deployment-policy.md`
- scalability and deployment model: `docs/architecture/scalability-and-deployment-model.md`
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
- API documentation standard: `docs/standards/api-documentation.md`
- migration contract standard: `docs/standards/migration-contract.md`
- platform governance source: `../lotus-platform/rfcs/RFC-0069-lotus-ai-shared-ai-platform-service.md`
