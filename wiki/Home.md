# lotus-ai

`lotus-ai` is the shared AI capability service for the Lotus ecosystem. It provides governed AI
execution and operator-facing control planes so downstream Lotus applications can use prompts,
retrieval, safety controls, evaluation gates, async execution, and provider-routing seams without
moving business authority out of the domain services that already own it.

## Why It Exists

Every Lotus application has work that an AI model could help with — explaining a performance
result, drafting commentary, classifying an exception, answering from governed documents. Built
per-application, each of those needs its own provider integration, prompt versioning, spend control,
safety labelling, audit trail and evaluation. Built five times, they drift, and the bank ends up
unable to answer a simple question: *what did the AI actually do, for whom, on what evidence?*

`lotus-ai` is that capability built once, with the governance attached rather than added later:

- **Domain authority stays where it belongs.** The service holds no portfolio, position or client
  record. Every output carries a label declaring its intended use, and no label authorises business
  execution. An application decides how output is applied; `lotus-ai` decides only that it was
  produced under policy.
- **Every execution leaves evidence.** Audit records, correlation identifiers and signed
  workflow-run attestations are produced by the execution path, not bolted on, so "what happened"
  is answerable after the fact rather than reconstructed.
- **Provider risk is bounded centrally.** Quota, budget, timeout, retry and circuit-breaker
  controls, plus rollout state and degradation posture, live in one place with operator surfaces —
  not scattered across the applications that call them.
- **Nothing is on by default.** Provider execution, retrieval and embeddings ship disabled, and
  activation is evidence-gated. Capability is switched on deliberately, per surface, with a readiness
  posture an operator can inspect.

The trade is explicitness over convenience: the service is deliberately larger in governance surface
than in execution surface, because in a private-banking context the question that matters is rarely
*can it answer* but *may it, and can we prove what it did*.

## Start Here

If you need the shortest accurate orientation, read these in order:

1. [Overview](Overview) — role and ownership boundaries
2. [Glossary](Glossary) — the vocabulary, including the four posture questions that account for
   a third of the API surface
3. [Architecture](Architecture) — measured shape, default posture, known gaps
4. [Getting Started](Getting-Started) — running it locally
5. [Configuration Reference](Configuration-Reference) — every setting and its default
6. [Validation and CI](Validation-and-CI) — gates, and what CI actually invokes
7. [Operations Runbook](Operations-Runbook) — operating and supporting it

## Current Posture

`lotus-ai` is in a governed foundation phase. That means two things at once:

1. the service already has real runtime seams and durable state for prompts, retrieval,
   evaluations, async jobs, and provider operations,
2. live provider rollout and broader production posture remain intentionally bounded and
   evidence-gated rather than assumed from the code shape alone.

## What lotus-ai Does

`lotus-ai` owns:

1. bounded AI task execution contracts,
2. prompt rollout and audit traceability,
3. governed retrieval and citation-carrying answer paths,
4. safety labeling and safety posture surfaces,
5. runtime-backed evaluation and approval gates,
6. async runtime for governed AI jobs,
7. provider policy, quota, budget, and degradation controls,
8. AI-specific observability and evidence surfaces.

It does not own portfolio, performance, risk, advisory, management, or reporting domain truth.

## Workflow-Pack Product Coverage

Current executable workflow-pack coverage is implementation-backed for 17 pilot-scoped families:

1. `advisor_brief.pack@v1`
2. `workspace_rationale.pack@v1`
3. `twr_inspection_support_brief.pack@v1`
4. `proposal_memo_commentary.pack@v1`
5. `advisory_copilot_proposal_explanation.pack@v1`
6. `advisory_copilot_evidence_qa.pack@v1`
7. `advisory_copilot_meeting_preparation.pack@v1`
8. `advisory_copilot_compliance_review_summary.pack@v1`
9. `advisory_copilot_operations_report_handoff.pack@v1`
10. `advisory_copilot_client_follow_up_draft.pack@v1`
11. `dpm_pm_memo.pack@v1`
12. `dpm_wave_pm_memo.pack@v1`
13. `dpm_exception_summary.pack@v1`
14. `dpm_operations_handoff_summary.pack@v1`
15. `outcome_review_narrative.pack@v1`
16. `pm_quality_summary.pack@v1`
17. `idea_explanation.pack@v1`

The proposal memo and DPM packs are deliberately support-only and review-gated.
`proposal_memo_commentary.pack@v1` consumes bounded `lotus-advise` memo evidence and records
review-required commentary lineage without changing memo evidence, suitability, approval, or
client-ready posture. The RFC-0027 advisory copilot packs consume Advise-owned evidence packets
with source refs, model-risk controls, review-required posture, and blocked client-ready posture;
they do not approve advice, waive policy, create orders, send client messages, or expose raw
prompt/payload details. `dpm_pm_memo.pack@v1` consumes
`lotus-manage` `DpmProofPackAiEvidenceInput`; `dpm_wave_pm_memo.pack@v1` and
`dpm_operations_handoff_summary.pack@v1` consume `lotus-manage` `DpmWaveReportInput`;
`dpm_exception_summary.pack@v1` consumes bounded `lotus-manage` monitoring exception evidence; and
`outcome_review_narrative.pack@v1` consumes `lotus-manage` `DpmOutcomeAiEvidenceInput`;
`pm_quality_summary.pack@v1` consumes Manage-owned `PmOperatingQualityScoreRun` evidence without
calculating scores, ranking PMs, or creating HR, compensation, conduct, client-contact, execution,
or OMS decisions. The
proof-pack, wave, handoff, and outcome packs can also consume optional manage-owned
`portfolio_memory_context` as bounded source lineage. They validate forbidden actions, forbidden
fields, requested output scope, portfolio-memory redaction/source-authority posture, run-ledger
posture, and source evidence before generated narrative can be treated as usable support.
`idea_explanation.pack@v1` consumes `lotus-idea` redacted opportunity evidence packets and remains
review-gated support-only; it cannot create suitability approval, proposal authority, rebalance
authority, client-ready publication, supported-feature promotion, or missing source evidence.
`make rfc0002-idea-proof-gate` now provides a deterministic local-dev proof that this execution,
review, source-safe lineage, and fail-closed attestation/provider-retention boundary remain intact.
Live-provider certification and downstream Idea consumption remain separate evidence classes.

## Supported Task Families

Current task families include:

1. `explain.v1`
2. `summarize.v1`
3. `classify.v1`
4. `extract.v1`
5. `generate_structured.v1`
6. `knowledge_search.v1`
7. `knowledge_answer.v1`

## Read by Need

If you are:

1. integrating another Lotus app, start with [Integrations](Integrations)
2. operating the service, start with [Operations Runbook](Operations-Runbook)
3. validating a change, start with [Validation and CI](Validation-and-CI)
4. learning the repository, start with [Architecture](Architecture)
5. debugging local runtime problems, start with [Troubleshooting](Troubleshooting)

## Source Documents

The wiki is a navigation and onboarding layer. Detailed source material lives in the repo:

- `README.md`
- `REPOSITORY-ENGINEERING-CONTEXT.md`
- `docs/architecture/system-overview.md`
- `docs/architecture/feature-status-and-roadmap.md`
- `docs/guides/task-execution-contract.md`
- `docs/runbooks/service-operations.md`

## Quick Commands

```powershell
make install
make check
make ci
uvicorn app.main:app --reload --port 8140
docker compose up --build
```
