# RFC-0020: Production-Standard Deployment Baseline

- Status: Draft
- Date: 2026-03-24
- Owners: lotus-ai
- Requires Approval From: lotus-ai maintainers

## Summary

`lotus-ai` now has enough governed platform capability to support a real downstream use case and a live-provider path, but the repo still lacks one explicit production-standard deployment baseline for the current single-deployable service shape.

This RFC defines that baseline.

It standardizes how `lotus-ai` should be deployed before later deployment split and disaster-recovery work:

1. one production-standard runtime topology for the current service,
2. explicit production-only versus local fallback infrastructure,
3. governed startup, migration, worker, secret, and artifact posture,
4. truthful runtime, readiness, and governance reporting for production posture.

## Why This RFC Exists

The first downstream and Docker demo passes surfaced a real gap:

1. the platform contracts worked,
2. the Docker path worked after targeted fixes,
3. the live-provider path is reachable,
4. but the repo does not yet define one clear production-standard setup that operators can treat as the baseline go-live posture.

Existing RFCs cover adjacent concerns, but not this exact gap:

1. `RFC-0015` is about later deployment split into runtime, retrieval, and eval planes,
2. `RFC-0017` is about resilience, backup, restore, and disaster recovery,
3. this RFC comes before both and defines the first production-standard single-deployable posture.

## Evidence From Recent Demo Passes

Two recent demo passes sharpen the problem this RFC must solve.

### Dockerized Stub Pass

The Dockerized first-use-case pass proved that the current service can run successfully in a deployment-shaped local topology, but it also exposed hidden deployment assumptions:

1. checked-in compose startup needed hardening before it worked cleanly,
2. migrations were not applied automatically at container startup,
3. required runtime assets were missing from the image,
4. deployment success depended on local knowledge rather than an explicit production baseline.

### Dockerized Live-Provider Pass

The Dockerized live-provider pass proved that the OpenAI path can execute successfully in the current service shape, but it also exposed why "works in Docker" is still not the same as "production-ready":

1. live provider execution required a demo-only caller-policy override for `lotus-performance`,
2. the first-use-case rollout gate correctly fell back from ready to blocked,
3. the service was still running on local fallback classes such as SQLite and local env-file secret handling,
4. provider governance remained explicitly incomplete even though one live request succeeded.

This RFC therefore must distinguish:

1. local or demo-capable posture,
2. prod-shaped local posture,
3. actual production-ready posture.

## Problem Statement

Today, `lotus-ai` can be run successfully in several ways:

1. source-run local workflows,
2. Dockerized local workflows,
3. durable SQL-backed control planes,
4. live-provider execution when explicitly configured.

That flexibility is useful during build-out, but it creates ambiguity about what is truly acceptable for production.

The repo still allows or relies on postures that are acceptable for local or demo use but should not define production:

1. SQLite-backed durable state,
2. local filesystem artifact payload storage as a fallback,
3. ad hoc project env files for live secrets,
4. container startup paths that need explicit production hardening and governance,
5. deployment behavior that is operationally valid but not yet called out as the required production baseline.

Without one explicit baseline, `lotus-ai` risks:

1. demos being mistaken for production posture,
2. different environments drifting into inconsistent durable-state or secret-handling choices,
3. governance surfaces overstating readiness,
4. later split and resilience work being built on an ambiguous base.

## Posture Model

This RFC defines three distinct posture classes.

### Local or Demo-Capable

This posture is valid for engineering validation, demos, and RFC proof:

1. SQLite may still be present,
2. local `.env` files may still be used,
3. local filesystem or memory-backed artifact payload storage may still be used,
4. demo-only caller-policy overrides may still be used,
5. successful execution does not imply production readiness.

### Prod-Shaped Local

This posture is stronger than a basic demo, but still not production:

1. API, worker, and Redis run in containerized topology,
2. PostgreSQL-backed durable store seams are active instead of SQLite or memory-backed durable state,
3. startup, migrations, and asset packaging are exercised,
4. live provider execution may be tested,
5. local secret files or fallback object storage may still exist,
6. governance may remain intentionally blocked.

### Production-Ready

This is the only posture this RFC considers acceptable for go-live:

1. PostgreSQL-backed authoritative state,
2. dedicated worker plus Redis queue active,
3. governed object storage active rather than local fallback,
4. deployment-managed secret injection,
5. no demo-only caller-policy overrides,
6. runtime, readiness, runbook, and governance surfaces all agree that production posture is ready.

## Goals

