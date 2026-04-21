# RFC-0097 Slice 2 Task-Flow Store Review

## Scope

Slice 2 adds the local `lotus-ai` persistence foundation for long-running workflow-pack task flows.
It intentionally does not add a public API route, gateway contract, Workbench surface, heartbeat
adapter, or domain handoff execution path.

## Implemented

1. `workflow_pack_task_flow_store_mode` configuration with memory and SQLAlchemy modes.
2. Memory and SQL-backed repositories for task-flow descriptors and checkpoint descriptors.
3. Alembic migration `0031_add_workflow_pack_task_flow_tables`.
4. A small service seam for creating task flows, recording checkpoints, listing checkpoints, and
   enforcing bounded lifecycle transitions.
5. Platform runtime status, metadata, startup readiness, and OpenAPI schema exposure for the
   task-flow store posture.
6. Restart-safe SQL proof for task-flow and checkpoint persistence.

## Review Findings

1. The repository persists the full typed descriptor payload while also indexing operational fields
   needed for future catalog and attention queries. This avoids duplicating every descriptor field
   as relational state before the public API shape is proven.
2. Checkpoint recording reuses the Slice 1 transition guard and rejects terminal-state reopening.
3. Store readiness follows the existing workflow-pack run-store pattern and degrades startup
   readiness when the SQL store is configured but not migrated.
4. Wiki source was updated only for platform-runtime posture because `/platform/runtime-status`
   now exposes task-flow store mode and readiness; it explicitly states that public task-flow
   routes, gateway publication, Workbench rendering, heartbeat attention, and domain handoff
   execution remain future slices.

## Proof

1. `python -m pytest tests\unit\test_workflow_pack_task_flow_store.py tests\unit\test_workflow_pack_task_flow_service.py tests\unit\test_runtime_readiness.py -q`
   - 24 passed.
2. `python -m pytest tests\integration\test_runtime_modes.py tests\integration\test_health.py tests\unit\test_platform_status.py tests\unit\test_openapi_contract.py -q`
   - 30 passed.
3. `python -m pytest tests\unit\test_workflow_pack_task_flow_contracts.py tests\unit\test_workflow_pack_task_flow_store.py tests\unit\test_workflow_pack_task_flow_service.py tests\unit\test_runtime_readiness.py tests\integration\test_runtime_modes.py tests\integration\test_health.py tests\unit\test_platform_status.py tests\unit\test_openapi_contract.py -q`
   - 60 passed.
4. `python -m ruff check ...touched files...`
   - passed.

## Remaining RFC-0097 Gaps

1. Public task-flow catalog/detail/checkpoint API routes.
2. Gateway publication and Workbench rendering of task-flow posture.
3. Advisor-brief first-wave runtime binding to task-flow records.
4. Heartbeat attention adapter for stale, blocked, degraded, and review-waiting task flows.
5. Domain handoff contract integration with owner services.
