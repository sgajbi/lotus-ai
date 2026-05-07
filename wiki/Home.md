# lotus-ai

`lotus-ai` is the shared AI capability service for the Lotus ecosystem. It provides governed AI
execution and operator-facing control planes so downstream Lotus applications can use prompts,
retrieval, safety controls, evaluation gates, async execution, and provider-routing seams without
moving business authority out of the domain services that already own it.

## Start Here

If you need the shortest accurate orientation, read these in order:

1. [Overview](./Overview.md)
2. [Architecture](./Architecture.md)
3. [Getting Started](./Getting-Started.md)
4. [Validation and CI](./Validation-and-CI.md)
5. [Operations Runbook](./Operations-Runbook.md)

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

Current executable workflow-pack coverage is implementation-backed for five pilot-scoped families:

1. `advisor_brief.pack@v1`
2. `workspace_rationale.pack@v1`
3. `twr_inspection_support_brief.pack@v1`
4. `dpm_pm_memo.pack@v1`
5. `outcome_review_narrative.pack@v1`

The DPM packs are deliberately support-only and review-gated. `dpm_pm_memo.pack@v1` consumes
`lotus-manage` `DpmProofPackAiEvidenceInput`; `outcome_review_narrative.pack@v1` consumes
`lotus-manage` `DpmOutcomeAiEvidenceInput`. Both validate forbidden actions, forbidden fields,
requested output scope, run-ledger posture, and source evidence before generated narrative can be
treated as usable support.

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

1. integrating another Lotus app, start with [Integrations](./Integrations.md)
2. operating the service, start with [Operations Runbook](./Operations-Runbook.md)
3. validating a change, start with [Validation and CI](./Validation-and-CI.md)
4. learning the repository, start with [Architecture](./Architecture.md)
5. debugging local runtime problems, start with [Troubleshooting](./Troubleshooting.md)

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