1. Define one truthful production-standard deployment baseline for the current single-deployable `lotus-ai` service.
2. Distinguish clearly between local fallback posture and acceptable production posture.
3. Standardize production requirements for:
   1. API process,
   2. dedicated worker,
   3. Redis queue,
   4. PostgreSQL-backed durable state,
   5. governed object storage,
   6. secret injection,
   7. startup migration behavior,
   8. health, readiness, and governance reporting.
4. Make production-readiness inspectable from runtime and governance surfaces rather than only documentation.
5. Leave `lotus-ai` ready for later `RFC-0015` deployment split and `RFC-0017` resilience work without redoing the baseline.

## Non-Goals

1. Splitting `lotus-ai` into separate deployable services.
2. Full disaster-recovery automation, backup orchestration, or restore drills.
3. Multi-region, active-active, or cross-cloud topology.
4. Turning `lotus-ai` into a Kubernetes-specific design only.
5. Broad product-surface expansion unrelated to production deployment posture.

## Production Baseline Decision

The first production-standard baseline for `lotus-ai` is:

1. one externally coherent `lotus-ai` API deployment,
2. one dedicated `lotus-ai` worker deployment,
3. Redis as the managed queue backend,
4. PostgreSQL as the authoritative relational store for all SQL-backed domains,
5. governed object storage as the production artifact payload store,
6. injected secrets through deployment-managed secret handling rather than checked-in or ad hoc local env patterns,
7. startup or release behavior that guarantees required migrations are applied before the runtime is treated as ready,
8. production-readiness surfaces that block if the service falls back to local-only infrastructure classes.

## Required Production Invariants

### Durable State

Production must not rely on local SQLite for authoritative runtime state.

Required behavior:

1. audit, prompt rollout, retrieval metadata, access control, provider operations, async runtime, evaluation runtime, and artifact metadata all run on PostgreSQL through the existing SQL-backed store seams,
2. runtime and governance surfaces report production as blocked when the service remains on SQLite or in-memory durable-state substitutes,
3. migration state is explicit and observable.

### Async Execution

Production must run the dedicated worker path.

Required behavior:

1. API replicas do not act as the primary execution path for allowlisted async job types,
2. Redis-backed queue delivery and dedicated-worker execution remain active,
3. drain, degraded, and backlog posture remain observable.

### Artifact Payload Storage

Production must not use local-memory or local-filesystem fallback object storage as the accepted production posture.

Required behavior:

1. artifact metadata remains relational,
2. payload bytes are stored in a governed object store,
3. public contracts remain descriptor-first and never expose raw backend URLs,
4. production-readiness blocks while artifact payload storage is still in local fallback mode.

### Live Provider Configuration

Production live-provider posture must be explicit and bounded.

Required behavior:

1. live provider activation remains governed by rollout, allowlist, caller policy, and evaluation evidence,
2. provider credentials are injected securely and are never checked into the repo,
3. production runtime surfaces distinguish configured, activatable, degraded, and blocked posture truthfully,
4. the first downstream use case must not be treated as production-ready merely because live-provider execution is technically possible.

### Secret Handling

Production secrets must not be managed as ordinary project files.

Required behavior:

1. production secrets are injected through deployment-managed secret handling,
2. local `.env` files remain explicitly local-only and non-production,
3. docs and runbooks distinguish local demo setup from production secret posture clearly.

### Startup and Release Behavior

Production startup must be explicit and safe.

Required behavior:

1. required migrations must be applied before the service is considered ready,
2. startup behavior must be deterministic and reviewable,
3. image contents must include the assets required by runtime-governed features,
4. release behavior must avoid hidden startup assumptions discovered only during bring-up.

## Runtime and Governance Requirements

This RFC requires a production-standard governance layer, not only infrastructure configuration.

The platform must expose:

1. production-baseline runtime status,
2. production activation readiness,
3. production runbook readiness,
4. production governance status.

Those surfaces must answer, at minimum:

1. is the service using PostgreSQL rather than SQLite,
2. is the dedicated worker fleet active,
3. is Redis queue delivery active,
4. is object storage production-grade rather than fallback,
5. are live-provider secrets injected through an acceptable posture,
6. are migrations and startup dependencies satisfied,
7. are operators looking at a production-capable posture or only a local/demo-capable posture.

This RFC should introduce one explicit posture classification that can distinguish:

1. `LOCAL_OR_DEMO_CAPABLE`,
2. `PROD_SHAPED_LOCAL`,
3. `PRODUCTION_READY`.

## Delivery Slices

### Slice 1: Production Baseline Contract and Runtime Inventory

Outcome:

1. explicit production-baseline contracts exist,
2. current runtime posture can be evaluated against the required baseline,
3. local-only fallbacks are classified clearly,
4. "prod-shaped" and "production-ready" are no longer conflated.

