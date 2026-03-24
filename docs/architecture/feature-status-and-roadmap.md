# Feature Status and Roadmap

This document is the quickest way to understand what `lotus-ai` supports today, what is governed but still intentionally limited, and what major feature areas are next.

## Current Product Shape

`lotus-ai` is a shared AI platform service for Lotus applications. It currently provides:

1. bounded AI task execution contracts,
2. governed prompt selection and rollback,
3. governed retrieval over approved platform documents,
4. runtime safety enforcement for bounded outputs,
5. runtime-backed evaluation and approval-gate evidence,
6. durable async execution with dedicated worker and queue support,
7. caller identity and tenant-aware authorization controls,
8. audit, evidence, and operator-facing governance surfaces,
9. governed artifact metadata and payload-store foundation.

The service is no longer only a documentation skeleton. It has real runtime control planes and durable platform state. It is still in a foundation phase because some important production-support features are intentionally deferred.

## Supported Today

### Bounded Task APIs

Supported task families:

1. `explain.v1`
2. `summarize.v1`
3. `generate_structured.v1`
4. `knowledge_search.v1`
5. `knowledge_answer.v1`

What this means:

1. task contracts are stable and typed,
2. task execution passes through validation, prompt resolution, provider routing, evidence assembly, safety handling, and audit persistence,
3. responses include structured audit and evidence metadata.

### Retrieval

Supported now:

1. governed retrieval source and document catalog,
2. live indexed search when `retrieval_mode=enabled`,
3. citation-bearing `knowledge_search.v1`,
4. citation-backed or refusal-style `knowledge_answer.v1`,
5. retrieval governance, activation, runbook, and evidence-readiness endpoints.

Important limitation:

1. retrieval is live for the approved indexed corpus only,
2. broader ingestion and corpus refresh are not implemented yet,
3. embedding-provider expansion now has one bounded live path available for retrieval indexing, but broader retrieval/provider activation is still not approved.

### Prompt Governance

Supported now:

1. durable prompt definition versions,
2. durable rollout state,
3. promote and rollback control-plane actions,
4. prompt runtime status and control history,
5. runtime-backed evaluation gating for prompt promotion,
6. prompt-linked audit and execution evidence.

Important limitation:

1. prompt bodies are still repository-managed,
2. the runtime only governs selection between approved prompt versions, not free-form editing.

### Safety

Supported now:

1. output-label-aware safety policy,
2. deterministic runtime redaction for bounded outputs,
3. typed safety outcome persistence in audit and evidence,
4. runtime-backed safety evaluation fixtures,
5. safety runtime, evidence, runbook, and governance surfaces.

Important limitation:

1. this is not a general moderation platform,
2. safety remains intentionally bounded to the existing task and output-contract model.

### Async Runtime

Supported now:

1. durable async job, attempt, lease, and control-event state,
2. queue-backed worker delivery with dedicated-worker activation,
3. governed retry, replay, requeue, and abandon actions,
4. retrieval indexing and evaluation execution as active async consumers,
5. async runtime, activation, runbook, and governance surfaces.

Important limitation:

1. the async system is still intentionally narrow in job-type scope,
2. it is not yet a general background-work platform for arbitrary domain tasks.

### Evaluation and Approval Gates

Supported now:

1. runtime-backed evaluation submission and execution,
2. durable run attempts and case outcomes,
3. approval-gate summaries for provider, retrieval, prompt, and safety rollout domains,
4. staged historical baseline visibility separated from current runtime truth.

### Access Control

Supported now:

1. caller policy registry,
2. task, retrieval, and live-provider authorization,
3. async, prompt, and provider control-plane authorization,
4. tenant-aware restrictions where tenant identity is part of the request contract,
5. authorization outcome persistence in audit, evidence, and control history,
6. access-control runtime, activation, runbook, and governance surfaces.

## Intentionally Limited or Not Yet Live

These areas are important because they are visible in the platform shape, but not fully delivered yet.

### Live Model Execution

Current state:

1. live-provider seams exist,
2. provider policy, quota, budget, degradation, and control-plane surfaces are implemented,
3. live execution remains disabled by default unless explicitly enabled and governed.

Practical meaning:

1. `lotus-ai` is structurally ready for governed live provider rollout,
2. it should still be treated as pre-rollout for production live-model traffic.

### Embeddings and Corpus Growth

Current state:

1. retrieval works over the existing approved indexed corpus,
2. RFC-0018 now exposes embeddings as a first-class governed provider capability with a registered live path and typed configuration posture,
3. retrieval indexing can now consume that bounded live embedding path when configured,
4. broader document ingestion is still not yet implemented as a first-class governed feature,
5. full retrieval/provider activation still remains blocked on later evidence and governance slices.

### Observability and Incident Evidence

Current state:

1. many runtime and governance endpoints exist,
2. `/platform/observability/runtime-status`, `/platform/observability/activation-readiness`, `/platform/observability/runbook-readiness`, and `/platform/observability/governance-status` now provide the bounded in-service observability control-plane surface,
3. provider, retrieval, async, evaluation, prompt, and safety incident summaries are now available through the observability API surface,
4. bounded caller, tenant, and capability breakdowns are now available through the observability API surface,
5. observability incident evidence now emits governed artifact descriptors for bounded per-domain incident bundles,
6. durable observability governance is now explicitly gated on SQL-backed audit and caller-policy stores rather than implied through prose.

### Artifact Storage

Current state:

1. a governed artifact metadata model and payload-store seam now exist,
2. relational metadata remains authoritative while payload bytes stay behind a bounded object-store interface,
3. evaluation runtime case results now emit governed artifact references for runtime-generated evidence bundles,
4. async runtime jobs now emit governed artifact references for terminal completion and failure payloads,
5. observability incident summaries now emit governed artifact references for bounded domain incident bundles,
6. artifact lifecycle posture is now inspectable through bounded catalog, activation, runbook, and governance surfaces,
7. filesystem-backed payload storage remains a clearly labeled local or development fallback and does not yet satisfy full artifact activation readiness,
8. broader consumer cutovers for additional runtime domains are still roadmap work.

### First Downstream Production Use Case

Current state:

1. the platform is ready enough for serious integration planning,
2. first-use-case onboarding is now partially implemented through a bounded `lotus-performance` contract, limited-rollout readiness surface, runbook-readiness surface, composed governance view, and reusable onboarding template,
3. first-use-case limited-rollout readiness now also depends on resilience governance so downstream onboarding does not overstate continuity posture,
4. a Dockerized live-provider demo path has now been proven technically,
5. that same live demo also showed the current platform is still not at a truthful production-standard baseline because live success required demo-only posture and the governed first-use-case gate fell back to blocked.
6. RFC-0020 runtime posture now distinguishes local or demo-capable from prod-shaped local by requiring both PostgreSQL-backed durable stores and the dedicated Redis-backed worker topology before the stack is treated as deployment-shaped.
7. RFC-0020 now also exposes `/platform/production-baseline/runtime-status`, `/platform/production-baseline/activation-readiness`, `/platform/production-baseline/runbook-readiness`, and `/platform/production-baseline/governance-status` so operators can inspect go-live posture separately from demo success.

## Roadmap

### Next Likely Feature Areas

The next RFCs already identified in the repo describe the expected sequence:

1. `RFC-0015` controlled deployment split into runtime, retrieval, and evals
2. `RFC-0017` production resilience and disaster recovery
3. `RFC-0018` governed embeddings and provider expansion
4. `RFC-0019` governed document ingestion and corpus refresh

Current status against that sequence:

1. `RFC-0015` is implemented, including runtime, activation, runbook, and governance posture for unified versus split deployment stages.
2. `RFC-0017` now exposes a bounded resilience runtime inventory surface, an ordered restore-plan surface, explicit degraded-versus-restored runtime posture for queue, worker, provider, retrieval, and artifact continuity dependencies, plus drill-evidence, activation, runbook, and governance surfaces.
3. `RFC-0018` is now in active implementation with Slice 2 complete at the bounded live embedding execution layer, while `RFC-0019` remains a roadmap item.

Early RFC-0015 groundwork now exists as a bounded runtime surface:

1. `/platform/deployment-split/runtime-status` reports the current unified versus split-ready posture and the intended runtime, retrieval, and eval plane ownership model,
2. `/platform/deployment-split/activation-readiness`, `/platform/deployment-split/runbook-readiness`, and `/platform/deployment-split/governance-status` now expose the operator-facing rollout truth for each split stage,
3. split-aware internal routing is now modeled explicitly for retrieval search, retrieval async execution, evaluation submission, and evaluation async execution,
4. retrieval can now be modeled as the first split-active internal plane while the runtime plane remains the single external front door,
5. retrieval-and-evals split can now be modeled as the second active internal stage while the runtime plane still remains the single external front door,
6. both retrieval and eval split activation are explicitly rollbackable to `UNIFIED` and can be reported as degraded instead of silently falling back.

The current preferred RFC-0016 target is:

1. `lotus-performance` analytics commentary over caller-supplied structured performance facts.
2. runtime and rollout posture are now inspectable through `/platform/use-cases/first-production-use-case`, `/platform/use-cases/first-production-use-case/readiness`, `/platform/use-cases/first-production-use-case/runbook-readiness`, and `/platform/use-cases/first-production-use-case/governance-status`.
3. reusable downstream onboarding guidance is now inspectable through `/platform/use-cases/onboarding-template`.

### Why These Are Next

In practical feature terms, the roadmap is:

1. build cleaner deployment topology on top of the now-explicit production baseline,
2. improve resilience on top of that baseline, using the new runtime, restore-plan, drill-evidence, and governance surfaces to harden actual recovery posture,
3. expand retrieval and provider breadth,
4. broaden corpus management.

## Recommended Reading Order

For a new engineer:

1. [README](C:/Users/Sandeep/projects/lotus-ai/README.md)
2. [system-overview.md](C:/Users/Sandeep/projects/lotus-ai/docs/architecture/system-overview.md)
3. this document
4. [phased-roadmap.md](C:/Users/Sandeep/projects/lotus-ai/docs/architecture/phased-roadmap.md)
5. [docs/rfcs/README.md](C:/Users/Sandeep/projects/lotus-ai/docs/rfcs/README.md)

For someone integrating a client app:

1. [integration-guide.md](C:/Users/Sandeep/projects/lotus-ai/docs/guides/integration-guide.md)
2. [task-execution-contract.md](C:/Users/Sandeep/projects/lotus-ai/docs/guides/task-execution-contract.md)
3. this document

For an operator:

1. [service-operations.md](C:/Users/Sandeep/projects/lotus-ai/docs/runbooks/service-operations.md)
2. [system-overview.md](C:/Users/Sandeep/projects/lotus-ai/docs/architecture/system-overview.md)
3. this document
