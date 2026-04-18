# Platform Surfaces

## Why This Page Exists

`lotus-ai` does not expose one flat API. It exposes a small direct execution surface plus a broad
set of platform, governance, and operator-facing surfaces.

This page groups the current public routes by router family so engineers can find the right surface
quickly without reading one long endpoint dump.

The groupings below are derived from the current FastAPI router layout in `src/app/main.py` and
`src/app/routers/`.

## Service Identity and Health Surface

Use these first when you need to answer "is the service up?" and "what mode is it running in?"

1. `/`
2. `/metadata`
3. `/health`
4. `/health/live`
5. `/health/ready`

## Direct Execution and Audit Surface

These are the smallest public integration surfaces and the ones most downstream callers start with.

1. `/ai/tasks/execute`
2. `/ai/audit`
3. `/ai/audit/{request_id}`

The separation matters:

1. `/ai/tasks/execute` is the bounded execution contract,
2. `/ai/audit` is the persisted execution and evidence review surface.

## Capability and Task-Runtime Surface

These surfaces tell you what `lotus-ai` can do and how task execution is behaving in practice.

1. capability catalog
   - `/platform/capabilities`
2. task-runtime posture and sampled execution summaries
   - `/platform/tasks/runtime-status`
   - `/platform/tasks/execution-summary`
   - `/platform/tasks/evidence-summary`
   - `/platform/tasks/retrieval-summary`

This is distinct from the direct execution API. It is the inspection and support surface around
task execution, not the execution entrypoint itself.

## Core Platform Governance Surface

These top-level operator and rollout surfaces describe broad service posture and cross-cutting
platform programs.

1. overall runtime posture
   - `/platform/runtime-status`
2. app-capability rollout governance
   - `/platform/app-capability-rollouts`
   - `/platform/app-capability-rollouts/governance-status`
   - `/platform/app-capability-rollouts/observability-summary`
   - `/platform/app-capability-rollouts/lifecycle-status`
   - `/platform/app-capability-rollouts/{downstream_app}/{capability_pack_id}`
   - `/platform/app-capability-rollouts/{downstream_app}/{capability_pack_id}/governance-status`
   - `/platform/app-capability-rollouts/{downstream_app}/{capability_pack_id}/lifecycle-status`
   - `/platform/app-capability-rollouts/{downstream_app}/{capability_pack_id}/onboarding-template`
3. cross-cutting rollout programs
   - `/platform/resilience/*`
   - `/platform/deployment-split/*`
   - `/platform/production-baseline/*`
   - `/platform/production-go-live/*`
4. workflow-pack runtime registration
   - `/platform/workflow-packs/registry`
   - `/platform/workflow-packs/registry/{pack_id}/{version}`

## Provider Surface

Prefix:

- `/platform/providers`

This family covers:

1. provider catalog and execution policy
2. operator profile
3. quota and budget policy
4. operations status
5. control-plane history and reset action
6. activation, runbook, evidence, and governance readiness

Key routes:

- `/platform/providers`
- `/platform/providers/policy`
- `/platform/providers/operator-profile`
- `/platform/providers/quota-policy`
- `/platform/providers/budget-policy`
- `/platform/providers/operations-status`
- `/platform/providers/control-plane-actions`
- `/platform/providers/control-plane-actions/reset`
- `/platform/providers/activation-readiness`
- `/platform/providers/runbook-readiness`
- `/platform/providers/evidence-readiness`
- `/platform/providers/governance-status`

## Prompt Surface

Prefix:

- `/platform/prompts`

This family covers:

1. prompt catalog and prompt-by-task detail
2. prompt governance and control history
3. prompt control actions
4. runtime, activation, runbook, evidence, and governance readiness

Key routes:

- `/platform/prompts`
- `/platform/prompts/{task_id}`
- `/platform/prompts/governance`
- `/platform/prompts/control-history`
- `/platform/prompts/control-actions`
- `/platform/prompts/runtime-status`
- `/platform/prompts/activation-readiness`
- `/platform/prompts/runbook-readiness`
- `/platform/prompts/evidence-readiness`
- `/platform/prompts/governance-status`

## Retrieval Surface

Prefix:

- `/platform/retrieval`

This is one of the broadest surfaces in the service. It covers:

1. source, document, and chunk inspection
2. source and document governance
3. runtime, index, ingestion, and execution status
4. indexing and ingestion job catalogs plus async submission paths
5. activation, runbook, evidence, and governance readiness
6. bounded retrieval search

Key route families:

