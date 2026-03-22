# Evaluation Strategy

`lotus-ai` must be testable in a way that matches its intended role as enterprise-facing AI infrastructure.

## Evaluation Principles

1. Every supported task should have golden examples.
2. Output structure matters as much as output quality.
3. Hallucination risk should be measured explicitly for retrieval-backed flows.
4. Prompt changes should be regression-tested before promotion.
5. Evaluation should be cheap enough to run often.

## Evaluation Layers

### Contract evaluations

Check:

1. schema validity,
2. required metadata presence,
3. deterministic error handling,
4. policy gating behavior.

### Retrieval evaluations

Check:

1. source selection quality,
2. citation presence,
3. freshness/provenance behavior,
4. refusal behavior when sources are insufficient.

### Prompt regression evaluations

Check:

1. output stability against approved examples,
2. expected tone and enterprise posture,
3. no leakage of disallowed content,
4. no structural regression.

### Domain-integration evaluations

Check:

1. domain context assembly quality,
2. correct task choice,
3. downstream rendering compatibility,
4. audit trail completeness.

## First Evaluation Assets To Add

1. task capability contract fixtures,
2. explanation task fixture set,
3. summarization fixture set,
4. retrieval citation fixture set.

## Current Execution Evidence

`lotus-ai` task responses now carry a typed execution evidence bundle.

Current evidence categories:

1. task contract selection,
2. prompt selection,
3. provider resolution,
4. safety outcome,
5. retrieval posture.

This evidence is intentionally deterministic in foundation phase so later evaluation and regression
work has a stable evidence schema to build on.

The current platform inspection surface for evaluation readiness is:

1. `GET /platform/evals/catalog`
2. `GET /platform/evals/runtime-status`
3. `GET /platform/evals/fixtures/{fixture_id}`

This catalog exposes:

1. current execution evidence categories,
2. staged fixture families,
3. the current delivery-phase posture for evaluation assets.

Fixture-family detail exposes:

1. the governed descriptor for a specific fixture family,
2. associated `task_id` when available,
3. case-level metadata such as `case_id` and `summary` without surfacing mutable payload internals through the API.

The source of truth for fixture inventory is now:

1. [fixture-manifest.json](C:/Users/Sandeep/projects/lotus-ai/docs/evals/fixture-manifest.json)

This manifest is versioned so evaluation catalog and runtime status surfaces can point to a governed
artifact instead of only hardcoded service metadata.

The manifest is also now enforced by a dedicated validation gate:

1. `make eval-manifest-gate`

That gate validates:

1. unique evidence-category and fixture-family identifiers,
2. staged-versus-documented manifest consistency,
3. existence of referenced fixture files,
4. basic fixture-file shape, including unique `case_id` values and object-shaped `input` and `expected` sections.

The first concrete staged fixture asset now exists at:

1. [basic_cases.json](C:/Users/Sandeep/projects/lotus-ai/docs/evals/fixtures/explain.v1/basic_cases.json)

The second concrete staged fixture asset now exists at:

1. [basic_cases.json](C:/Users/Sandeep/projects/lotus-ai/docs/evals/fixtures/summarize.v1/basic_cases.json)

The first retrieval-oriented staged fixture asset now exists at:

1. [basic_cases.json](C:/Users/Sandeep/projects/lotus-ai/docs/evals/fixtures/retrieval.search/basic_cases.json)

The first provider-policy staged fixture asset now exists at:

1. [basic_cases.json](C:/Users/Sandeep/projects/lotus-ai/docs/evals/fixtures/providers.policy/basic_cases.json)

This gives the platform real file-backed fixture families for `explain.v1`, `summarize.v1`,
governed retrieval citation/refusal behavior, and provider-policy behavior while the remaining
inventory stays documented.
