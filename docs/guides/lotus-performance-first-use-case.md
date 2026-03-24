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
