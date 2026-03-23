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
3. prompt and provider orchestration,
4. task execution pipeline stages for validation, resolution, response assembly, and audit persistence.

The API-facing service layer should remain stateless so multiple replicas can serve the same
contracts without hidden node-local behavior.

Current task execution runtime is intentionally split into small pipeline stages:

1. request validation against the bounded capability catalog,
2. runtime-context construction containing capability, prompt, safety, and execution metadata,
3. safety posture resolution from output-label policy,
4. provider execution through the internal provider gateway,
5. evidence assembly for prompt, provider, safety, and retrieval posture,
6. audit persistence through the configured audit repository seam.

Prompt runtime status and task execution now share the same runtime-selection rule rather than
encoding prompt-selection semantics separately in different services.

The runtime context object exists to keep later pipeline stages small and explicit instead of
threading overlapping request, prompt, and safety fields through multiple function signatures.

Response and audit-record construction now also live in a dedicated mapping layer so the pipeline
itself stays focused on execution stages rather than serialization details.

Provider request construction is also isolated in a dedicated builder so the pipeline no longer
assembles provider payloads inline.

Capability and output-label validation are also isolated in a dedicated validator so the runtime
pipeline no longer mixes policy enforcement with context construction.

Runtime-context construction now also lives in a dedicated builder, and the shared execution
context models are isolated in their own module so pipeline, mapping, and provider-request
services can depend on the same runtime types without import coupling.

Public task and audit API behavior is now also verified through a dedicated integration module
instead of being buried only inside the broader health suite.

Prompt API behavior is also verified through its own dedicated integration module so prompt
governance and runtime contract coverage can evolve independently of the broader platform
health suite.

Provider API behavior is also verified through its own dedicated integration module so
provider contract coverage can evolve independently of the broader platform health suite.

Retrieval API behavior is also verified through its own dedicated integration module so
retrieval contract coverage can evolve independently of the broader platform health suite.

Safety API behavior is also verified through its own dedicated integration module so safety
contract coverage can evolve independently of the broader platform health suite.

Evaluation API behavior is also verified through its own dedicated integration module so
evaluation contract coverage can evolve independently of the broader platform health suite.

Async API behavior is also verified through its own dedicated integration module so async
contract coverage can evolve independently of the broader platform health suite.

The standard integration API modules now share a common test client fixture so harness setup
is centralized without hiding route-level assertions behind generic helpers.

Runbook, evidence, and governance builders also share a small readiness helper for item-count
and blocking-count bookkeeping, so the domain services stay focused on their own governed
content instead of repeating the same counting logic.

The top-level platform runtime summary also isolates startup-readiness state extraction and has
direct unit coverage, so changes to operator-facing status aggregation do not rely only on
route-level integration tests.

Prompt runtime services also own lifecycle counting now, so prompt governance and prompt
runtime status share the same lifecycle summary source instead of duplicating active-prompt
filtering in separate builders.

Evaluation runtime services also use a dedicated inventory-summary helper now, so fixture and
case-count derivation is isolated from the final runtime-status response assembly.

Retrieval services also use a dedicated inventory-summary helper now, so source-level and
runtime-level document and chunk counts are derived in one place instead of being recomputed
independently by retrieval status and job builders.

The provider gateway also stays intentionally explicit in foundation phase: supported provider
modes are validated first, provider selection resolves through a small registered adapter seam,
and live OpenAI execution is only available when rollout state, credentials, and task-level
allowlisting all permit it. Otherwise provider-backed tasks continue through the deterministic
stub path or fail with an explicit blocked-live posture.

Provider runtime mode and provider rollout posture are now also separated explicitly. The
provider APIs expose current supported execution mode, future rollout state, and live-provider
configuration posture as distinct concepts so bank-grade activation review does not depend on
interpreting a single overloaded setting.

Provider execution posture is also now bounded explicitly at request time through timeout,
retry, and output-token controls. Even though current foundation execution remains stubbed,
those controls now exist as part of the provider contract so live rollout can inherit a real
execution-hardening seam rather than implicit provider-SDK defaults.

Provider operations hardening now begins with a dedicated quota contract. `/platform/providers/quota-policy`
exposes task, caller-app, tenant, and default quota scopes separately from provider rollout posture,
and the live provider gateway now fails explicitly when quota configuration is malformed or a live
execution scope has exceeded its configured request budget.

