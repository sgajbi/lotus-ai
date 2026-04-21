# RFC-0097 Slice 4 Task-Flow Runtime Binding Review

## Scope

Slice 4 binds task-flow recording into the existing Phase-1 workflow-pack execution paths in
`lotus-ai`. It covers both explicit `/platform/workflow-packs/execute` execution and implicit
pack-backed `/ai/tasks/execute` recording.

## Implemented

1. Preflight task-flow store readiness before pack-backed execution, matching the run-ledger
   readiness posture.
2. Task-flow id generation from workflow-pack family and run request id.
3. Initial task-flow recording with run refs, runtime state, review state, supportability posture,
   authorization evidence, and readiness evidence.
4. Checkpoint recording after the workflow-pack run is written.
5. Failed execution mapping to failed task-flow posture with degraded checkpoint evidence.
6. SQL-backed restart proof that task-flow records survive alongside run-ledger records.

## Review Findings

1. Blocking execution when the task-flow store is degraded is the truthful behavior; otherwise
   long-running workflow-pack flows could produce run-ledger state without task-flow traceability.
2. The task-flow recorder is a separate service module so execution orchestration stays readable.
3. Existing task-flow read-only APIs were reused as proof surfaces instead of adding a mutation API.
4. One remaining tightening gap is now explicit: run review actions update run lineage, but
   task-flow replacement-lineage descriptors are not yet synchronized from `REVISE` and
   `SUPERSEDE` review actions.

## Proof

1. `python -m pytest tests\integration\test_workflow_pack_run_api_contract.py tests\integration\test_workflow_pack_task_flow_api_contract.py tests\unit\test_openapi_contract.py -q`
   - 37 passed.
2. `python -m ruff check ...touched workflow-pack runtime binding files...`
   - passed.

## Remaining RFC-0097 Gaps

1. Review-action synchronization into task-flow replacement lineage.
2. Gateway publication and Workbench rendering of task-flow posture.
3. Heartbeat attention adapter for stale, blocked, degraded, and review-waiting task flows.
4. Domain handoff contract integration with owner services.
5. Second-last governance review and final docs/context/wiki/skills/branch-hygiene slices.
