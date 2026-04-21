# RFC-0097 Slice 3 Task-Flow API Review

## Scope

Slice 3 adds a read-only `lotus-ai` API surface for task-flow inspection. It deliberately avoids
public task-flow mutation, gateway publication, Workbench rendering, heartbeat attention, and domain
handoff execution.

## Implemented

1. `GET /platform/workflow-packs/task-flows`
   - bounded filters for workflow-pack id, caller, tenant, workflow surface, flow status,
     supportability status, and limit.
2. `GET /platform/workflow-packs/task-flows/{task_flow_id}`
   - task-flow descriptor plus checkpoint history.
3. `GET /platform/workflow-packs/task-flows/{task_flow_id}/checkpoints`
   - checkpoint catalog for one task flow.
4. OpenAPI operation ids, response descriptions, and schema coverage.
5. API tests for empty catalog, filtered catalog, detail, checkpoints, unknown task-flow ids,
   degraded SQL stores, and SQL restart-safe readback.
6. Shared test fixtures for task-flow descriptors and checkpoints to avoid repeated bulky setup.

## Review Findings

1. Read-only routes are the right first API slice because downstream systems can adopt a stable
   posture contract without gaining mutation authority before task-flow ownership rules are proven.
2. The catalog exposes counts for active, waiting-for-review, blocked, and terminal task-flow
   cohorts so clients do not need to infer high-level posture from raw descriptors.
3. The degraded-store response now mirrors the existing workflow-pack run-ledger readiness message
   by carrying the readiness enum in the error detail.
4. The route tests prove source-truth separation by asserting runtime state, review state, and
   checkpoint evidence are returned as distinct fields.

## Proof

1. `python -m pytest tests\unit\test_workflow_pack_task_flow_service.py tests\integration\test_workflow_pack_task_flow_api_contract.py tests\unit\test_openapi_contract.py -q`
   - 12 passed.
2. `python -m ruff check ...touched task-flow API files...`
   - passed.

## Remaining RFC-0097 Gaps

1. First-wave advisor-brief runtime binding that creates task-flow records during execution.
2. Gateway publication and Workbench rendering of task-flow posture.
3. Heartbeat attention adapter for stale, blocked, degraded, and review-waiting task flows.
4. Domain handoff contract integration with owner services.
5. Second-last governance review and final docs/context/wiki/skills/branch-hygiene slices.
