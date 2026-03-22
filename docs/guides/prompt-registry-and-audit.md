# Prompt Registry and Audit

This guide explains the current prompt-registry and audit design in `lotus-ai`.

## Why This Exists

The task execution contract established the public integration surface.

The next platform requirement is traceability:

1. every task execution should resolve to an explicit prompt version,
2. every execution should leave a retrievable audit record,
3. future provider integrations should not change the shape of that traceability model.

## Prompt Registry

Current implementation:

1. in-repo registry keyed by `task_id`,
2. versioned prompt descriptors,
3. one prompt descriptor per registered task.

Current prompt fields:

1. `task_id`
2. `prompt_version`
3. `prompt_kind`
4. `system_instructions`
5. `output_contract_notes`

This is intentionally simple for foundation phase.

## Audit Store

Current implementation:

1. in-memory audit store abstraction,
2. save-on-execution behavior,
3. retrieval by `request_id`.

This gives us immediate traceability while keeping persistence pragmatic.

## Why In-Memory First

1. We want the contract and service seams first.
2. We do not yet need a durable database just to validate the architecture.
3. Moving to PostgreSQL later should be an implementation change behind the same service interfaces.

## Current Endpoints

1. `GET /platform/prompts`
2. `GET /platform/prompts/{task_id}`
3. `GET /ai/audit/{request_id}`

## Future Direction

Likely next evolution:

1. prompt files or database-backed prompt registry,
2. durable audit persistence in PostgreSQL,
3. tenant-aware prompt selection,
4. prompt promotion and rollback workflow,
5. richer audit records including safety-policy outcomes.