Provider operations hardening now also includes a dedicated budget contract. `/platform/providers/budget-policy`
exposes current tracked spend plus configured soft and hard budget thresholds separately from rollout
posture, and the live provider gateway now fails explicitly when hard-budget posture blocks further
execution or when budget enforcement is configured inconsistently.

Provider operations hardening now also includes a dedicated operations summary. `/platform/providers/operations-status`
combines rollout posture, quota posture, budget posture, and the current degradation placeholder into
one operator-facing truth surface, and `/platform/runtime-status` embeds that same summary instead of
recomputing a parallel provider-operations view.

Provider degradation controls are now explicit runtime behavior rather than a placeholder. The live
provider gateway tracks timeout, rate-limit, and upstream-error failures separately, reports degraded-upstream
versus circuit-open posture explicitly, and resets the circuit-open state through a configured cooldown
window instead of silent indefinite blocking.

Provider rollout posture is now also centralized in one small helper so activation readiness,
runbook readiness, and task-runtime notes all describe the same live-provider path honestly.
That keeps operator-facing status aligned when rollout is still stub-default versus when a live
provider has been allowlisted but remains intentionally disabled.

Provider operations durability now has an explicit repository seam and migration-managed
relational schema, and quota, budget, plus tracked degradation mutations all flow through that
configured provider-operations store instead of process-local counters. The durable control plane
now owns accepted-request counts, structured spend accumulation, timeout/rate-limit/upstream-error
failure tracking, and circuit-open cooldown timestamps, so operator truth remains consistent across
restart when the SQL-backed provider-operations path is enabled.

Those durable mutations now happen at the repository layer rather than through service-layer
read-modify-write sequences, which keeps provider blocking state closer to the authoritative store.
The provider-evidence and operations runbook surfaces also now treat that durable state model as
the real control plane: evaluation fixtures, recorded baselines, and operator guidance describe
restart-survival and durable recovery posture explicitly instead of assuming process-local resets.

That control plane now also exposes a dedicated reset-action history and bounded reset action
surface, so quota, budget, and degradation recovery can be reviewed as explicit operator actions
with reason and approval metadata instead of relying on ad hoc table edits or service restarts.

Audit persistence now also preserves task category, output label, and execution evidence, so
downstream inspection of prior executions does not depend on replaying the original task call.

Audit persistence now also preserves optional caller identity fields such as `requested_by` and
`tenant_id`, so support and review workflows retain the full caller traceability carried by the
task request rather than only application-level correlation metadata.

Audit inspection also supports a bounded catalog view now, with explicit caller, requester,
tenant, task, category, and output-label filters plus limit controls, so operator and support
workflows can inspect recent executions without relying only on direct request-id lookup.

Retrieval execution now also supports a deterministic catalog-only path for enabled staged
sources, so Lotus apps can get bounded preview hits from curated corpus metadata before live
vector retrieval is activated.

The initial enabled subset is intentionally small: Lotus platform RFCs and lotus-ai
architecture documents are searchable through the catalog-only path, while other staged
sources remain disabled until they are explicitly promoted.

Per-source rollout posture is also exposed through `/platform/retrieval/source-governance`, so
registered, staged-only, and currently searchable corpus slices are reviewed through an explicit
governance surface rather than inferred from raw source rows.

`knowledge_search.v1` now uses that same bounded retrieval path directly, so the task
execution surface has a real governed knowledge-search capability instead of a generic
placeholder for retrieval-class work.

`knowledge_answer.v1` now also builds a conservative source-backed answer on top of the same
bounded retrieval path, with explicit citations preserved in the task result payload.

Low-support retrieval matches now produce an explicit conservative refusal mode for
`knowledge_answer.v1` instead of a weak answer, which keeps the retrieval-backed task path
more defensible under the current catalog-only execution model.

Task runtime posture now also resolves through a dedicated execution-path helper so provider-backed
and retrieval-backed task routing semantics are defined in one place instead of being encoded only
inside runtime-status assembly.

Task runtime posture is now also exposed through a dedicated `/platform/tasks/runtime-status`
surface and embedded into `/platform/runtime-status`, so operators can distinguish stub-backed
task paths from retrieval-backed task paths without inferring that from task behavior alone.

Task execution activity is also exposed through `/platform/tasks/execution-summary`, which
samples persisted audit records to show category-level and provider-mode execution counts across
recent task runs.

`/platform/tasks/evidence-summary` adds a parallel bounded view over execution evidence,
including citation-bearing executions plus retrieval answer-mode counts for citation-backed
answers and conservative refusals.

