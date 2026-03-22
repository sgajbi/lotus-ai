# Decision Log

This file records the core architectural decisions for `lotus-ai` in a concise format.

## Decision 1: Separate AI Platform Service

Decision:

`lotus-ai` is a separate Lotus application rather than embedding all AI capability directly into every Lotus repo.

Why:

1. central prompt and safety governance,
2. shared auditability,
3. reusable retrieval and evaluation tooling,
4. lower duplication across apps.

Trade-off:

Requires careful ownership discipline so the service does not absorb business logic.

## Decision 2: Domain Apps Keep Business Ownership

Decision:

Each Lotus app keeps ownership of the business meaning of AI features that touch its workflows.

Why:

1. domain services understand their own semantics,
2. deterministic systems remain authoritative,
3. AI remains assistive rather than authoritative.

## Decision 3: Build Contract-First

Decision:

Introduce capability and task contracts before real provider integrations.

Why:

1. easier integration with downstream apps,
2. clearer versioning and testing,
3. avoids provider-driven architecture drift.

## Decision 4: Start With Explanation and Retrieval

Decision:

Initial business-facing AI value should come from explanation, summarization, retrieval, and drafting.

Why:

1. lower risk,
2. high user value,
3. fits well with Lotus deterministic services,
4. easier to govern in a banking context.

## Decision 5: Enterprise-Grade Controls, Startup-Grade Scope

Decision:

Use bank-grade engineering controls, but keep the actual feature scope narrow and incremental.

Why:

1. target customers require strong governance,
2. startup constraints require disciplined sequencing rather than big-bang builds.
