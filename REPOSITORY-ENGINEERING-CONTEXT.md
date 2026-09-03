# Repository Engineering Context

This file provides repository-local engineering context for `lotus-ai`.

For platform-wide truth, read:

1. `../lotus-platform/context/LOTUS-QUICKSTART-CONTEXT.md`
2. `../lotus-platform/context/LOTUS-ENGINEERING-CONTEXT.md`
3. `../lotus-platform/context/CONTEXT-REFERENCE-MAP.md`

## Repository Role

`lotus-ai` is the shared AI capability service for the Lotus ecosystem.

It provides governed AI task execution, retrieval, prompt, safety, evaluation, async, and workflow-pack control-plane foundations for other Lotus applications.

## Business And Domain Responsibility

This repository owns:

1. shared AI execution capabilities,
2. prompt, provider, retrieval, safety, and evaluation governance,
3. async AI run infrastructure,
4. workflow-pack registration and activation control-plane seams,
5. AI-specific observability, evidence, and control-plane surfaces.

It does not own portfolio, performance, risk, advisory, or management domain truth.

## Current Architecture

What `lotus-ai` is today, as one control plane rather than a set of subsystems.

**The execution spine.** A caller asks for a governed AI task or workflow pack. The
request is authenticated and authorized, bound to a prompt and an execution
configuration, routed to a provider candidate, executed, validated, and recorded
with evidence:

`caller identity → caller-policy authorization → task/pack binding → execution config
→ routing decision → provider execution → output validation → audit + evidence`

**Caller identity.** `LOTUS_AI_CALLER_TRUST_MODE` selects the boundary: `header`
(local runtimes; a startup finding in the promoted profile) or
`verified_service_jwt`, where the caller is the `sub` claim of a platform-issued
EdDSA credential verified against a configured issuer, audience, and rotating key
map. Failures are fail-closed `401 CALLER_CREDENTIAL_INVALID` with no header
fallback. Every protected router additionally requires the caller to be a
registered ACTIVE caller-policy entry; capability rules, tenant restriction, and
privileged audit scope all key off that policy.

**Execution configuration.** One frozen `ProviderExecutionConfig` per execution
carries model identity, endpoint, credential, sampling, and enforcement
thresholds. Evaluation and per-candidate routing install it through a contextvar
override, so no code path reads mutable process settings mid-request.

**Routing.** `LOTUS_AI_ROUTING_STRATEGY` is `fixed` (one configured identity) or
`ordered_fallback` (configured primary, then one governed alternate). Both
candidates pass the same fences under their own execution config: kill switches,
per-provider circuit breaker, and governed catalogue binding. Quota counters and
the budget envelope are request-scoped and charged once. Every execution records
a routing decision — each candidate, its rejection reason where rejected, the
selection, and the `fallback_path`. Whichever candidate serves, it is the one
named on every surface: audit record, routing decision, response, cost, metrics
labels, structured logs, tracing spans, bounded failure messages, breaker
evidence, and the attested run ledger all carry the serving identity.

**Model catalogue.** Provider, family, revision, deployment, and SKU are
first-class governed identity. Lifecycle state gates execution (a retired or
unapproved revision is refused with `MODEL_LIFECYCLE_INELIGIBLE`), catalogue rows
are seeded from configuration and from the approved model-risk inventory, and
revision drift is recorded from the provider echo. Identity-bound,
effective-dated rate cards price executions and carry cost posture onto audit
records.

**Output validation.** Every provider output — structured channel and narrative
message — passes one deterministic validator before safety redaction: evidence
grounding against supplied references, numeric grounding of percent and currency
tokens, per-task and per-pack JSON Schema contracts, and strict-JSON posture. The
verdict and an explicit `non_authoritative_ai_output` marking ride the response
and the audit record; a rejected output is withheld whole. The verdict is also
carried as execution evidence, so it reaches the run record and every projection
built from that bundle, and accepted-output publishes only what has a proven
`VALIDATED` verdict — a run whose evidence carries no verdict is refused rather
than grandfathered, because authority is proven at generation time or it is
absent. A workflow-pack family
cannot be registered without an output contract.

**Operator controls, deliberately distinct.** Routing selects an eligible
candidate; the circuit breaker is automatic health protection keyed per provider
identity, and an open circuit survives the deployment that rekeys its
bookkeeping or becomes a startup finding rather than a silent drop; kill
switches are explicit operator prohibition across six scopes with HARD_KILL and
DRAIN semantics; evaluation gates decide whether a model may be
eligible at all; lifecycle governs promotion and retirement. These are separate
mechanisms with separate evidence, composed into operator views rather than
merged into one state machine.