`/platform/tasks/retrieval-summary` adds a retrieval-specific bounded view over recent
knowledge-search and knowledge-answer executions, including source usage, retrieval status,
and refusal patterns.

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
11. the contract boundary for future worker-backed execution,
12. the durable async-runtime repository and store seam that later worker-backed slices will cut over onto.

The first RFC-0006 delivery slice also adds explicit migration-managed async-runtime persistence
for jobs, attempts, and worker leases. Public async endpoints still remain documentation-backed at
this stage, but the durable storage seam now exists so later slices can cut over without inventing
runtime table creation or ad hoc persistence logic.

The next slice activates a narrow durable-submission posture on top of that seam. Allowlisted job
types can now be recorded into runtime-backed queue state and appear in the public async job
catalog/detail views as durable runtime records, while non-allowlisted job types remain explicitly
staged and artifact-backed until worker execution slices arrive.

### Providers

- `src/app/providers/`

Owns:

1. provider-specific execution adapters,
2. deterministic stub providers for foundation phase,
3. governed live-provider adapters that remain disabled by default until rollout permits activation,
4. the future boundary where live model SDK integrations will sit.

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

Current retrieval rollout posture includes:

1. retrieval activation readiness through `/platform/retrieval/activation-readiness`,
2. retrieval runbook readiness through `/platform/retrieval/runbook-readiness`,
3. retrieval evidence readiness through `/platform/retrieval/evidence-readiness`,
4. combined retrieval governance review through `/platform/retrieval/governance-status`.

Retrieval governance now summarizes technical activation, runbook, and evidence readiness
together.

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
3. provider quota posture is visible through `/platform/providers/quota-policy`,
4. provider budget posture is visible through `/platform/providers/budget-policy`,
5. provider operations posture is visible through `/platform/providers/operations-status`,
6. provider activation readiness is visible through `/platform/providers/activation-readiness`,
7. provider runbook readiness is visible through `/platform/providers/runbook-readiness`,
8. provider evidence readiness is visible through `/platform/providers/evidence-readiness`,
9. provider governance status is visible through `/platform/providers/governance-status`,
10. foundation-phase providers are documented and inspectable,
11. task execution already flows through an internal provider gateway,
12. runtime execution remains disabled until a stronger provider gateway and safety posture is in place.

`/platform/runtime-status` now embeds provider governance posture directly so operators can review
provider rollout state from the same top-level runtime surface that already carries async
governance posture. Provider governance now summarizes technical activation, runbook, and
evidence readiness together.

`/platform/runtime-status` now also embeds provider operations posture directly so operators can
review rollout-blocked versus operations-blocked state from the same top-level runtime surface
without stitching together quota, budget, and degradation-related endpoints manually.

Provider evidence readiness is now grounded in real evaluation assets rather than only a static
checklist: staged provider policy, runtime, failure-mode, operations, and degradation fixtures
plus a recorded provider regression baseline are visible directly through the governed
evidence-readiness surface.

Provider runbook readiness also now treats incident response and rollback as first-class required
activation items, so live-provider rollout cannot be considered operationally ready with only
generic escalation and dashboard guidance.

Provider runbook readiness now also treats spend-anomaly response and degradation/circuit-open
response as first-class required activation items, so the new provider operations controls cannot
be activated safely on paper while still being operationally unsupported.

## Prompt Posture

`lotus-ai` exposes governed prompt posture so downstream teams can inspect both runtime selection
and rollout readiness without relying on repository tribal knowledge.

Current rules:

1. prompt definition inventory is visible through `/platform/prompts`,
2. prompt governance posture is visible through `/platform/prompts/governance`,
3. prompt runtime selection is visible through `/platform/prompts/runtime-status`,
4. prompt activation readiness is visible through `/platform/prompts/activation-readiness`,
5. prompt runbook readiness is visible through `/platform/prompts/runbook-readiness`,
6. prompt evidence readiness is visible through `/platform/prompts/evidence-readiness`,
7. prompt governance status is visible through `/platform/prompts/governance-status`,
8. runtime prompt mutation remains disabled in foundation phase,
9. live prompt promotion remains repository-governed until a stronger activation model is introduced.

`/platform/runtime-status` now embeds prompt governance posture directly so operators can review
prompt rollout state from the same top-level runtime surface that already carries async, provider,
and retrieval governance posture. Prompt governance now summarizes technical activation, runbook,
and evidence readiness together.

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
