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
