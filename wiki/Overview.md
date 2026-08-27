# Overview

## Repository Role

`lotus-ai` is the shared AI capability service for Lotus applications.

It exists to provide a governed AI layer that downstream repos can use without surrendering domain
ownership. The service is intentionally capability-oriented rather than domain-authoritative.

## Ownership Boundaries

`lotus-ai` owns:

1. bounded AI execution contracts,
2. prompt, provider, retrieval, safety, and evaluation governance,
3. async runtime for governed AI work,
4. AI-specific observability, evidence, and control-plane surfaces.

`lotus-ai` does not own:

1. portfolio or transaction truth,
2. performance or risk conclusions,
3. advisory or management workflow authority,
4. downstream business decisions beyond the explicit task contracts it exposes.

Calling services remain responsible for:

1. assembling the business context,
2. preserving domain semantics,
3. deciding how AI output is applied,
4. handling user-facing consequences.

## Current Product Shape

The service is in a governed foundation phase with real runtime behavior already implemented.

What is real today:

1. typed task contracts,
2. prompt rollout state and audit traceability,
3. governed retrieval and citation-carrying answer paths,
4. safety policy and safety runtime posture surfaces,
5. runtime-backed evaluation and approval-gate posture,
6. async jobs, attempts, leases, and worker-backed execution for governed job types,
7. provider operations controls for quota, budget, and degradation posture.

What remains intentionally bounded:

1. live provider rollout is controlled and not generally enabled,
2. retrieval remains curated and bounded rather than open-ended,
3. prompt bodies remain repository-managed even though runtime selection is durable,
4. production readiness depends on evidence-backed governance posture, not on feature count alone.

## Why This Matters in Lotus

Lotus applications need AI support without allowing the AI service to become the implicit source of
business truth. `lotus-ai` is designed to keep that line clear:

1. domain services own data and deterministic conclusions,
2. `lotus-gateway` and other callers assemble governed context,
3. `lotus-ai` executes bounded AI behavior against that context,
4. downstream systems preserve audit, evidence, and output-label metadata.

## Read Next

1. use [Architecture](Architecture) for the runtime shape and execution flow,
2. use [Platform Surfaces](Platform-Surfaces) for the grouped public API map,
3. use [Roadmap](Roadmap) for what is intentionally bounded versus expanding.
