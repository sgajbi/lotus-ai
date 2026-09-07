# Repository Engineering Context

This is the durable repository-local orientation for `lotus-ai`. Read [AGENTS.md](AGENTS.md)
first. Load the specialist references below only when the task needs them; GitHub issues and pull
requests hold temporary delivery status.

Shared Lotus context remains authoritative in `lotus-platform`:

1. [Lotus Quickstart Context](https://github.com/sgajbi/lotus-platform/blob/main/context/LOTUS-QUICKSTART-CONTEXT.md)
2. [Lotus Engineering Context](https://github.com/sgajbi/lotus-platform/blob/main/context/LOTUS-ENGINEERING-CONTEXT.md)
3. [Lotus Skill Routing Map](https://github.com/sgajbi/lotus-platform/blob/main/context/LOTUS-SKILL-ROUTING-MAP.md)
4. [Context Reference Map](https://github.com/sgajbi/lotus-platform/blob/main/context/CONTEXT-REFERENCE-MAP.md)

## Repository Role

`lotus-ai` is the shared governed AI capability service for Lotus applications. It executes bounded
AI tasks and workflow packs while preserving the authority of the calling domain service.

## Business And Domain Responsibility

This repository owns:

1. governed AI task execution and provider routing,
2. prompt, model, retrieval, safety, evaluation, and activation controls,
3. durable async execution, workflow-pack runtime state, and operator controls,
4. AI-specific audit, lineage, cost, observability, and signed execution evidence.

It does not own portfolio, transaction, performance, risk, advisory, management, reporting, or
client truth. Every AI output is marked `non_authoritative_ai_output` until an authoritative caller
validates and applies it. AI output must never create approval, suitability, execution, or financial
truth by implication.

## Current-State Summary

Implemented task contracts, workflow packs, governance surfaces, and durable stores support
controlled local and integration use. Live provider, retrieval, and pack activation remain
separately evidence-gated; implementation presence is not production certification.

The default posture is conservative:

1. live provider execution, retrieval, and embeddings are disabled unless explicitly activated,
2. provider output is accepted only after deterministic grounding and contract validation,
3. rejected output is withheld rather than returned as plausible content,
4. promoted runtime profiles require durable stores and explicit economic limits,
5. calling services retain business meaning, decision authority, and downstream consequences.

Current delivery priority and external evidence dependencies belong on the
[`lotus-ai` issue tracker](https://github.com/sgajbi/lotus-ai/issues), not in this file.

## Architecture And Module Map

A request follows one explicit execution spine:

```text
verified caller -> policy and task/pack binding -> frozen execution configuration
                -> governed provider/retrieval execution -> deterministic validation
                -> audit, evidence, cost, and response
```

Primary ownership areas:

| Area | Responsibility |
| --- | --- |
| `src/app/contracts/` | Public request, response, and evidence contracts |
| `src/app/routers/` | FastAPI transport, authorization, and problem-detail mapping |
| `src/app/services/` | Execution orchestration and governance controls |
| `src/app/providers/` | Provider adapters and execution transport |
| `src/app/prompts/` | Prompt definitions, selection, and rollout state |
| `src/app/retrieval/` | Governed sources, indexing, grounding, and search |
| `src/app/evals/` | Runtime evaluation and approval evidence |
| `contracts/` | Machine-readable output, policy, lifecycle, and evidence contracts |
| `alembic/` | Migration-managed durable state |
| `docs/` | Detailed architecture, standards, guides, RFCs, and runbooks |
| `wiki/` | Authored source for concise published onboarding and operations pages |

Detailed component behavior belongs in the
[system overview](docs/architecture/system-overview.md). Capability maturity belongs in
[feature status and roadmap](docs/architecture/feature-status-and-roadmap.md).

## Runtime And Integration Boundaries

1. Callers send structured, minimized business context and source references.
2. Caller identity and active caller policy are verified before protected execution. Verified JWT
   mode fails closed and does not fall back to caller-supplied headers.
3. One frozen execution configuration binds model identity and enforcement settings for a run.
4. Governed routing order is policy, not model ranking; every attempted and selected candidate is
   recorded.
5. Quota, budget, circuit-breaker, kill-switch, lifecycle, and evaluation controls remain distinct
   mechanisms with distinct evidence.
6. Provider output passes evidence grounding, numeric grounding, task or pack schema validation,
   and safety handling before it can be returned.
7. Shared API and worker deployments must use durable cross-process stores. In-memory modes are
   development seams, not promoted distributed-runtime posture.
8. Workflow packs constrain AI behavior but do not absorb the caller's domain workflow or
   authority.
9. PostgreSQL is the durable production-shaped database; Redis is the queue transport, not the
   authoritative job ledger.
10. **The API and the dedicated worker have different health contracts and are not
    interchangeable.** The API answers `/health/live` and `/health/ready` over HTTP. The worker
    binds no port, so none of those endpoints exist inside its container: it writes a liveness
    marker each loop cycle and the container `HEALTHCHECK` runs `python -m app.worker_health_main`
    in a separate process to read it. Worker health answers "did this worker's loop run recently
    AND reach the queue backend it needs", with distinct fail-closed reason codes rather than one
    boolean.

    Two rules follow, both learned by the defect this replaced — the worker inherited the API image
    probe and reported permanently unhealthy while executing jobs correctly:

    - Never satisfy a container health check by standing up a server the workload does not
      otherwise run. That reports on the probe, not on the workload.
    - A queue-backend outage must leave the worker running and reporting the outage, not kill it.
      A health contract cannot detect what kills it first, and a worker that dies takes its own
      diagnosis with it.

    Operational detail, reason codes and the deliberate negative test live in
    `docs/runbooks/service-operations.md`.

Frameworks and provider SDKs are adapters. They must not become the authority for request flow,
task semantics, validation, policy, or audit evidence.

## Task Routes

Load only the route relevant to the change:

| Task | Required local references |
| --- | --- |
| Task API or consumer integration | [Task execution contract](docs/guides/task-execution-contract.md), [integration guide](docs/guides/integration-guide.md) |
| Workflow-pack change | [Workflow-pack owner onboarding](docs/guides/workflow-pack-owner-onboarding.md), owning RFC and output contract |
| Provider or model governance | [Provider mode switching](docs/runbooks/provider-mode-switching.md), [service operations](docs/runbooks/service-operations.md) |
| Retrieval or corpus work | [Retrieval and vector store](docs/guides/retrieval-and-vector-store.md), applicable retrieval contracts |
| Evaluation or activation | [Evaluation strategy](docs/evals/evaluation-strategy.md), applicable fixture manifest and RFC |
| Async worker or recovery | [System overview](docs/architecture/system-overview.md), [service operations](docs/runbooks/service-operations.md) |
| Security, identity, or tenant controls | [Security and governance](docs/security/security-and-governance.md), relevant contract and RFC |
| Migration or durable-state change | [Migration contract](docs/standards/migration-contract.md), Alembic history, PostgreSQL proofs |
| RFC or roadmap work | [RFC index](docs/rfcs/README.md), platform RFC governance through the skill routing map |

## Repo-Native Commands

Run commands from the repository root in an activated Python 3.12 environment.

| Purpose | Command |
| --- | --- |
| Install locked dependencies | `make install` |
| Fast local gate | `make check` |
| PR-grade gate | `make ci` |
| Unit, integration, or E2E tests | `make test-unit`, `make test-integration`, `make test-e2e` |
| Runtime-mode proof | `make runtime-mode-smoke` |
| Real PostgreSQL fence proof | `make test-postgres` |
| Migration SQL validation | `make migration-smoke` |
| API contract gate | `make openapi-gate` |
| Docker runtime proof | `make docker-build` |

`make test-postgres` requires `LOTUS_AI_POSTGRES_TEST_URL` pointing to a disposable database. CI
uses `LOTUS_AI_POSTGRES_TEST_REQUIRED` to prevent silent skipping in the PostgreSQL lane.

## Validation And CI Expectations

The delivery lanes are Remote Feature Lane, Pull Request Merge Gate, and Main Releasability Gate.
Use targeted tests while iterating, then run the narrowest repository-native gate that covers the
changed contract. `make ci` is the local PR-grade composition; GitHub checks remain the authority
for exact-head and exact-main evidence.

Tests must prove behavior, including:

1. non-authoritative output and source-authority boundaries,
2. fail-closed identity, policy, activation, and economic controls,
3. deterministic validation and whole-output rejection,
4. idempotency, replay, lease fencing, and recovery,
5. audit, lineage, model identity, and cost evidence,
6. real PostgreSQL concurrency semantics where database isolation matters.

Do not replace database proof with mocks, weaken an assertion to accommodate a defect, or call a
stub/live fixture production certification. Review findings marked `BLOCKING` or `MUST-FIX` remain
merge gates under [AGENTS.md](AGENTS.md).

## Standards And RFCs That Govern This Repository

Repository standards live in [docs/standards](docs/standards/). The
[RFC index](docs/rfcs/README.md) distinguishes implemented, draft, and superseded design truth.
Shared Lotus engineering and documentation conventions remain platform-owned; link to them rather
than copying them locally.

Key local standards are:

1. [Enterprise readiness](docs/standards/enterprise-readiness.md)
2. [Durability and consistency](docs/standards/durability-consistency.md)
3. [Data model ownership](docs/standards/data-model-ownership.md)
4. [Migration contract](docs/standards/migration-contract.md)
5. [API documentation](docs/standards/api-documentation.md)
6. [Scalability and availability](docs/standards/scalability-availability.md)

## Known Constraints And Implementation Notes

1. Live providers require independent activation, evaluation, model-risk, retention, and operator
   evidence; code and deterministic fixtures alone do not satisfy those controls.
2. Dual control currently binds distinct verified service credentials, not verified human
   principals.
3. Some readiness families predate the shared readiness catalog; do not copy their legacy module
   shape into new work.
4. Cost is recorded and budget admission is enforced where configured, but cost preference is not
   a general model-ranking authority.
5. Local header identity is for explicitly configured local runtime only.

## Context Maintenance Rule

Keep durable repository facts here: ownership, architecture, boundaries, task routes, canonical
commands, validation expectations, and lasting constraints. Keep delivery status, commit history,
temporary blockers, and planned issue order in GitHub.

Update this file when a repository responsibility, architecture boundary, canonical command, or
completion requirement changes. Update central `lotus-platform` context only when the convention is
ecosystem-wide.

## Cross-Links

1. [README](README.md) — product front door and recommended quick start
2. [System overview](docs/architecture/system-overview.md) — detailed implementation architecture
3. [Feature status and roadmap](docs/architecture/feature-status-and-roadmap.md) — capability posture
4. [Service operations](docs/runbooks/service-operations.md) — operations and recovery
5. [Security and governance](docs/security/security-and-governance.md) — trust boundaries and controls
6. [GitHub wiki](https://github.com/sgajbi/lotus-ai/wiki) — published onboarding navigation
