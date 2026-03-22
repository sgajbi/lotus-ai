# Phased Roadmap

This roadmap is the canonical execution plan for `lotus-ai`.

The guiding principle is:

build the minimum platform slice that is useful, well-governed, and easy to understand before expanding into more powerful AI behaviors.

## Phase 0: Service Foundation

Goals:

1. Establish repository standards and branch governance.
2. Define service purpose, boundaries, and non-goals.
3. Create architecture, security, integration, and evaluation documents.
4. Introduce typed capability and task contracts.

Delivery outcomes:

1. `lotus-ai` exists as a standard Lotus backend repo.
2. New engineers can understand what the service is for and how it should evolve.
3. Calling apps can discover supported AI task categories through stable contracts.

## Phase 1: Contract-First AI Task Layer

Goals:

1. Define canonical request and response contracts for bounded AI tasks.
2. Introduce task identifiers, task classes, and output modes.
3. Add capability discovery endpoints.
4. Establish the first eval fixtures for contract and policy behavior.

Delivery outcomes:

1. Upstream Lotus apps can integrate against stable contracts.
2. The platform can version AI features before real model execution is introduced.

## Phase 2: Prompt Registry and Settings

Goals:

1. Add prompt registry abstractions.
2. Version prompts explicitly.
3. Add runtime settings for provider, safety, and audit policy behavior.
4. Ensure every AI task is traceable to a task id and prompt version.

Delivery outcomes:

1. Prompt changes become reviewable and reversible.
2. The service has a clear bridge from contract to execution policy.
3. Task execution flows through an explicit provider gateway even while live execution remains disabled.

## Phase 3: Audit, Safety, and Redaction

Goals:

1. Add AI request audit records.
2. Add response labeling and redaction policy.
3. Add role-aware access hooks and usage policy gates.
4. Define minimum evidence retained for enterprise review.

Delivery outcomes:

1. The service can be used in supportable pre-production workflows.
2. AI output can be inspected, attributed, and governed.

## Phase 4: Knowledge Retrieval

Goals:

1. Index approved Lotus documents:
   - RFCs
   - standards
   - architecture docs
   - OpenAPI-derived documentation
2. Support search and citation-backed knowledge answers.
3. Keep source freshness and provenance explicit.
4. Use PostgreSQL with `pgvector` as the first vector-store architecture.

Delivery outcomes:

1. `lotus-ai` becomes a trustworthy platform knowledge layer.
2. New engineers and downstream apps can consume cited platform explanations.

## Phase 5: First Real Domain Integration

Preferred first integration:

1. `lotus-manage` explanation of rebalance run outcomes.

Why:

1. high value,
2. low execution risk,
3. clear structured inputs,
4. deterministic domain system remains in control.

Delivery outcomes:

1. One real Lotus app gets business value from `lotus-ai`.
2. The integration pattern becomes the template for other apps.

## Phase 6: Expansion Across Lotus Apps

Likely next adopters:

1. `lotus-advise` for workflow summaries,
2. `lotus-risk` for risk explanations,
3. `lotus-performance` for analytics commentary,
4. `lotus-core` for supportability triage.

## Phase 7: Async Runs and Controlled Tool Use

Goals:

1. Add async task execution.
2. Add governed tool invocation patterns.
3. Keep human-in-the-loop controls where consequences are non-trivial.

This phase should only start after prior phases have real usage evidence.
