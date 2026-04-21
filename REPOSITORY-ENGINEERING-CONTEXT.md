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

## Current-State Summary

Current repository posture:

1. `lotus-ai` now has an implemented bounded workflow-pack runtime foundation for the current
   Phase-1 pack families, with broader pack-family expansion remaining follow-on work,
2. live provider rollout remains controlled and deliberately constrained,
3. retrieval, prompts, provider policy, evaluation, async runtime, and governance are real first-class seams,
4. workflow-pack registry truth now exists as a separate control-plane seam above capability-pack maturity, with owner-artifact references that must resolve back to the real downstream repository and with one governed store-mode seam that can keep activation state and control history in memory or in a migration-backed SQL store,
5. workflow-pack run-ledger foundations now exist as a separate runtime seam for the current three Phase-1 workflow-pack families (`advisor_brief.pack`, `workspace_rationale.pack`, and `twr_inspection_support_brief.pack`), with runtime state kept separate from review state, bounded actor-attributed review transitions available through the ledger API, bounded ledger-compatible `allowed_review_actions` emitted for consumers, governed workflow-pack artifact refs now attached for bounded output-summary review, an operator-facing supportability profile available for run-level diagnosis that now also exposes the latest event type, latest event actor, the latest recorded review-transition actor and timestamp, bounded review-transition counts, bounded per-event-type history counts, and one bounded provenance summary describing linked artifact and evidence posture, a grouped consumer-view contract available for downstream composition layers that now also carries explicit supportability posture, the latest recorded review-transition actor, timestamp, and bounded review-history counts, plus one bounded provenance summary describing linked artifact and evidence posture, the run-detail route now also carries shared review-progression posture, shared supportability posture, and one bounded provenance summary alongside raw history and lineage so callers can inspect review and provenance posture without scanning every linked descriptor first, each run descriptor in the filtered run catalog now also carries a bounded `review_summary` block with latest review-transition actor, timestamp, and history counts so downstream triage and composition layers do not need raw event fetches just to understand review provenance, a shared run-review-summary seam now grounding catalog, consumer-view, run-detail, and estate-level runtime-status review metadata, a shared run-supportability seam now grounding operator-profile posture, consumer-view posture, run-detail posture, per-run descriptor posture, and estate-level workflow-pack activity posture, a shared run-provenance-summary seam now grounding consumer-view posture, run-detail posture, operator-profile posture, and estate-level runtime-status artifact and evidence linkage summaries, a filtered run-catalog surface now available so operators and downstream services can query backlog slices by registration, caller app, tenant id, workflow surface, runtime state, review state, supportability posture, workflow-authority owner, and bounded limit instead of reconstructing triage client-side, with server-side ready, action-required, and historical supportability cohort counts now emitted for the returned slice, an explicit `supportability_status` now carried on each workflow-pack run descriptor, an explicit workflow-pack execution route and a reusable binding registry now available for implemented Phase-1 pack paths instead of relying only on inferred task execution, with registration records remaining the source of caller and workflow-surface scope while bindings stay focused on task-shape truth and now being validated through the same registry path, with registry inspection now also exposing bounded explicit execution-binding metadata for implemented pack versions, with `/platform/runtime-status` now exposing both the estate-level count of registered-versus-explicitly-executable workflow-pack versions, the subset whose registered execution mode still requires review gating, a bounded workflow-pack run summary covering review backlog plus action-required run posture, per-pack activity counts plus supportability counts for executable pack versions including direct pointers to the latest ready and latest action-required runs plus their bounded review provenance and bounded artifact or evidence linkage summaries, and a bounded cross-pack attention queue for the newest actionable runs now also carrying review provenance plus bounded artifact or evidence linkage summaries, with shared Phase-1 specs grounding seed registration and execution-binding metadata, with governed live downstream proof now existing through `lotus-workbench` -> `lotus-gateway` -> `lotus-ai`, `lotus-advise` -> `lotus-ai`, and `lotus-performance` -> `lotus-ai`, and with a migration-backed SQL store available for durable posture,
6. RFC-0097 task-flow foundations now exist for future long-running workflow-pack paths: typed flow, step, checkpoint, blocking-condition, replacement-lineage, handoff, runtime-state, review-state, and evidence descriptors are available, bounded lifecycle transitions are centralized, and task-flow plus checkpoint state can run in memory or through a migration-backed SQL store with platform readiness reporting; public task-flow APIs, gateway adoption, Workbench adoption, heartbeat attention, and domain handoff execution remain future slices,
7. the service is designed to support Lotus apps without stealing domain ownership from them.

## Architecture And Module Map

Primary areas:

1. `src/app/providers/`
   provider adapters and routing.
2. `src/app/prompts/`
   prompt registry and rollout state.
3. `src/app/retrieval/`
   retrieval and indexed-search capabilities.
4. `src/app/safety/`
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
4. workflow-pack registry records, workflow-pack run records, and RFC-0097 task-flow records provide bounded, inspectable runtime posture without taking workflow authority, and all three can move between in-memory and SQL-backed runtime posture through explicit governed store-mode seams,
5. does not replace upstream domain logic or workflow authority.

Boundary rules:

1. other Lotus apps provide structured business context and remain responsible for business meaning,
2. `lotus-ai` provides bounded governed AI capabilities with audit and evidence,
3. framework choices must not obscure control flow, governance, or auditability,
4. live-provider, retrieval, async, and workflow-pack control seams remain rollout-governed and evidence-backed.

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

## Validation And CI Expectations

`lotus-ai` uses explicit CI lanes:

1. `Remote Feature Lane`
2. `Pull Request Merge Gate`
3. `Main Releasability Gate`

Important validation expectations:

1. OpenAPI, evaluation-manifest, evaluation-run, async-job, and migration gates are active,
2. security and dependency health are part of the real CI contract,
3. coverage and Docker build are part of the merge gate,
4. AI posture changes should remain evidence-backed and bounded rather than speculative.

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