**Runtime profiles.** `LOTUS_AI_RUNTIME_PROFILE=promoted` derives the protection
set (retries with backoff, quota/budget/breaker enforcement, SQL-backed
provider-operations and admission stores, degrade readiness, enforce startup)
for keys the operator did not set explicitly. It never invents economic limits:
missing quota tables or budget ceilings are blocking startup findings.

**Durability and replicas.** Store-mode seams keep audit, prompts, retrieval,
caller policy, workflow-pack registry/run/task-flow/queue-event, provider
operations, model catalogue, rate cards, kill switches, and admission leases in
memory or in migration-backed SQL. Admission capacity binds across replicas
through atomic leases with TTL reclamation.

**Readiness as data.** The runbook-readiness family is one catalog plus one
builder; execution states are `ENFORCED` / `PARTIAL` / `DOCUMENTED_ONLY` /
`OUT_OF_SCOPE` and readiness is derived, never asserted. A lint-lane guard
refuses new copy-paste readiness modules and ratchets module size.

**Data lifecycle.** Retention is policy-as-data
(`contracts/data-lifecycle/retention-policy.v1.json`) over every ORM table, with
a bidirectional coverage invariant; one idempotent engine applies every declared
period (legal holds override expiry; six protective predicates keep live state —
enforcing switches, pending governed actions, in-flight jobs, review-retained
artifacts, current document versions, recurring drift — out of reach), and every
deletion writes an append-only `data_lifecycle_events` row referencing content
only by digest. Tenant erasure is a governed two-step `DATA_ERASURE` action
yielding an Ed25519-signed receipt verifiable against the published attestation
keys; erasure overrides retention, legal hold overrides erasure, and both are
recorded. Minimisation caps the audit `result_preview` at persistence and ages
passing evaluation-case content at a declared shorter horizon.