- `/platform/retrieval/sources`
- `/platform/retrieval/source-governance`
- `/platform/retrieval/document-governance`
- `/platform/retrieval/index-status`
- `/platform/retrieval/runtime-status`
- `/platform/retrieval/ingestion-status`
- `/platform/retrieval/ingestion-jobs`
- `/platform/retrieval/ingestion-jobs/{job_id}`
- `/platform/retrieval/ingestion-jobs/{job_id}/submit-async`
- `/platform/retrieval/execution-status`
- `/platform/retrieval/activation-readiness`
- `/platform/retrieval/runbook-readiness`
- `/platform/retrieval/evidence-readiness`
- `/platform/retrieval/governance-status`
- `/platform/retrieval/indexing-policy`
- `/platform/retrieval/index-jobs`
- `/platform/retrieval/index-jobs/{job_id}`
- `/platform/retrieval/index-jobs/{job_id}/submit-async`
- `/platform/retrieval/sources/{source_id}/documents`
- `/platform/retrieval/documents/{document_id}/chunks`
- `/platform/retrieval/search`

## Safety Surface

Prefix:

- `/platform/safety`

This family is intentionally compact:

1. policy
2. runtime status
3. activation readiness
4. runbook readiness
5. governance status

## Artifact Surface

Prefix:

- `/platform/artifacts`

This family covers the governed artifact backbone rather than raw payload download:

1. runtime status
2. descriptor-first catalog
3. activation readiness
4. runbook readiness
5. governance status

## Evaluation Surface

Prefix:

- `/platform/evals`

This family covers:

1. evaluation catalog
2. runtime status
3. run catalog and run detail
4. run submission
5. fixture detail

Key routes:

- `/platform/evals/catalog`
- `/platform/evals/runtime-status`
- `/platform/evals/runs`
- `/platform/evals/runs/submit`
- `/platform/evals/fixtures/{fixture_id}`
- `/platform/evals/runs/{run_id}`

## Async Runtime Surface

Prefix:

- `/platform/async`

This family covers:

1. runtime status
2. queue-backend and worker-execution inventory
3. activation, runbook, and governance readiness
4. control-plane history and apply action
5. job catalog, job detail, and submission

Key routes:

- `/platform/async/runtime-status`
- `/platform/async/queue-backends`
- `/platform/async/worker-executions`
- `/platform/async/activation-readiness`
- `/platform/async/runbook-readiness`
- `/platform/async/governance-status`
- `/platform/async/control-plane-actions`
- `/platform/async/control-plane-actions/apply`
- `/platform/async/jobs`
- `/platform/async/jobs/{job_id}`
- `/platform/async/jobs/submit`

## Observability Surface

Prefix:

- `/platform/observability`

This family covers:

1. runtime, activation, runbook, and governance posture
2. incident summary
3. bounded summaries by provider, retrieval, async, evaluation, prompt, and safety
4. breakdown views for operator analysis

## Access-Control Surface

Prefix:

- `/platform/access-control`

This family covers:

1. runtime status
2. activation readiness
3. runbook readiness
4. governance status
5. caller policy catalog

## Capability-Pack and Use-Case Adoption Surface

These are the app-facing rollout and onboarding surfaces rather than low-level runtime inspection.

1. capability packs
   - `/platform/capability-packs`
   - `/platform/capability-packs/governance-status`
   - `/platform/capability-packs/{pack_id}`
   - `/platform/capability-packs/{pack_id}/adoption-template`
   - `/platform/capability-packs/{pack_id}/observability-summary`
   - `/platform/capability-packs/{pack_id}/activation-readiness`
   - `/platform/capability-packs/{pack_id}/runbook-readiness`
   - `/platform/capability-packs/{pack_id}/governance-status`
2. workflow-pack registry
   - `/platform/workflow-packs/registry`
   - `/platform/workflow-packs/registry/{pack_id}/{version}`
3. app-capability rollouts
   - `/platform/app-capability-rollouts`
4. first production use-case and onboarding templates
   - `/platform/use-cases/first-production-use-case`
   - `/platform/use-cases/first-production-use-case/readiness`
   - `/platform/use-cases/first-production-use-case/runbook-readiness`
   - `/platform/use-cases/first-production-use-case/governance-status`
   - `/platform/use-cases/onboarding-template`

These are important when the work is about downstream adoption and rollout governance rather than
one isolated task call.

## Read Next

1. use [Integrations](./Integrations.md) for how downstream systems should consume these surfaces,
2. use [Operations Runbook](./Operations-Runbook.md) for the runtime interpretation of these groups,
3. use [Troubleshooting](./Troubleshooting.md) when one surface says something different from another.
