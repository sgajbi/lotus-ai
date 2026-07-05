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
2. live provider rollout remains controlled and deliberately constrained, with production go-live
   governance covering both text-generation and embedding execution posture,
3. retrieval, prompts, provider policy, evaluation, async runtime, and governance are real first-class seams, and enabled retrieval now remains a production go-live blocker until retrieval governance and runtime-backed evaluation evidence are approval-ready,
4. workflow-pack registry truth now exists as a separate control-plane seam above capability-pack maturity, with owner-artifact references that must resolve back to the real downstream repository and with one governed store-mode seam that can keep activation state and control history in memory or in a migration-backed SQL store,
5. workflow-pack run-ledger foundations now exist as a separate runtime seam for the current
   executable workflow-pack families (`advisor_brief.pack`, `workspace_rationale.pack`,
   `proposal_memo_commentary.pack`, `advisory_copilot_proposal_explanation.pack`,
   `advisory_copilot_evidence_qa.pack`, `advisory_copilot_meeting_preparation.pack`,
   `advisory_copilot_compliance_review_summary.pack`,
   `advisory_copilot_operations_report_handoff.pack`,
   `advisory_copilot_client_follow_up_draft.pack`, `twr_inspection_support_brief.pack`,
   `dpm_pm_memo.pack`, `dpm_wave_pm_memo.pack`, `dpm_exception_summary.pack`,
   `dpm_operations_handoff_summary.pack`, `outcome_review_narrative.pack`, and
   `pm_quality_summary.pack`, and `idea_explanation.pack`), with runtime state
   kept separate from review state,
   bounded actor-attributed review transitions available through the ledger API, bounded
   ledger-compatible `allowed_review_actions` emitted for consumers, governed workflow-pack
   artifact refs now attached for bounded output-summary review, deterministic proposal memo
   commentary support for bounded `lotus-advise` memo evidence that cannot mutate memo status,
   suitability, approval, or client-ready posture, deterministic RFC-0027 advisory copilot
   guardrails that validate Advise-owned source-backed evidence packets, bounded requested outputs,
   required model-risk controls, review-required posture, blocked client-ready posture, unsupported
   claims, and forbidden technical fields before run/audit/task-flow side effects, deterministic proof-pack PM memo
   guardrails that validate manage-owned `DpmProofPackAiEvidenceInput`, required forbidden
   actions, forbidden fields, forbidden requested outputs, and optional source-lineage-only
   `portfolio_memory_context` before run/audit/task-flow side effects, deterministic wave PM memo
   guardrails that validate manage-owned `DpmWaveReportInput`, required forbidden actions,
   forbidden fields, forbidden requested outputs, source refs, proof-pack posture, no-external-execution
   posture, `NO_RAW_PAYLOADS`, and optional source-lineage-only `portfolio_memory_context` before
   run/audit/task-flow side effects, deterministic operations handoff summary guardrails that
   validate manage-owned `DpmWaveReportInput`, non-empty bounded handoff refs, required forbidden
   actions, forbidden fields, forbidden requested outputs, no-external-execution posture,
   `NO_RAW_PAYLOADS`, and optional source-lineage-only `portfolio_memory_context` before
   run/audit/task-flow side effects, deterministic exception summary guardrails that validate
   manage-owned monitoring exception evidence, bounded source refs, required forbidden actions,
   forbidden fields, forbidden requested outputs, `NO_RAW_PAYLOADS`, and support-only posture
   before run/audit/task-flow side effects, and deterministic
   outcome-review narrative guardrails that validate manage-owned `DpmOutcomeAiEvidenceInput`,
   required forbidden actions, forbidden fields, forbidden requested outputs, and optional
   source-lineage-only `portfolio_memory_context`, and deterministic PM quality summary guardrails
   that validate Manage-owned `PmOperatingQualityScoreRun` evidence, required non-use guardrails,
   source refs, bounded requested outputs, and optional source-lineage-only
   `portfolio_memory_context` before run/audit/task-flow side effects. The
   deterministic idea explanation execution validates `lotus-idea` caller authorization,
   required redacted evidence packet, bounded explanation request, supportability posture,
   review-required posture, unsupported claims, forbidden actions, and forbidden
   suitability/proposal/rebalance/client-publication authority before run/audit/task-flow side
   effects.
   The
   portfolio-memory context is consumed only as bounded lineage with matching portfolio identity,
   `NO_RAW_PAYLOADS` redaction, capped event refs, source content hash, and explicit
   no-reconstruction source-authority policy; generated outputs expose compact lineage summaries
   rather than reconstructed timeline facts. Operator-facing supportability profiles, grouped
   consumer views, run detail, filtered run catalog, shared review/supportability/provenance
   summaries, AI-owned source-event projections through `/platform/workflow-packs/source-events`
   and `/platform/workflow-packs/runs/{run_id}/source-events` for no-raw-payload portfolio-memory
   lineage consumption, explicit workflow-pack execution, reusable binding registry, queue policies,
   runtime-status activity, cross-pack attention, and RFC-0108 AI surface supportability now cover
   the expanded executable pack set. Gateway and Workbench product realization for proof-pack PM
   memo, wave PM memo, and outcome-review narrative remains downstream follow-on after the lotus-ai
   contracts are merged and proven; existing governed live downstream proof already exists through
   `lotus-workbench` -> `lotus-gateway` -> `lotus-ai`, `lotus-advise` -> `lotus-ai`, and
   `lotus-performance` -> `lotus-ai`, and a migration-backed SQL store is available for durable
   posture,
