# lotus-performance First Use-Case Contract

This guide defines the bounded first production-oriented downstream use case for `lotus-ai`.

## Selected Use Case

The first use case is `lotus-performance` analytics commentary over caller-supplied structured facts.

The target shape is:

1. `lotus-performance` computes analytics truth,
2. `lotus-performance` selects the material changes worth explaining,
3. `lotus-ai` turns that structured input into explanation-only commentary,
4. `lotus-performance` remains the owner of rendering and final user-facing interpretation.

## Contract Boundary

The first contract is intentionally narrow.

Required upstream fields:

1. `analysis_scope`
2. `period_window`
3. `metric_deltas`
4. `material_findings`

These fields should be structured and curated by `lotus-performance`. `lotus-ai` should not receive raw portfolio dumps as the primary contract for this use case.

## Readiness Signals

Use these runtime surfaces to review onboarding readiness without overstating downstream activation:

1. `GET /platform/use-cases/first-production-use-case`
2. `GET /platform/use-cases/first-production-use-case/readiness`
3. `GET /platform/use-cases/first-production-use-case/runbook-readiness`
4. `GET /platform/use-cases/first-production-use-case/governance-status`
5. `GET /platform/evals/runtime-status`

The bounded rollout review is currently grounded in:

1. explicit caller-policy registration for `lotus-performance`,
2. explanation-only safety posture for `EXPLANATION_ONLY` output,
3. a dedicated runtime-backed evaluation family for the first use case,
4. SQL-backed audit review for restart-safe support inspection,
5. observability and bounded incident-evidence review,
6. descriptor-first artifact review for bounded incident bundles.

## Rollout and Rollback Posture

Limited rollout should be treated as governed only when:

1. `/platform/use-cases/first-production-use-case/readiness` is ready,
2. `/platform/use-cases/first-production-use-case/runbook-readiness` is ready,
3. `/platform/use-cases/first-production-use-case/governance-status` reports `LIMITED_ROLLOUT_READY`.

Rollback posture is intentionally simple:

1. if first-use-case governance becomes blocked, downstream exposure should be treated as blocked,
2. unsupported or incomplete analytics inputs should be handled as a support and rollback review path, not normal explanation variance,
3. audit, observability incident summaries, and attached artifact descriptors are the primary review surfaces for that path.

## Ownership

`lotus-performance` owns:

1. analytics computation,
2. metric truth,
3. period selection,
4. materiality rules,
5. final user-facing rendering.

`lotus-ai` owns:

1. bounded explanation generation,
2. prompt, safety, audit, evidence, and observability posture for the task path,
3. explanation-only output discipline.

## Non-Goals

This first use case does not allow `lotus-ai` to:

1. recompute or infer portfolio analytics,
2. invent missing financial facts,
3. produce authoritative investment decisions,
4. replace downstream domain-owned interpretation.
