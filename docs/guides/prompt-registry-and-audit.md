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

1. repository abstraction for audit persistence,
2. in-memory adapter for simple development,
3. SQLAlchemy adapter for durable storage,
4. save-on-execution behavior,
5. retrieval by `request_id`,
6. Alembic-managed schema contract for relational persistence.

This gives us immediate traceability while keeping the persistence architecture clean.

## Why We Introduced the Repository Seam First

1. We wanted contract and service seams before durable storage complexity.
2. We wanted durable persistence to be an adapter change, not an API redesign.
3. The same execution flow should work against memory and SQL-backed stores.

## Durable Persistence Path

Current durable path:

1. `LOTUS_AI_AUDIT_STORE_MODE=sqlalchemy`
2. `LOTUS_AI_DATABASE_URL=<db-url>`

The current enterprise posture is:

1. repository adapters assume schema already exists,
2. schema changes are managed through Alembic revisions,
3. migration smoke checks are part of the normal quality gate,
4. PostgreSQL remains the canonical durable runtime target.

## Current Endpoints

1. `GET /platform/prompts`
2. `GET /platform/prompts/{task_id}`
3. `GET /ai/audit/{request_id}`

## Future Direction

Likely next evolution:

1. database-backed prompt registry or prompt asset packaging,
2. PostgreSQL-backed runtime persistence beyond the initial audit table,
3. tenant-aware prompt selection,
4. prompt promotion and rollback workflow,
5. richer audit records including safety-policy outcomes.
