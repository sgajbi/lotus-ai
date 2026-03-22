# API Documentation Standard

This document defines the minimum API documentation standard for `lotus-ai`.

The goal is not only to produce valid OpenAPI. The goal is to produce a stable, readable, reviewable contract that another Lotus team can rely on without reading service internals.

## Why This Standard Exists

`lotus-ai` is intended to become shared platform infrastructure for the Lotus estate.

That means the API contract must be:

1. understandable by new engineers,
2. stable enough for downstream clients,
3. explicit enough for review and governance,
4. strong enough to support enterprise delivery expectations.

## Required For Every Non-Exempt Endpoint

Every non-health endpoint must define:

1. `tags`
2. `summary`
3. `description`
4. explicit `operation_id`
5. a success response
6. at least one error response

Health and metrics endpoints are exempt from the full documentation requirement because they are operational probes rather than product-facing contracts.

## `operation_id` Rules

`operation_id` values are treated as part of the public API contract.

They must be:

1. explicit in route declarations,
2. unique across the service,
3. stable across refactors unless a real contract change is intended,
4. written in clear action-oriented camelCase such as `getCapabilityCatalog` or `executeTask`.

Do not rely on framework-generated `operationId` values for governed endpoints. Generated identifiers are implementation artifacts and can drift during refactors.

## Summary Rules

The `summary` should:

1. fit on one line,
2. start with a verb,
3. describe the contract outcome, not the implementation detail.

Good examples:

1. `List approved retrieval sources`
2. `Execute a bounded lotus-ai task`
3. `Get lotus-ai audit record`

## Description Rules

The `description` should explain:

1. what the endpoint returns or does,
2. any important phase or policy caveats,
3. any constraints that a caller should know before integration.

Descriptions should be concise but specific. They should not copy internal implementation details that are likely to churn.

## Response Documentation Rules

Every governed endpoint must document:

1. the expected successful response category,
2. the most relevant client-visible error categories.

At this phase, concise response descriptions are enough. As the service matures, examples and richer schema-linked documentation can be added where they improve clarity.

## Schema Documentation Rules

Pydantic models used in request and response contracts should:

1. use descriptive field names,
2. include `Field(description=...)` for externally meaningful fields,
3. avoid ambiguous or overloaded fields,
4. preserve domain-neutral platform terminology unless a domain-owned contract requires otherwise.

## Change Management Rules

If an API documentation change alters:

1. endpoint meaning,
2. request shape,
3. response shape,
4. `operation_id`,
5. error semantics,

then the change should be reviewed as a contract change, not as a cosmetic documentation update.

## Enforcement

This standard is enforced in CI through `scripts/openapi_quality_gate.py`.

The gate currently checks:

1. path presence,
2. `summary`,
3. `description`,
4. `tags`,
5. `operationId`,
6. unique `operationId` values,
7. at least one `2xx` response,
8. at least one `4xx` or `5xx` response.

If this standard evolves, the CI gate should evolve with it so the documented expectation and the automated enforcement remain aligned.