**Current limitations.** Capability requirements exist for latency (one governed
end-to-end budget), structured output, and tool calling (catalogue-evidence
eligibility inside the routing decision), with cost recorded as a preference;
cost has not yet graduated to a hard requirement (its billing-truth prerequisite
closed with #232), and residency, classification, and quality-floor dimensions
await concrete enforcement stories. Dual control binds two distinct verified
service credentials, not verified human principals — the platform identity
dependency recorded on #157's closure. Twenty-one activation/evidence readiness
modules still predate the readiness catalog (the runbook family converted in
#154; consolidation is #284). Provider-side retention execution and external
certification evidence remain externally blocked (#115, #122, #126). Forward
priorities live on the North Star execution board (#246).

## Architecture And Module Map

Primary areas:

1. `src/app/providers/`
   provider adapters and one shared execution transport (provider policy, quota,
   budget, and degradation state live in `src/app/services/`). Routing selects
   among candidates under `LOTUS_AI_ROUTING_STRATEGY`: `fixed` resolves the one
   configured identity, `ordered_fallback` attempts a configured primary then one
   governed alternate. Every execution records a routing decision — every
   candidate, its rejection reason where rejected, the selection, and the
   `fallback_path` — on its response, audit record, and evidence bundle.
2. `src/app/prompts/`
   prompt registry and rollout state.
3. `src/app/retrieval/`
   retrieval and indexed-search capabilities.
4. `src/app/services/safety_*.py`
   output controls and safety policy.
5. `src/app/evals/`
   evaluation and evidence foundations.
6. `src/app/services/`
   orchestration and runtime services.
7. `src/app/contracts/`
   public request and response models.
8. `src/app/routers/`
   API surfaces.
9. `docs/`
   architecture, standards, guides, and local RFCs.
10. `wiki/`
   canonical local source pages for the GitHub wiki and repo onboarding navigation.

## Runtime And Integration Boundaries

Runtime model:

1. shared FastAPI service with bounded AI control-plane and data-plane seams,
2. consumed by other Lotus apps for governed AI tasks,
3. workflow-pack registry records define runtime registration truth without centralizing business workflow logic,
4. workflow-pack default-version resolution is exposed as a conservative read-only control-plane
   route over registered, activation-eligible, non-superseded versions; it does not auto-promote
   discovered or dark successor versions,
5. workflow-pack registry records, workflow-pack run records, RFC-0097 task-flow records, and RFC-0098 queue-event records provide bounded, inspectable runtime posture without taking workflow authority, and these workflow-pack source-truth seams can move between in-memory and SQL-backed runtime posture through explicit governed store-mode seams,
6. does not replace upstream domain logic or workflow authority,
7. owns a thin HTTP boundary and shared problem-details error envelope while keeping business
   rules in routers/services and domain guardrails.

Boundary rules:

1. other Lotus apps provide structured business context and remain responsible for business meaning,
2. `lotus-ai` provides bounded governed AI capabilities with audit and evidence,
3. framework choices must not obscure control flow, governance, or auditability,
4. live-provider, retrieval, async, and workflow-pack control seams remain rollout-governed and evidence-backed,
5. every AI output carries a deterministic validation verdict and the `non_authoritative_ai_output` authority marking on the response and the audit record (evidence grounding, numeric grounding, per-task/per-pack JSON Schema contracts under `contracts/ai-task-outputs/`, strict-JSON posture); REJECTED outputs are withheld whole with the failing rule ids, a pack family without an output contract cannot be registered, and the eval runtime executes through the same pipeline so eval and production verdicts agree,
6. `LOTUS_AI_RUNTIME_PROFILE=promoted` applies the protection default set (retries with backoff, quota/budget/breaker enforcement, SQL-backed provider-operations and admission stores, degrade readiness, enforce startup) while explicit per-key settings always win; the setting-by-profile table lives in `docs/runbooks/service-operations.md` (Runtime Profile).

## Repo-Native Commands

Use these commands as the primary local contract:

1. install
   `make install`
2. fast local gate
   `make check`
3. PR-grade local gate
   `make ci`
4. runtime-mode smoke
   `make runtime-mode-smoke`
5. Docker build
   `make docker-build`
6. RFC-0002 Idea explanation proof gate
   `make rfc0002-idea-proof-gate`

## Validation And CI Expectations

`lotus-ai` uses explicit CI lanes:

1. `Remote Feature Lane`
2. `Pull Request Merge Gate`
3. `Main Releasability Gate`

Merged PRs to `main` dispatch `main-releasability.yml` through
`.github/workflows/merged-pr-main-releasability.yml`, so post-merge RFC and release evidence can
bind to the exact mainline commit.

Important validation expectations:

1. OpenAPI, evaluation-manifest, evaluation-run, async-job, and migration gates are active,
2. RFC-0002 Idea explanation local-dev proof is part of `make check` and `make ci`,
3. security and dependency health are part of the real CI contract,
4. coverage and Docker build are part of the merge gate,
5. AI posture changes should remain evidence-backed and bounded rather than speculative.

## Standards And RFCs That Govern This Repository

Most relevant current governance:

1. `../lotus-platform/rfcs/RFC-0069-lotus-ai-shared-ai-platform-service.md`
2. `../lotus-platform/rfcs/RFC-0072-platform-wide-multi-lane-ci-validation-and-release-governance.md`
3. `../lotus-platform/rfcs/RFC-0073-lotus-ecosystem-engineering-context-and-agent-guidance-system.md`
4. `docs/architecture/system-overview.md`
5. `docs/security/security-and-governance.md`

## Known Constraints And Implementation Notes

1. this service has a large documented current-state posture, so context drift is a serious risk if docs are not kept current,
2. live AI rollout must remain governed, bounded, and evidence-backed,
3. domain ownership should stay in the calling services even when `lotus-ai` adds value,
4. retrieval, prompt, provider, safety, and async seams should remain explicit and auditable,
5. `wiki/` inside the main repo is the authored source of truth for the repository wiki,
6. any separate local clone of `https://github.com/sgajbi/lotus-ai.wiki.git` is only a publish target
   and must not become a second maintained documentation source.

## Context Maintenance Rule

Update this document when:

1. major bounded capability posture changes,
2. live-provider or retrieval rollout posture changes materially,
3. repo-native commands or validation gates change,
4. architecture or control-plane seams change materially,
5. the service’s current phase or governance posture changes,
6. the wiki ownership or publication workflow changes,
7. new workflow-pack onboarding lessons become durable enough to help future pack owners or future agents.

## Cross-Links

1. `../lotus-platform/context/LOTUS-QUICKSTART-CONTEXT.md`
2. `../lotus-platform/context/LOTUS-ENGINEERING-CONTEXT.md`
3. `../lotus-platform/context/CONTEXT-REFERENCE-MAP.md`
4. `../lotus-platform/context/Repository-Engineering-Context-Contract.md`
5. [Lotus Developer Onboarding](../lotus-platform/docs/onboarding/LOTUS-DEVELOPER-ONBOARDING.md)
6. [Lotus Agent Ramp-Up](../lotus-platform/docs/onboarding/LOTUS-AGENT-RAMP-UP.md)