Acceptance gate:

1. one typed runtime surface exists for production-baseline posture,
2. every major runtime dependency is classified as production-standard, fallback, or blocked,
3. platform status remains truthful,
4. at least these dependencies are classified explicitly:
   1. database backend,
   2. queue backend,
   3. worker mode,
   4. artifact payload backend,
   5. secret posture,
   6. migration posture,
   7. live-provider rollout posture.

### Slice 2: Production Deployment Configuration Hardening

Outcome:

1. Docker and deployment startup paths reflect the required production baseline,
2. migration behavior is deterministic,
3. image contents and runtime config no longer rely on accidental local assumptions,
4. the checked-in deployment example can represent the intended production-shaped baseline honestly.

Acceptance gate:

1. the containerized stack can run in the intended baseline shape,
2. startup and worker paths are explicit,
3. required runtime assets are present,
4. tests and demo validation prove the hardened deployment path,
5. no container success depends on undocumented manual fixes discovered only during bring-up.

### Slice 3: Production Storage and Secret Posture Enforcement

Outcome:

1. PostgreSQL-backed durable state is required for production-ready posture,
2. artifact payload storage distinguishes production-grade object storage from local fallback,
3. secret posture is classified explicitly,
4. live-provider success no longer masks a blocked production baseline.

Acceptance gate:

1. governance blocks production posture on SQLite, fallback object storage, or local-only secret handling,
2. docs and runtime surfaces agree on those blocks,
3. no production summary overstates the fallback path,
4. first-use-case and provider governance can remain blocked while live execution still succeeds, and that distinction is visible to operators.

### Slice 4: Runbook, Readiness, and Go-Live Governance

Outcome:

1. operators have a production-standard runbook,
2. production go-live and rollback posture are explicit,
3. downstream onboarding can refer to a real production baseline rather than demo guidance,
4. local demo setup and production setup have clearly separated operator instructions.

Acceptance gate:

1. activation-readiness, runbook-readiness, and governance-status surfaces are implemented,
2. docs match runtime truth,
3. local/demo posture and production posture are explicitly separated,
4. service documentation can point to one production-standard baseline without caveats hidden in demo guides.

## Risks

1. folding too much resilience or split-deployment work into this RFC would blur scope and slow delivery,
2. under-specifying the baseline would let demo posture keep masquerading as production posture,
3. overcommitting to one deployment substrate could make the RFC less portable than needed,
4. delaying this RFC would keep real go-live decisions too dependent on local demo knowledge.

## Alternatives Considered

### Alternative 1: Treat RFC-0015 as the Production Setup RFC

Rejected.

Reason:

1. deployment split is a later topology concern,
2. the current gap exists even before any split is attempted.

### Alternative 2: Fold This Entirely Into RFC-0017

Rejected.

Reason:

1. resilience and DR come after the service has one accepted production baseline,
2. the platform needs a clean production-standard setup before deeper DR work is actionable.

### Alternative 3: Continue With Ad Hoc Docker Hardening Only

Rejected.

Reason:

1. the live and Docker demo passes already showed that hidden deployment assumptions surface too late without an RFC,
2. the platform now needs governed runtime truth, not only working local scripts.

## Initial Implementation Focus

The first implementation pass for this RFC should stay narrowly focused on the current single-service topology and the exact gaps surfaced by the demo work:

1. add production-baseline posture contracts and endpoints,
2. harden the checked-in container topology to the intended baseline,
3. block production posture on SQLite, local secret files, and fallback object storage,
4. separate "live provider technically works" from "use case and provider governance are approved",
5. update runbooks so operators can tell whether they are looking at demo guidance or production guidance.

## Acceptance Criteria

This RFC is complete when:

1. `lotus-ai` has one explicit production-standard deployment baseline for the current single-deployable service,
2. production runtime and governance surfaces can distinguish production-capable versus local/demo fallback posture,
3. PostgreSQL, Redis, dedicated workers, and governed object storage are treated as the required production backbone,
4. secret handling and startup migration posture are explicit and reviewable,
5. docs, runbooks, and runtime surfaces all describe the same production truth,
6. the platform is ready to build `RFC-0015` and `RFC-0017` on top of a non-ambiguous base.

## Approval Requested

Approve this RFC if the team agrees that:

1. `lotus-ai` now needs a production-standard single-service baseline before further scale and resilience work,
2. Docker/demo-capable posture should no longer stand in for production posture,
3. PostgreSQL, Redis, dedicated workers, governed object storage, and deployment-managed secrets should define the first production baseline,
4. implementation should proceed through the slices above.
