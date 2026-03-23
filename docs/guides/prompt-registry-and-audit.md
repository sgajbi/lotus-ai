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

1. repository abstraction for prompt definitions and rollout state,
2. in-memory prompt registry for simple development,
3. SQLAlchemy-backed prompt registry for durable storage,
4. versioned prompt descriptors,
5. one active rollout-state record per registered task,
6. durable rollout-event history for promote and rollback actions.

Current prompt fields:

1. `task_id`
2. `prompt_version`
3. `prompt_kind`
4. `lifecycle_status`
5. `management_mode`
6. `source_reference`
7. `system_instructions`
8. `output_contract_notes`

This is intentionally simple for foundation phase.

Current durable path:

1. `LOTUS_AI_PROMPT_STORE_MODE=sqlalchemy`
2. `LOTUS_AI_DATABASE_URL=<db-url>`

The current enterprise posture is:

1. prompt definitions can remain memory-backed for local development,
2. durable prompt definitions and rollout state are seeded and managed through Alembic revisions,
3. prompt-store mode is independent from audit and retrieval store mode,
4. prompt definitions expose lifecycle and provenance metadata in every store mode,
5. runtime prompt selection now resolves through explicit rollout state rather than assuming a single mutable active row,
6. bounded promote and rollback actions now update rollout state through durable control history,
7. prompt bodies still remain repository-managed,
8. public prompt APIs do not change when the backing store changes.

## Prompt Governance

Current governance posture:

1. prompt-body mutation APIs are disabled,
2. prompt promotion and rollback write APIs are enabled only for governed rollout-state actions,
3. durable rollout state is now writable through bounded control-plane actions,
4. prompt bodies still change through reviewed repository changes,
5. SQL-backed prompt promotion state is completed through Alembic-managed persistence plus durable control history,
6. the current governance posture is visible through `GET /platform/prompts/governance`,
7. the active runtime prompt selection set is visible through `GET /platform/prompts/runtime-status`,
8. prompt control history is visible through `GET /platform/prompts/control-history`,
9. prompt control actions are applied through `POST /platform/prompts/control-actions`,
10. the current prompt activation-readiness posture is visible through `GET /platform/prompts/activation-readiness`,
11. the current prompt operational-readiness posture is visible through `GET /platform/prompts/runbook-readiness`,
12. the current prompt evidence-readiness posture is visible through `GET /platform/prompts/evidence-readiness`,
13. the combined prompt rollout review posture is visible through `GET /platform/prompts/governance-status`,
14. the combined prompt rollout review posture now includes technical, operational, and evidence readiness in one response.

## Audit Store

Current implementation:

1. repository abstraction for audit persistence,
2. in-memory adapter for simple development,
3. SQLAlchemy adapter for durable storage,
4. save-on-execution behavior,
5. retrieval by `request_id`,
6. Alembic-managed schema contract for relational persistence.

This gives us immediate traceability while keeping the persistence architecture clean.

Audit records now also preserve prompt selection trace, including rollout role and latest durable
prompt control event, so prompt promotion and rollback history can be reconstructed from the same
runtime artifacts that already capture task, provider, safety, and retrieval posture.

Current audit fields also include execution safety posture:

1. `safety_mode`
2. `redaction_posture`
3. `enforced_safety_controls`

Current audit fields also preserve caller traceability:

1. `caller_app`
2. `correlation_id`
3. `requested_by`
4. `tenant_id`

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
3. `GET /platform/prompts/governance`
4. `GET /platform/prompts/runtime-status`
5. `GET /platform/prompts/activation-readiness`
6. `GET /platform/prompts/runbook-readiness`
7. `GET /platform/prompts/evidence-readiness`
8. `GET /platform/prompts/governance-status`
9. `GET /platform/prompts/control-history`
10. `POST /platform/prompts/control-actions`
11. `GET /ai/audit/{request_id}`
12. `GET /ai/audit`

`GET /ai/audit` supports bounded filtering by:

1. `caller_app`
2. `task_id`
3. `category`
4. `output_label`
5. `requested_by`
6. `tenant_id`
7. `limit`

## Future Direction

Likely next evolution:

1. prompt promotion and rollback workflow,
2. tenant-aware prompt selection,
3. richer prompt approval status and promotion-history metadata,
4. richer audit records including safety-policy outcomes.