6. RFC-0097 task-flow foundations now exist for future long-running workflow-pack paths: typed flow, step, checkpoint, blocking-condition, replacement-lineage, handoff, runtime-state, review-state, and evidence descriptors are available, bounded lifecycle transitions are centralized, task-flow plus checkpoint state can run in memory or through a migration-backed SQL store with platform readiness reporting, read-only task-flow catalog/detail/checkpoint routes now expose inspection, Phase-1 workflow-pack execution records task-flow/checkpoint state for explicit and implicit pack-backed execution paths, workflow-pack review actions synchronize task-flow review posture plus replacement lineage, accepted task flows record explicit `READY_FOR_HANDOFF` posture for the workflow authority owner, and `/platform/runtime-status` now carries heartbeat-style task-flow attention for waiting, blocked, stale, and action-required flows; domain handoff execution remains a future slice,
7. RFC-0098 queue policy foundations now expose declarative per-pack queue policies, in-process queue admission capacity checks, bounded queue policy/status APIs, durable queue-event history for queue admission requests, queued posture, admitted posture, execution handoff, rejections, releases, timeout posture, cancellation posture, degraded queued-worker execution, governed queue request-snapshot artifact refs, governed retry/replay decision evidence, bounded retry/replay execution from retained request snapshots, and durable workflow-pack async execution submission through `/platform/workflow-packs/execute-async`; workflow-pack async jobs use the existing async runtime job, attempt, lease, delivery-queue, and dedicated-worker path while preserving queue events and run/task-flow records as separate source-truth seams behind memory or migration-backed SQL store modes, with platform readiness reporting for those stores and runtime-status `queue_attention` for source-backed saturation, stale active-admission posture, durable terminal timeout/cancellation/degraded queue events, blocked retry/replay recovery posture, repeated timeout/cancellation/blocked-recovery clusters, and degraded queue-source posture when configured queue dependencies are not ready,
8. RFC-0108 AI surface supportability now carries bounded `supportability_reason` values and
   explicit `metric_labels` truth for `lotus_ai_surface_supportability_state`, so operators can
   distinguish no-sensitive-telemetry degradation from workflow-pack run posture without relying on
   raw prompts, generated content, portfolio identifiers, correlation ids, or trace ids,
9. the FastAPI perimeter now has explicit service-owned HTTP boundary controls for allowed hosts,
   bounded CORS, secure response headers, opt-in HSTS, maximum request body size, and
   problem-details API errors with stable `error_code` and body/header correlation context,
10. the service is designed to support Lotus apps without stealing domain ownership from them.

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
